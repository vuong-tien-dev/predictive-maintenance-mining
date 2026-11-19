"""Xuất giao diện CSV ổn định cho kho/dashboard và kiểm chứng độc lập."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from maintenance.evaluation import score_metrics
from maintenance.preprocessing import prepare_tables
from maintenance.splits import KEYS, config_digest, validate_mapping


def validate_scores(scores, readings, runs, mappings):
    required = [*KEYS, "model_run_id", "split_id", "split", "model_family", "feature_set",
                "priority_score", "predicted_failure", "priority_rank"]
    if list(scores.columns) != required or scores.isna().any().any():
        raise ValueError("Score thiếu/thừa/sai thứ tự cột hoặc chứa null.")
    if scores.duplicated(["model_run_id", "split", *KEYS]).any():
        raise ValueError("Score trùng grain run × split × phiên bản × bản ghi.")
    if not np.isfinite(scores.priority_score).all() or not scores.predicted_failure.isin([0, 1]).all():
        raise ValueError("Score không hữu hạn hoặc dự đoán không nhị phân.")
    for (run_id, partition), subset in scores.groupby(["model_run_id", "split"], sort=False):
        rows = runs.loc[runs.model_run_id.eq(run_id)]
        if len(rows) != 1 or partition not in {"validation", "test"}:
            raise ValueError("Run hoặc partition không hợp lệ.")
        run = rows.iloc[0]
        if not subset.split_id.eq(run.split_id).all() or not subset.model_family.eq(run.model_family).all() or not subset.feature_set.eq(run.feature_set).all():
            raise ValueError("Metadata score khác run.")
        mapping = mappings.loc[mappings.split_id.eq(run.split_id)]
        expected = mapping.loc[mapping.split.eq(partition), KEYS]
        if not subset[KEYS].reset_index(drop=True).equals(expected.reset_index(drop=True)):
            raise ValueError("Score không phủ đúng thứ tự/quần thể partition.")
        order = np.lexsort((subset.reading_id.to_numpy(), -subset.priority_score.to_numpy()))
        expected_ranks = np.empty(len(subset), dtype=int)
        expected_ranks[order] = np.arange(1, len(subset)+1)
        if not np.array_equal(expected_ranks, subset.priority_rank.to_numpy()):
            raise ValueError("Thứ hạng không đúng score giảm dần/ID tăng dần.")
        if not np.array_equal((subset.priority_score >= run.threshold).astype(int), subset.predicted_failure):
            raise ValueError("Dự đoán khác ngưỡng đã khóa.")
    expected_pairs = {(r, s) for r in runs.model_run_id for s in ("validation", "test")}
    if set(zip(scores.model_run_id, scores["split"])) != expected_pairs:
        raise ValueError("Thiếu run/partition trong scores.")


def export_handoff(root: Path) -> dict:
    prepared, _ = prepare_tables(root)
    readings = prepared["readings"]
    lock_path = root/"data/metadata/evaluation-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    test_manifest = json.loads((root/"reports/tables/test/manifest.json").read_text(encoding="utf-8"))
    if test_manifest["lock_digest"] != config_digest(lock):
        raise ValueError("Test không khớp khóa bàn giao.")
    split_manifest = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    mappings = []
    for entry in split_manifest["files"]:
        path = root/entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Hash split sai.")
        mapping = pd.read_csv(path)
        validate_mapping(mapping, readings)
        mappings.append(mapping)
    mappings = pd.concat(mappings, ignore_index=True)
    run_rows, score_tables = [], []
    ordered_columns = [*KEYS, "model_run_id", "split_id", "split", "model_family", "feature_set",
                       "priority_score", "predicted_failure", "priority_rank"]
    test_files = {item["model_run_id"]: item for item in test_manifest["artifacts"]}
    for run in lock["runs"]:
        run_rows.append({name: run[name] for name in
                        ("model_run_id", "split_id", "model_family", "feature_set", "seed", "threshold")})
        for path, digest in ((root/run["score_path"], run["score_sha256"]),
                             (root/test_files[run["model_run_id"]]["score_path"], test_files[run["model_run_id"]]["score_sha256"])):
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Hash score đầu vào không khớp; tái lập đúng bước trước.")
            score_tables.append(pd.read_csv(path)[ordered_columns])
    runs = pd.DataFrame(run_rows)
    scores = pd.concat(score_tables, ignore_index=True)
    validate_scores(scores, readings, runs, mappings)
    metrics, budgets = [], []
    for (run_id, partition), subset in scores.groupby(["model_run_id", "split"], sort=False):
        run = runs.loc[runs.model_run_id.eq(run_id)].iloc[0]
        joined = subset.merge(readings[[*KEYS, "machine_failure"]], on=KEYS, validate="many_to_one")
        values = score_metrics(joined.machine_failure, joined.priority_score, joined.reading_id,
                               run.threshold, lock["settings"]["budgets"])
        row = {"model_run_id": run_id, "split": partition, "population_scope": "all",
               "split_id": run.split_id, "model_family": run.model_family, "seed": int(run.seed),
               **{k: v for k, v in values.items() if "_at_" not in k and not k.startswith("k_")}}
        metrics.append(row)
        for k in lock["settings"]["budgets"]:
            applicable = run.model_family != "always_normal"
            budgets.append({"model_run_id": run_id, "split": partition, "population_scope": "all",
                            "budget_k": k, "n_samples": len(joined), "n_failures": int(joined.machine_failure.sum()),
                            "topk_applicable": applicable, "tp": values[f"tp_at_{k}"] if applicable else None,
                            "precision": values[f"precision_at_{k}"] if applicable else None,
                            "recall": values[f"recall_at_{k}"] if applicable else None})
    metric_table = pd.DataFrame(metrics)
    # Đối chiếu metrics nguồn, không tạo một kết quả thứ hai khác báo cáo.
    originals = pd.concat([pd.read_csv(root/f"reports/tables/{folder}/{name}.csv") for folder, name in
        (("isolation", "validation"), ("classification", "validation"), ("test", "metrics"))], ignore_index=True)
    for row in metrics:
        original = originals.loc[originals.model_run_id.eq(row["model_run_id"]) & originals["split"].eq(row["split"])]
        if len(original) != 1:
            raise ValueError("Không có một dòng metrics nguồn duy nhất.")
        for name in ("tp", "fp", "fn", "tn", "average_precision", "roc_auc", "precision", "recall", "f1"):
            a, b = row[name], original.iloc[0][name]
            if a is None and pd.isna(b):
                continue
            if not np.isclose(a, b, rtol=1e-10, atol=1e-12):
                raise ValueError(f"Metrics bàn giao khác nguồn: {name}.")
    exports = {"readings": (readings, KEYS), "features": (prepared["features"], KEYS),
               "quality_flags": (prepared["quality_flags"], KEYS),
               "split_membership": (mappings, ["split_id", *KEYS]),
               "model_runs": (runs, ["model_run_id"]),
               "scores": (scores, ["model_run_id", "split", *KEYS]),
               "metrics": (metric_table, ["model_run_id", "split", "population_scope"]),
               "budget_metrics": (pd.DataFrame(budgets), ["model_run_id", "split", "population_scope", "budget_k"])}
    destination = root/"data/processed/handoff-v1"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"version": "handoff-v1", "dataset_version": lock["dataset_version"],
                "evaluation_lock_digest": config_digest(lock), "primary_split_id": lock["primary_split_id"],
                "primary_seed": 42, "budgets": lock["settings"]["budgets"], "files": []}
    for name, (frame, grain) in exports.items():
        if frame.duplicated(grain).any():
            raise ValueError(f"Bảng {name} không duy nhất theo grain.")
        path = destination/f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.17g")
        manifest["files"].append({"table": name, "path": path.relative_to(root).as_posix(), "rows": len(frame),
                                  "primary_key": grain, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "columns": [{"name": c, "pandas_dtype": str(frame[c].dtype), "nullable": bool(frame[c].isna().any())} for c in frame]})
    for path in (destination/"manifest.json", root/"data/metadata/handoff.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return manifest


def verify_handoff(root: Path) -> dict:
    manifest = json.loads((root/"data/metadata/handoff.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = root/entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Sai hash bảng {entry['table']}.")
        frame = pd.read_csv(path)
        if len(frame) != entry["rows"] or list(frame.columns) != [c["name"] for c in entry["columns"]]:
            raise ValueError("Sai cấu trúc/số dòng.")
        if frame.duplicated(entry["primary_key"]).any():
            raise ValueError("Trùng khóa trong bảng bàn giao.")
    return manifest
