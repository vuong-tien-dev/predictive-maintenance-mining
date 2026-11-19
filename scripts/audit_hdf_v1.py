"""Bổ sung hậu kiểm HDF từ nguồn/mapping/score v1 đã lưu; không fit hoặc chấm model."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODES = ["twf", "hdf", "pwf", "osf", "rnf"]
KEYS = ["dataset_version", "reading_id"]


def hdf_policy_counts(frame, threshold, k=None):
    """Recall mode trong chính sách dự báo hỏng tổng; không phải classifier HDF."""
    if frame.reading_id.duplicated().any() or not np.isfinite(frame.priority_score).all():
        raise ValueError("ID trùng hoặc điểm không hữu hạn.")
    total = int(frame.hdf.sum())
    if k is None:
        selected = frame.priority_score.ge(threshold).to_numpy()
    else:
        if k < 1 or k > len(frame):
            raise ValueError("Ngân sách vượt phạm vi dữ liệu.")
        order = np.lexsort((frame.reading_id.to_numpy(), -frame.priority_score.to_numpy()))
        selected = np.zeros(len(frame), dtype=bool)
        selected[order[:k]] = True
    found = int(frame.loc[selected, "hdf"].sum())
    return {"n_samples": len(frame), "n_hdf": total, "n_selected": int(selected.sum()),
            "hdf_found": found, "hdf_missed": total-found,
            "hdf_recall": found/total if total else None, "hdf_recall_defined": bool(total)}


def run_audit(root=ROOT):
    from sys import path
    path.insert(0, str(root/"src"))
    from maintenance.quality import read_source, typed_view
    from maintenance.splits import config_digest, validate_mapping
    raw, metadata = read_source(root)
    readings = typed_view(raw, metadata["schema"])
    readings.insert(0, "dataset_version", metadata["dataset_version"])
    readings["source_position"] = np.arange(1, len(readings)+1)
    source_hash = metadata["sha256"]
    block_rows = []
    for block, group in readings.groupby((readings.source_position-1)//1000):
        block_rows.append({"block_start": int(group.source_position.min()), "block_end": int(group.source_position.max()),
            "rows": len(group), "failures": int(group.machine_failure.sum()), "failure_rate": float(group.machine_failure.mean()),
            **{mode: int(group[mode].sum()) for mode in MODES}})
    split_manifest = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    lock = json.loads((root/"data/metadata/evaluation-lock.json").read_text(encoding="utf-8"))
    test_manifest = json.loads((root/"reports/tables/test/manifest.json").read_text(encoding="utf-8"))
    if config_digest(lock) != test_manifest["lock_digest"] or metadata["dataset_version"] != lock["dataset_version"]:
        raise ValueError("Nguồn hoặc khóa không khớp v1.")
    test_files = {r["model_run_id"]: r for r in test_manifest["artifacts"]}
    split_counts, coverage, inputs = [], [], []
    for entry in split_manifest["files"]:
        p = root/entry["path"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Hash mapping sai.")
        mapping = pd.read_csv(p)
        validate_mapping(mapping, readings)
        joined = mapping.merge(readings[[*KEYS, "machine_failure", *MODES]], on=KEYS, validate="one_to_one")
        for partition, group in joined.groupby("split"):
            split_counts.append({"split_id": entry["split_id"], "split": partition, "rows": len(group),
                "failures": int(group.machine_failure.sum()), **{mode: int(group[mode].sum()) for mode in MODES}})
        for run in lock["runs"]:
            if run["split_id"] != entry["split_id"] or run["seed"] != 42 or run["model_family"] not in {"isolation_forest", "logistic_regression"}:
                continue
            for partition in ("validation", "test"):
                ref = run if partition == "validation" else test_files[run["model_run_id"]]
                p = root/ref["score_path"]
                if hashlib.sha256(p.read_bytes()).hexdigest() != ref["score_sha256"]:
                    raise ValueError("Score v1 sai hash.")
                scores = pd.read_csv(p)
                expected = mapping.loc[mapping.split.eq(partition), KEYS].reset_index(drop=True)
                if not scores[KEYS].reset_index(drop=True).equals(expected):
                    raise ValueError("Quần thể score không đúng partition.")
                frame = scores.merge(readings[[*KEYS, "hdf", "machine_failure"]], on=KEYS, validate="one_to_one")
                inputs.append({"path": ref["score_path"], "sha256": ref["score_sha256"]})
                for k in (None, 20, 50, 100):
                    coverage.append({"model_run_id": run["model_run_id"], "split_id": run["split_id"], "split": partition,
                        "model_family": run["model_family"], "seed": 42, "policy": "fixed_threshold" if k is None else f"global_top{k}",
                        "threshold": run["threshold"] if k is None else None,
                        **hdf_policy_counts(frame, run["threshold"], k)})
    folder = root/"reports/tables/hdf-supplement-v1"
    folder.mkdir(parents=True, exist_ok=True)
    result = {"scope": "post-hoc mode coverage, no model fit/scoring or selection", "source_sha256": source_hash,
              "evaluation_lock_digest": config_digest(lock), "score_inputs": inputs, "outputs": []}
    for name, records in (("blocks", block_rows), ("split-modes", split_counts), ("hdf-coverage", coverage)):
        p = folder/f"{name}.csv"
        pd.DataFrame(records).to_csv(p, index=False, lineterminator="\n")
        result["outputs"].append({"path": p.relative_to(root).as_posix(), "rows": len(records),
                                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    (folder/"manifest.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(pd.DataFrame(coverage).loc[lambda t: t.split_id.eq("stratified-seed42-v1")].to_string(index=False))
    return result


if __name__ == "__main__":
    run_audit()
