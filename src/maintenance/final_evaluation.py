"""Đánh giá test từ mô hình/ngưỡng validation đã khóa; không fit hoặc chọn lại."""
import hashlib
import json
import copy
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

from maintenance.classification import positive_score
from maintenance.evaluation import binary_counts, random_priority, ranking_order, score_metrics
from maintenance.models import anomaly_score
from maintenance.preprocessing import prepare_tables
from maintenance.splits import config_digest, load_partition


def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision_view(lock):
    """So quyết định, không đòi joblib tái tạo cùng bytes giữa các lần fit lại."""
    view = copy.deepcopy(lock)
    view.pop("selection_digests", None)  # Digest manifest thay khi hash joblib thay.
    for run in view["runs"]:
        run.pop("model_sha256", None)
    return view


def freeze_selection(root: Path) -> dict:
    """Xác minh tất cả model/config/code trước lần gọi loader test đầu tiên."""
    settings = json.loads((root/"configs/evaluation.json").read_text(encoding="utf-8"))
    if settings["refit_models"] or settings["retune_thresholds"]:
        raise ValueError("Đánh giá cuối không được fit hoặc chọn ngưỡng mới.")
    split = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    records, references = [], {}
    for folder, config_name in (("isolation", "isolation"), ("classification", "classification")):
        manifest = json.loads((root/f"reports/tables/{folder}/selection.json").read_text(encoding="utf-8"))
        config = json.loads((root/f"configs/{config_name}.json").read_text(encoding="utf-8"))
        if manifest["config_sha256"] != config_digest(config) or manifest["split_manifest_digest"] != config_digest(split):
            raise ValueError("Cấu hình/split không khớp lựa chọn validation đã lưu.")
        if manifest["dataset_version"] != split["dataset_version"] or manifest["sklearn_version"] != sklearn.__version__:
            raise ValueError("Phiên bản dữ liệu/thư viện không khớp model đã lưu.")
        for name, digest in manifest["source_hashes_lf_normalized"].items():
            content = (root/f"src/maintenance/{name}.py").read_text(encoding="utf-8").replace("\r\n", "\n")
            if hashlib.sha256(content.encode()).hexdigest() != digest:
                raise ValueError(f"Mã nguồn {name} đã đổi sau huấn luyện; không tự fit lại để vượt kiểm tra.")
        references[folder] = config_digest(manifest)
        for choice in manifest["selections"]:
            runs = choice["runs"] if folder == "isolation" else [choice]
            for run in runs:
                record = {**run, "split_id": choice["split_id"],
                          "model_family": run.get("model_family", "logistic_regression"),
                          "feature_set": choice["feature_set"] if "model_path" in run else "none"}
                if not np.isfinite(record["threshold"]):
                    raise ValueError("Ngưỡng đã khóa không hợp lệ.")
                if sha_file(root/run["score_path"]) != run["score_sha256"]:
                    raise ValueError("Điểm validation không khớp provenance.")
                if "model_path" in run and sha_file(root/run["model_path"]) != run["model_sha256"]:
                    raise ValueError("File model sai hash; không nạp joblib không xác minh.")
                records.append(record)
    expected = {entry["split_id"] for entry in split["files"]}
    for split_id in expected:
        selected = [r for r in records if r["split_id"] == split_id]
        if len(selected) != 10 or {r["model_family"] for r in selected} != {
                "isolation_forest", "random", "always_normal", "logistic_regression"}:
            raise ValueError("Thiếu hoặc trùng các run đã chọn.")
    lock = {"version": settings["version"], "settings": settings,
            "selection_digests": references, "split_manifest_digest": config_digest(split),
            "primary_split_id": split["primary"], "dataset_version": split["dataset_version"],
            "runs": records}
    path = root/"data/metadata/evaluation-lock.json"
    payload = json.dumps(lock, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if decision_view(existing) != decision_view(lock):
            raise ValueError("Quyết định đánh giá đã thay đổi; dừng, không thay cấu hình sau xem test.")
        # Giữ bản chốt gốc. Model hiện tại đã được xác minh theo manifest hiện tại ở trên.
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return lock


def block_bootstrap(y, score_sets: dict, *, repeats=500, block_rows=100, seed=42) -> pd.DataFrame:
    """Khoảng percentile thăm dò; không khẳng định các khối đã độc lập."""
    y = np.asarray(y)
    if not len(y) or repeats < 1 or block_rows < 1:
        raise ValueError("Cấu hình bootstrap hoặc dữ liệu rỗng không hợp lệ.")
    if any(len(s) != len(y) or not np.isfinite(s).all() for s in score_sets.values()):
        raise ValueError("Các bộ điểm phải cùng quần thể và hữu hạn.")
    blocks = [np.arange(start, min(start+block_rows, len(y))) for start in range(0, len(y), block_rows)]
    rng = np.random.default_rng(seed)
    samples = {(family, metric): [] for family in score_sets for metric in ("average_precision", "roc_auc")}
    deltas = []
    for _ in range(repeats):
        indices = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        truth = y[indices]
        if len(np.unique(truth)) != 2:
            continue
        ap = {}
        for family, values in score_sets.items():
            points = np.asarray(values)[indices]
            ap[family] = float(average_precision_score(truth, points))
            samples[family, "average_precision"].append(ap[family])
            samples[family, "roc_auc"].append(float(roc_auc_score(truth, points)))
        if {"isolation_forest", "logistic_regression"} <= set(ap):
            deltas.append(ap["logistic_regression"]-ap["isolation_forest"])
    if deltas:
        samples["LR_minus_IF", "average_precision_difference"] = deltas
    result = []
    for (family, metric), values in samples.items():
        low, high = np.percentile(values, [2.5, 97.5]) if values else (None, None)
        result.append({"model_family": family, "metric": metric, "lower_percentile_2_5": low,
                       "upper_percentile_97_5": high, "valid_resamples": len(values),
                       "requested_resamples": repeats, "block_rows": block_rows,
                       "interpretation": "exploratory block bootstrap; independence/coverage not established"})
    return pd.DataFrame(result)


def error_groups(frame, y, predicted, top50):
    """Phân tích hậu kiểm; mode chồng lấp, không dùng làm đầu vào/xếp hạng."""
    groups = {f"Type={kind}": frame.product_type.eq(kind).to_numpy() for kind in ("L", "M", "H")}
    groups.update({f"mode={mode}": frame[mode].eq(1).to_numpy() for mode in ("twf", "hdf", "pwf", "osf", "rnf")})
    result = []
    for name, mask in groups.items():
        hits = int((y[mask] * top50[mask]).sum())
        result.append({"group": name, "rows": int(mask.sum()), "n_failures": int(y[mask].sum()),
                       "global_top50_hits": hits,
                       "global_top50_recall": hits/int(y[mask].sum()) if y[mask].sum() else None,
                       **binary_counts(y[mask], predicted[mask])})
    return result


def run_final_evaluation(root: Path) -> dict:
    lock = freeze_selection(root)  # Phải hoàn tất trước nạp/chấm test.
    settings = lock["settings"]
    output = root/"reports/tables/test"
    output.mkdir(parents=True, exist_ok=True)
    readings = prepare_tables(root)[0]["readings"]
    tables, groups, cache, artifacts = [], [], {}, []
    for split_id in sorted({r["split_id"] for r in lock["runs"]}):
        partition = load_partition(root, split_id, "test", allow_test=True)
        X, y, keys = partition["X"], partition["y"].to_numpy(), partition["keys"]
        context = keys.merge(readings, on=["dataset_version", "reading_id"], validate="one_to_one")
        for run in [r for r in lock["runs"] if r["split_id"] == split_id]:
            family = run["model_family"]
            if family == "random":
                scores = random_priority(keys, run["seed"])
            elif family == "always_normal":
                scores = np.zeros(len(y))
            else:
                model = joblib.load(root/run["model_path"])
                scores = anomaly_score(model, X) if family == "isolation_forest" else positive_score(model, X)
            metrics = score_metrics(y, scores, keys.reading_id, run["threshold"], settings["budgets"])
            metrics["topk_applicable"] = family != "always_normal"
            if family == "always_normal":
                for k in settings["budgets"]:
                    for name in (f"tp_at_{k}", f"precision_at_{k}", f"recall_at_{k}"):
                        metrics[name] = None
            tables.append({"model_run_id": run["model_run_id"], "split_id": split_id, "split": "test",
                           "model_family": family, "feature_set": run["feature_set"], "seed": run["seed"], **metrics})
            order = ranking_order(scores, keys.reading_id)
            ranks = np.empty(len(y), dtype=int)
            ranks[order] = np.arange(1, len(y)+1)
            predicted = (scores >= run["threshold"]).astype(int)
            top50 = ranks <= 50 if family != "always_normal" else np.zeros(len(y), dtype=bool)
            score_table = keys.copy()
            for name in ("model_run_id", "split_id", "model_family", "feature_set"):
                score_table[name] = run[name]
            score_table["split"], score_table["priority_score"] = "test", scores
            score_table["priority_rank"], score_table["predicted_failure"] = ranks, predicted
            path = root/f"artifacts/scores/test/{run['model_run_id']}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            score_table.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
            errors = keys.copy()
            errors["actual_failure"], errors["predicted_failure"], errors["in_global_top50"] = y, predicted, top50
            errors["error_type"] = np.where(y == predicted, "correct", np.where(predicted == 1, "FP", "FN"))
            errors_path = root/f"artifacts/metrics/test-errors/{run['model_run_id']}.csv"
            errors_path.parent.mkdir(parents=True, exist_ok=True)
            errors.to_csv(errors_path, index=False, lineterminator="\n")
            artifacts.append({"model_run_id": run["model_run_id"], "score_path": path.relative_to(root).as_posix(),
                              "score_sha256": sha_file(path), "error_path": errors_path.relative_to(root).as_posix(),
                              "error_sha256": sha_file(errors_path)})
            for group in error_groups(context, y, predicted, top50):
                groups.append({"model_run_id": run["model_run_id"], "split_id": split_id, "model_family": family,
                               "seed": run["seed"], **group})
            if run["seed"] == settings["primary_seed"]:
                cache[split_id, family] = {"y": y, "scores": scores, "metrics": metrics}
    metrics_table = pd.DataFrame(tables)
    metrics_table.to_csv(output/"metrics.csv", index=False, lineterminator="\n")
    pd.DataFrame(groups).to_csv(output/"groups.csv", index=False, lineterminator="\n")
    metrics_table.loc[metrics_table.seed.eq(settings["primary_seed"])].to_csv(output/"primary-seed.csv", index=False, lineterminator="\n")
    metrics_table.groupby(["split_id", "model_family"])[["average_precision", "roc_auc", "precision_at_50", "recall_at_50", "f1"]].agg(
        ["count", "mean", "std"]).to_csv(output/"seed_summary.csv", lineterminator="\n")
    primary = lock["primary_split_id"]
    bootstrap = block_bootstrap(cache[primary, "isolation_forest"]["y"],
        {family: cache[primary, family]["scores"] for family in ("isolation_forest", "logistic_regression")},
        repeats=settings["bootstrap_repeats"], block_rows=settings["bootstrap_block_rows"], seed=settings["bootstrap_seed"])
    bootstrap.to_csv(output/"bootstrap.csv", index=False, lineterminator="\n")
    plot_results(root, cache, primary)
    manifest = {"version": settings["version"], "lock_digest": config_digest(lock),
                "test_evaluated": True, "refit": False, "thresholds_from_validation": True,
                "runs_evaluated": len(tables), "artifacts": artifacts}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return manifest


def plot_results(root, cache, primary):
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve, roc_curve
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    destination = root/"reports/figures/test"
    destination.mkdir(parents=True, exist_ok=True)
    names = {"isolation_forest": "Isolation Forest", "logistic_regression": "Logistic Regression", "random": "Ngẫu nhiên seed 42"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for family, title in names.items():
        data = cache[primary, family]
        p, r, _ = precision_recall_curve(data["y"], data["scores"])
        axes[0].step(r, p, where="post", label=title)
        fpr, tpr, _ = roc_curve(data["y"], data["scores"])
        axes[1].plot(fpr, tpr, label=title)
    axes[0].axhline(cache[primary, "random"]["y"].mean(), color="gray", linestyle="--", label="Tỷ lệ hỏng test")
    axes[1].plot([0, 1], [0, 1], color="gray", linestyle="--")
    axes[0].set(xlabel="Recall", ylabel="Precision", title="Precision–Recall trên test chính", xlim=(0, 1), ylim=(0, 1.03))
    axes[1].set(xlabel="Tỷ lệ cảnh báo nhầm (FPR)", ylabel="Recall (TPR)", title="ROC trên test chính", xlim=(0, 1), ylim=(0, 1.03))
    for axis in axes: axis.legend(fontsize=8)
    fig.savefig(destination/"01-curves.png", dpi=150, bbox_inches="tight");plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), layout="constrained")
    for axis, family in zip(axes, ("isolation_forest", "logistic_regression")):
        m = cache[primary, family]["metrics"]
        matrix = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        axis.imshow(matrix, cmap="Blues")
        for i in range(2):
            for j in range(2): axis.text(j, i, str(matrix[i,j]), ha="center", va="center", color="white" if matrix[i,j]>matrix.max()/2 else "black")
        axis.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Không hỏng", "Hỏng"], yticklabels=["Không hỏng", "Hỏng"],
                 xlabel="Dự đoán", ylabel="Thực tế", title=names[family])
    fig.suptitle("Test chính, seed 42 — ngưỡng giữ nguyên từ validation")
    fig.savefig(destination/"02-confusion.png", dpi=150, bbox_inches="tight");plt.close(fig)
    fig, axis = plt.subplots(figsize=(8, 4), layout="constrained")
    for family, title in names.items():
        m = cache[primary, family]["metrics"]
        axis.plot([20, 50, 100], [m[f"tp_at_{k}"] for k in [20, 50, 100]], marker="o", label=title)
    prevalence = cache[primary, "random"]["y"].mean()
    axis.plot([20, 50, 100], np.array([20, 50, 100])*prevalence, linestyle="--", color="gray", label="Kỳ vọng chọn đều")
    axis.set(xlabel="Ngân sách kiểm tra k", ylabel="Số ca hỏng tìm được", title="Top-k trên test chính, seed 42", xticks=[20, 50, 100])
    axis.legend(fontsize=8)
    fig.savefig(destination/"03-budgets.png", dpi=150, bbox_inches="tight");plt.close(fig)
