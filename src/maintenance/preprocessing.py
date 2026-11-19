"""Chuẩn hóa bảng và tách đầu vào/nhãn; chưa fit scaler hoặc chia tập."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from maintenance.features import BASE_FEATURES, physical_features, select_inputs
from maintenance.quality import label_diagnostics, read_source, typed_view


def prepare_tables(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    raw, metadata = read_source(root)
    schema = metadata["schema"]
    if list(BASE_FEATURES) != schema["feature_columns"]:
        raise ValueError("Danh sách đầu vào trong code khác schema.")
    readings = typed_view(raw, schema)
    if readings["reading_id"].duplicated().any():
        raise ValueError("ID bản ghi trùng; không tự bỏ bản ghi.")
    readings.insert(0, "dataset_version", metadata["dataset_version"])
    readings.insert(1, "schema_version", schema["schema_version"])
    keys = readings[["dataset_version", "reading_id"]].copy()
    features = pd.concat([keys, physical_features(select_inputs(readings))], axis=1)
    labels = pd.concat([keys, readings[schema["label_columns"]]], axis=1)
    modes = [c["name"] for c in schema["columns"] if c["role"] == "failure_mode"]
    counts, sparse_flags = label_diagnostics(readings, modes)
    flags = keys.merge(sparse_flags, on="reading_id", how="left", validate="one_to_one")
    for col in ("failure_without_mode", "mode_without_failure", "multiple_modes"):
        flags[col] = flags[col].astype("boolean").fillna(False)
    manifest = {"preprocessing_version": "ai4i-preprocessing-v1",
                "schema_version": schema["schema_version"], "dataset_version": metadata["dataset_version"],
                "source_sha256": metadata["sha256"], "rows_in": len(raw), "rows_out": len(readings),
                "rows_removed": 0, "labels_changed": 0, "scaler_fitted": False,
                "split_created": False, "label_flags": counts,
                "feature_columns": list(features.columns[2:]), "files": []}
    return {"readings": readings, "features": features, "labels": labels, "quality_flags": flags}, manifest


def export_prepared(root: Path) -> dict:
    tables, manifest = prepare_tables(root)
    for name, table in tables.items():
        folder = "interim" if name == "readings" else "processed"
        path = root / f"data/{folder}/ai4i-{name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.17g")
        manifest["files"].append({"path": path.relative_to(root).as_posix(),
                                  "rows": len(table), "columns": list(table.columns),
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    metadata_path = root / "data/metadata/preprocessing.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
