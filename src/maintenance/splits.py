"""Ánh xạ split dùng chung, có provenance và kiểm tra trước khi nạp tập."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split

from maintenance.features import select_inputs
from maintenance.preprocessing import prepare_tables

KEYS = ["dataset_version", "reading_id"]
PARTITIONS = ("train", "validation", "test", "gap")


def config_digest(config: dict) -> str:
    """Hash nội dung JSON chuẩn hóa, tránh khác hash khi Git đổi LF/CRLF."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assign_split(readings: pd.DataFrame, spec: dict, ratios=(.6, .2, .2), seed=42) -> pd.DataFrame:
    """Thứ tự của readings phải là thứ tự nguồn; không sort ID hoặc dùng ID làm thời gian."""
    if readings.empty or readings[KEYS].isna().any().any() or readings.duplicated(KEYS).any():
        raise ValueError("Khóa nguồn thiếu/trùng hoặc bảng rỗng.")
    if readings.dataset_version.nunique() != 1:
        raise ValueError("Mỗi ánh xạ chỉ thuộc một phiên bản nguồn.")
    if len(ratios) != 3 or any(r <= 0 for r in ratios) or not np.isclose(sum(ratios), 1):
        raise ValueError("Cần ba tỷ lệ dương có tổng bằng 1.")
    n = len(readings)
    ntrain, nval = int(n * ratios[0]), int(n * ratios[1])
    if min(ntrain, nval, n-ntrain-nval) < 1:
        raise ValueError("Không đủ dữ liệu cho ba tập.")
    gap = spec["gap_rows"]
    if not isinstance(gap, int) or gap < 0:
        raise ValueError("gap_rows phải là số nguyên không âm.")
    result = readings[KEYS].reset_index(drop=True).copy()
    result["split_id"] = spec["split_id"]
    result["source_position"] = np.arange(1, n+1)
    allocation = np.full(n, "gap", dtype=object)
    if spec["method"] == "source_order":
        if gap >= min(nval, n-ntrain-nval):
            raise ValueError("Khoảng đệm làm rỗng validation hoặc test.")
        allocation[:ntrain] = "train"
        allocation[ntrain+gap:ntrain+nval] = "validation"
        allocation[ntrain+nval+gap:] = "test"
    elif spec["method"] == "stratified_random":
        if gap:
            raise ValueError("Phân tầng ngẫu nhiên không hỗ trợ khoảng đệm.")
        y = readings.machine_failure.to_numpy()
        if not set(np.unique(y)) <= {0, 1}:
            raise ValueError("Nhãn phân tầng phải là 0/1.")
        train, holdout = train_test_split(np.arange(n), train_size=ntrain,
                                        random_state=seed, stratify=y)
        validation, test = train_test_split(holdout, train_size=nval,
                                            random_state=seed, stratify=y[holdout])
        allocation[train], allocation[validation], allocation[test] = "train", "validation", "test"
    else:
        raise ValueError("Phương pháp split không được hỗ trợ.")
    result["split"] = allocation
    return result


def validate_mapping(mapping: pd.DataFrame, readings: pd.DataFrame) -> None:
    """Kiểm tra phủ đủ, duy nhất và thứ tự khóa; không im lặng drop dòng khi join."""
    required = {*KEYS, "split_id", "source_position", "split"}
    if set(mapping.columns) != required or mapping.isna().any().any():
        raise ValueError("Ánh xạ thiếu/thừa trường hoặc có ô thiếu.")
    if mapping.duplicated(KEYS).any() or len(mapping) != len(readings):
        raise ValueError("Ánh xạ trùng hoặc sai số dòng.")
    if mapping.split_id.nunique() != 1 or not set(mapping.split) <= set(PARTITIONS):
        raise ValueError("split_id hoặc nhãn tập không hợp lệ.")
    if not np.array_equal(mapping.source_position.to_numpy(), np.arange(1, len(readings)+1)):
        raise ValueError("Thứ tự dòng nguồn sai.")
    if not mapping[KEYS].reset_index(drop=True).equals(readings[KEYS].reset_index(drop=True)):
        raise ValueError("Khóa/phiên bản nguồn không khớp ánh xạ.")
    if not all(mapping.split.eq(name).any() for name in PARTITIONS[:3]):
        raise ValueError("Một tập chính bị rỗng.")


def summarize_mapping(mapping: pd.DataFrame, readings: pd.DataFrame) -> pd.DataFrame:
    joined = mapping.merge(readings[[*KEYS, "machine_failure"]], on=KEYS, validate="one_to_one")
    summary = joined.groupby(["split_id", "split"], sort=True).agg(
        rows=("reading_id", "size"), failures=("machine_failure", "sum"),
        min_source_position=("source_position", "min"), max_source_position=("source_position", "max"))
    summary["failure_rate"] = summary.failures / summary.rows
    return summary.reset_index()


def export_splits(root: Path) -> dict:
    config_path = root / "configs/splits.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    readings = prepare_tables(root)[0]["readings"]
    manifest = {"version": config["version"], "primary": config["primary"], "seed": config["seed"],
                "config_sha256": config_digest(config),
                "config_hash_format": "JSON sort_keys=True, separators=(',', ':'), UTF-8",
                "dataset_version": readings.dataset_version.iloc[0],
                "sklearn_version": sklearn.__version__, "model_fitted": False, "files": []}
    summaries, pending = [], []
    for spec in config["protocols"]:
        if Path(spec["split_id"]).name != spec["split_id"]:
            raise ValueError("split_id không được chứa đường dẫn.")
        mapping = assign_split(readings, spec, config["ratios"], config["seed"])
        validate_mapping(mapping, readings)
        payload = mapping.to_csv(index=False, lineterminator="\n").encode("utf-8")
        path = root / f"data/processed/splits/{spec['split_id']}.csv"
        if path.exists() and path.read_bytes() != payload:
            raise ValueError("Split đã tồn tại khác nội dung; cần phiên bản split_id mới, không ghi đè.")
        pending.append((path, payload))
        manifest["files"].append({**spec, "path": path.relative_to(root).as_posix(),
                                  "sha256": hashlib.sha256(payload).hexdigest(), "rows": len(mapping)})
        summaries.append(summarize_mapping(mapping, readings))
    for path, payload in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    destination = root / "data/metadata/splits.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tables = root / "reports/tables/splits"
    tables.mkdir(parents=True, exist_ok=True)
    pd.concat(summaries, ignore_index=True).to_csv(tables/"summary.csv", index=False, lineterminator="\n")
    return manifest


def load_partition(root: Path, split_id: str, partition: str, *, allow_test=False) -> dict:
    """Nạp theo mapping đã lưu, không chia lại; truy cập test cần bật cờ tường minh."""
    if partition not in PARTITIONS[:3]:
        raise ValueError("Chỉ nạp train, validation hoặc test; không fit trên gap.")
    if partition == "test" and not allow_test:
        raise ValueError("Test dành cho đánh giá cuối; cần allow_test=True sau khi khóa cấu hình.")
    config_path = root / "configs/splits.json"
    manifest = json.loads((root/"data/metadata/splits.json").read_text(encoding="utf-8"))
    if config_digest(json.loads(config_path.read_text(encoding="utf-8"))) != manifest["config_sha256"]:
        raise ValueError("Config thay đổi sau khi tạo split.")
    entries = [entry for entry in manifest["files"] if entry["split_id"] == split_id]
    if len(entries) != 1:
        raise ValueError("split_id không tồn tại hoặc bị trùng.")
    path = root / entries[0]["path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise ValueError("Hash ánh xạ không khớp manifest.")
    mapping = pd.read_csv(path)
    readings = prepare_tables(root)[0]["readings"]
    validate_mapping(mapping, readings)
    selected = mapping.loc[mapping.split.eq(partition), KEYS]
    subset = selected.merge(readings, on=KEYS, how="left", validate="one_to_one")
    return {"keys": subset[KEYS].copy(), "X": select_inputs(subset),
            "y": subset.machine_failure.copy(), "split_id": split_id, "partition": partition}
