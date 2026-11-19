"""Isolation Forest học không nhãn; chọn cấu hình trên validation, chưa nạp test."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline

from maintenance.evaluation import choose_threshold, random_priority, ranking_order, score_metrics
from maintenance.features import make_preprocessor
from maintenance.splits import config_digest, load_partition


def make_isolation(feature_set, max_samples, seed, *, n_estimators=200):
    return Pipeline([
        ("preprocess", make_preprocessor(feature_set, scale_numeric=False)),
        ("model", IsolationForest(n_estimators=n_estimators, max_samples=max_samples,
                                  contamination="auto", random_state=seed, n_jobs=1))])


def anomaly_score(model, X):
    """score_samples cao = bình thường hơn; đảo dấu đúng một lần."""
    return -model.score_samples(X)


def run_isolation(root: Path) -> dict:
    config = json.loads((root/"configs/isolation.json").read_text(encoding="utf-8"))
    if config["test_access"] or config["scale_numeric"] or config["contamination"] != "auto":
        raise ValueError("Runner validation này không hỗ trợ mở test hoặc đổi scaling/contamination.")
    split_manifest = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    digest = config_digest(config)
    source_hashes = {name: hashlib.sha256((root/f"src/maintenance/{name}.py").read_text(
        encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()
        for name in ("models", "evaluation", "features", "splits", "preprocessing", "quality")}
    code_digest = config_digest(source_hashes)
    tables = root/"reports/tables/isolation"
    tables.mkdir(parents=True, exist_ok=True)
    candidates, evaluations, selections = [], [], []
    for entry in split_manifest["files"]:
        split_id = entry["split_id"]
        train = load_partition(root, split_id, "train")
        validation = load_partition(root, split_id, "validation")
        X, y, keys = validation["X"], validation["y"], validation["keys"]
        fitted = {}
        current = []
        for feature_set in config["feature_sets"]:
            for size in config["max_samples"]:
                candidate = f"if-{feature_set}-m{size}"
                model = make_isolation(feature_set, size, config["selection_seed"],
                                       n_estimators=config["n_estimators"])
                model.fit(train["X"])  # Không truyền y hoặc lọc theo nhãn.
                scores = anomaly_score(model, X)
                threshold = choose_threshold(y, scores)
                metrics = score_metrics(y, scores, keys.reading_id, threshold, config["budgets"])
                row = {"split_id": split_id, "candidate_id": candidate, "feature_set": feature_set,
                       "max_samples": size, "seed": config["selection_seed"], "split": "validation", **metrics}
                current.append(row)
                fitted[candidate] = model
        candidates.extend(current)
        winner = sorted(current, key=lambda r: (-r["average_precision"], -r["precision_at_50"], r["candidate_id"]))[0]
        chosen = {"split_id": split_id, "candidate_id": winner["candidate_id"],
                  "feature_set": winner["feature_set"], "max_samples": winner["max_samples"],
                  "selection_seed": config["selection_seed"], "n_estimators": config["n_estimators"],
                  "selection_metric": "validation average_precision", "runs": []}
        for seed in config["repeat_seeds"]:
            model = fitted[winner["candidate_id"]] if seed == config["selection_seed"] else make_isolation(
                winner["feature_set"], winner["max_samples"], seed, n_estimators=config["n_estimators"])
            if seed != config["selection_seed"]:
                model.fit(train["X"])
            for family in ("isolation_forest", "random", "always_normal"):
                if family == "isolation_forest":
                    scores = anomaly_score(model, X)
                elif family == "random":
                    scores = random_priority(keys, seed)
                else:
                    scores = np.zeros(len(X))
                threshold = 1.0 if family == "always_normal" else choose_threshold(y, scores)
                run_id = f"{split_id}__{family}__s{seed}__{digest[:10]}__{code_digest[:6]}"
                metrics = score_metrics(y, scores, keys.reading_id, threshold, config["budgets"])
                metrics["topk_applicable"] = family != "always_normal"
                if family == "always_normal":
                    for k in config["budgets"]:
                        for name in (f"tp_at_{k}", f"precision_at_{k}", f"recall_at_{k}"):
                            metrics[name] = None
                evaluations.append({"model_run_id": run_id, "split_id": split_id, "split": "validation",
                                    "model_family": family, "feature_set": winner["feature_set"] if family == "isolation_forest" else "none",
                                    "seed": seed, **metrics})
                score_table = keys.copy()
                score_table["model_run_id"] = run_id
                score_table["split_id"] = split_id
                score_table["split"] = "validation"
                score_table["model_family"] = family
                score_table["feature_set"] = winner["feature_set"] if family == "isolation_forest" else "none"
                score_table["priority_score"] = scores
                score_table["predicted_failure"] = (scores >= threshold).astype(int)
                order = ranking_order(scores, keys.reading_id)
                ranks = np.empty(len(scores), dtype=int)
                ranks[order] = np.arange(1, len(scores)+1)
                score_table["priority_rank"] = ranks
                path = root/f"artifacts/scores/{run_id}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                score_table.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
                run = {"model_run_id": run_id, "model_family": family, "seed": seed,
                       "threshold": threshold, "score_path": path.relative_to(root).as_posix(),
                       "score_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                if family == "isolation_forest":
                    model_path = root/f"artifacts/models/{run_id}.joblib"
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    joblib.dump(model, model_path)
                    run["model_path"] = model_path.relative_to(root).as_posix()
                    run["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
                chosen["runs"].append(run)
        selections.append(chosen)
    candidate_table = pd.DataFrame(candidates)
    evaluation_table = pd.DataFrame(evaluations)
    candidate_table.to_csv(tables/"candidates.csv", index=False, lineterminator="\n")
    evaluation_table.to_csv(tables/"validation.csv", index=False, lineterminator="\n")
    evaluation_table.groupby(["split_id", "model_family"])[[
        "average_precision", "roc_auc", "precision_at_50", "recall_at_50", "f1"
    ]].agg(["mean", "std"]).to_csv(tables/"seed_summary.csv", lineterminator="\n")
    manifest = {"experiment_version": config["version"], "config_sha256": digest,
                "source_hashes_lf_normalized": source_hashes, "code_digest": code_digest,
                "split_manifest_digest": config_digest(split_manifest),
                "dataset_version": split_manifest["dataset_version"], "sklearn_version": sklearn.__version__,
                "primary_split_id": split_manifest["primary"], "score_direction": "higher means more anomalous",
                "fit_uses_labels": False, "validation_labels_used_for_selection": True,
                "test_evaluated": False, "selections": selections}
    (tables/"selection.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return manifest
