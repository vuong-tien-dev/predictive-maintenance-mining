"""Phân lớp hỏng/không hỏng; chỉ train/validation, dùng chung split và metrics."""
import hashlib
import json
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from maintenance.evaluation import choose_threshold, ranking_order, score_metrics
from maintenance.features import make_preprocessor
from maintenance.splits import config_digest, load_partition


def make_classifier(feature_set, C, class_weight, *, seed=42, max_iter=2000, tol=.0001):
    return Pipeline([
        ("preprocess", make_preprocessor(feature_set, scale_numeric=True)),
        ("model", LogisticRegression(C=C, class_weight=class_weight, solver="lbfgs",
                                     l1_ratio=0.0, max_iter=max_iter, tol=tol, random_state=seed))])


def positive_score(model, X):
    """Chọn cột xác suất đúng lớp 1; chưa khẳng định đã hiệu chuẩn ngoài mẫu."""
    classes = np.asarray(model.classes_)
    indices = np.flatnonzero(classes == 1)
    if len(indices) != 1 or len(classes) != 2 or not np.isin(classes, [0, 1]).all():
        raise ValueError("Mô hình cần đủ hai lớp 0/1.")
    values = model.predict_proba(X)[:, indices[0]]
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("Điểm phân lớp không hợp lệ.")
    return values


def run_classification(root: Path) -> dict:
    config = json.loads((root/"configs/classification.json").read_text(encoding="utf-8"))
    if config["test_access"] or not config["scale_numeric"] or config["solver"] != "lbfgs" or config["l1_ratio"] != 0:
        raise ValueError("Runner chỉ hỗ trợ validation Logistic Regression L2/lbfgs có scaling.")
    split_manifest = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    baseline_manifest = json.loads((root/"reports/tables/isolation/selection.json").read_text(encoding="utf-8"))
    if (baseline_manifest["dataset_version"] != split_manifest["dataset_version"]
            or baseline_manifest["split_manifest_digest"] != config_digest(split_manifest)):
        raise ValueError("Kết quả Isolation Forest không cùng phiên bản dữ liệu/split.")
    digest = config_digest(config)
    hashes = {name: hashlib.sha256((root/f"src/maintenance/{name}.py").read_text(
        encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()
        for name in ("classification", "features", "evaluation", "splits", "preprocessing", "quality")}
    code_digest = config_digest(hashes)
    folder = root/"reports/tables/classification"
    folder.mkdir(parents=True, exist_ok=True)
    candidates, selected_metrics, selections, coefficients = [], [], [], []
    for entry in split_manifest["files"]:
        split_id = entry["split_id"]
        train = load_partition(root, split_id, "train")
        validation = load_partition(root, split_id, "validation")
        if set(train["y"].unique()) != {0, 1}:
            raise ValueError("Train cần đủ hai lớp cho Logistic Regression.")
        current, fitted = [], {}
        for feature_set in config["feature_sets"]:
            for C in config["C_values"]:
                for weight in config["class_weights"]:
                    candidate_id = f"lr-{feature_set}-C{C:g}-{weight or 'none'}"
                    model = make_classifier(feature_set, C, weight, seed=config["seed"],
                                            max_iter=config["max_iter"], tol=config["tol"])
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", ConvergenceWarning)
                        model.fit(train["X"], train["y"])
                    scores = positive_score(model, validation["X"])
                    threshold = choose_threshold(validation["y"], scores)
                    metrics = score_metrics(validation["y"], scores, validation["keys"].reading_id,
                                            threshold, config["budgets"])
                    current.append({"split_id": split_id, "split": "validation", "candidate_id": candidate_id,
                                    "feature_set": feature_set, "C": C, "class_weight": weight or "none",
                                    "seed": config["seed"], "n_iter": int(model.named_steps["model"].n_iter_.max()), **metrics})
                    fitted[candidate_id] = model
        candidates.extend(current)
        winner = sorted(current, key=lambda r: (-r["average_precision"], -r["precision_at_50"], r["candidate_id"]))[0]
        model = fitted[winner["candidate_id"]]
        scores = positive_score(model, validation["X"])
        run_id = f"{split_id}__logistic_regression__s{config['seed']}__{digest[:10]}__{code_digest[:6]}"
        selected_metrics.append({"model_run_id": run_id, "model_family": "logistic_regression", **winner})
        table = validation["keys"].copy()
        table["model_run_id"], table["split_id"], table["split"] = run_id, split_id, "validation"
        table["model_family"], table["feature_set"] = "logistic_regression", winner["feature_set"]
        table["priority_score"] = scores
        table["predicted_failure"] = (scores >= winner["threshold"]).astype(int)
        ranks = np.empty(len(scores), dtype=int)
        ranks[ranking_order(scores, table.reading_id)] = np.arange(1, len(scores)+1)
        table["priority_rank"] = ranks
        path = root/f"artifacts/scores/{run_id}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
        model_path = root/f"artifacts/models/{run_id}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        selections.append({"split_id": split_id, "model_run_id": run_id, "candidate_id": winner["candidate_id"],
                           "feature_set": winner["feature_set"], "C": winner["C"], "class_weight": winner["class_weight"],
                           "seed": config["seed"], "threshold": winner["threshold"], "n_iter": winner["n_iter"],
                           "score_path": path.relative_to(root).as_posix(), "score_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "model_path": model_path.relative_to(root).as_posix(),
                           "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest()})
        names = model.named_steps["preprocess"].get_feature_names_out()
        for name, value in zip(names, model.named_steps["model"].coef_[0]):
            coefficients.append({"model_run_id": run_id, "split_id": split_id,
                                 "feature": name, "coefficient": float(value)})
    pd.DataFrame(candidates).to_csv(folder/"candidates.csv", index=False, lineterminator="\n")
    selected = pd.DataFrame(selected_metrics)
    selected.to_csv(folder/"validation.csv", index=False, lineterminator="\n")
    pd.DataFrame(coefficients).to_csv(folder/"coefficients.csv", index=False, lineterminator="\n")
    previous = pd.read_csv(root/"reports/tables/isolation/validation.csv")
    previous = previous.loc[previous.seed.eq(42)]
    columns = ["model_run_id", "split_id", "split", "model_family", "seed", "feature_set", "n_samples", "n_failures",
               "average_precision", "roc_auc", "precision_at_20", "precision_at_50", "recall_at_50",
               "tp_at_50", "threshold", "tp", "fp", "fn", "tn", "precision", "recall", "f1"]
    comparison = pd.concat([previous[columns], selected[columns]], ignore_index=True)
    if (comparison.groupby("split_id")["n_samples"].nunique().gt(1).any()
            or comparison.groupby("split_id")["n_failures"].nunique().gt(1).any()):
        raise ValueError("So sánh không cùng quần thể validation.")
    comparison.to_csv(folder/"comparison.csv", index=False, lineterminator="\n")
    manifest = {"experiment_version": config["version"], "config_sha256": digest,
                "source_hashes_lf_normalized": hashes, "code_digest": code_digest,
                "dataset_version": split_manifest["dataset_version"], "split_manifest_digest": config_digest(split_manifest),
                "isolation_selection_digest": config_digest(baseline_manifest), "sklearn_version": sklearn.__version__,
                "fit_uses_labels": True, "selection_uses_validation_labels": True,
                "scaler_fit_partition": "train", "test_evaluated": False, "selections": selections}
    (folder/"selection.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return manifest
