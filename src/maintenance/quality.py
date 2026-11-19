"""Kiểm tra nguồn và thống kê mô tả; không sửa dữ liệu hoặc học mô hình."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def read_source(root: Path) -> tuple[pd.DataFrame, dict]:
    """Đọc đúng header (kể cả BOM), kiểm tra checksum, giữ giá trị dạng chuỗi."""
    schema = json.loads((root / "configs/ai4i-schema.json").read_text(encoding="utf-8"))
    source = root / schema["source_file"]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = json.loads((root / "datasets/manifest.json").read_text(encoding="utf-8"))
    expected_hash = next(item["sha256"] for item in manifest["files"]
                         if item["path"] == "ai4i/ai4i2020.csv")
    if digest != expected_hash:
        raise ValueError("Checksum nguồn khác manifest; cần xác minh phiên bản trước khi phân tích.")
    with source.open(encoding=schema["csv"]["encoding"], newline="") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        expected = [c["source_name"] for c in schema["columns"]]
        if len(headers) != len(set(headers)) or set(headers) != set(expected):
            raise ValueError("Header thiếu, thừa hoặc trùng so với schema ai4i-v1.")
        records = list(reader)
    if any(len(row) != len(headers) for row in records):
        raise ValueError("Có dòng sai số lượng trường; không tự bỏ dòng.")
    frame = pd.DataFrame(records, columns=headers).rename(
        columns={c["source_name"]: c["name"] for c in schema["columns"]})
    return frame, {"schema": schema, "sha256": digest, "dataset_version": f"sha256:{digest}"}


def audit_columns(frame: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Đếm lỗi thay vì âm thầm ép kiểu, điền thiếu hoặc loại bản ghi."""
    result = []
    for col in schema["columns"]:
        series = frame[col["name"]]
        missing = series.isna() | series.astype("string").str.strip().eq("").fillna(False)
        invalid_type = pd.Series(False, index=series.index)
        invalid_domain = pd.Series(False, index=series.index)
        if col["dtype"] in {"integer", "float"}:
            number = pd.to_numeric(series.mask(missing), errors="coerce")
            invalid_type = (~missing) & (number.isna() | ~np.isfinite(number))
            if col["dtype"] == "integer":
                invalid_type |= (~missing) & number.notna() & number.mod(1).ne(0)
            if "allowed_values" in col:
                invalid_domain = (~missing) & (~invalid_type) & ~number.isin(col["allowed_values"])
        elif "allowed_values" in col:
            invalid_domain = (~missing) & ~series.isin(col["allowed_values"])
        result.append({"column": col["name"], "role": col["role"],
                       "missing": int(missing.sum()), "invalid_type": int(invalid_type.sum()),
                       "invalid_domain": int(invalid_domain.sum()),
                       "unique_nonmissing": int(series[~missing].nunique())})
    return pd.DataFrame(result)


def typed_view(frame: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Tạo bản xem số phục vụ thống kê, dừng khi có lỗi thay vì chữa dữ liệu."""
    audit = audit_columns(frame, schema)
    if audit[["missing", "invalid_type", "invalid_domain"]].to_numpy().sum():
        raise ValueError("Dữ liệu có lỗi kiểu/miền/thiếu; xem bảng audit trước khi thống kê.")
    result = frame.copy(deep=True)
    for col in schema["columns"]:
        if col["dtype"] in {"integer", "float"}:
            result[col["name"]] = pd.to_numeric(result[col["name"]]).astype(
                "int64" if col["dtype"] == "integer" else "float64")
    return result


def label_diagnostics(frame: pd.DataFrame, modes: list[str]) -> tuple[dict, pd.DataFrame]:
    """Giữ riêng nhãn tổng và mode; không ép quan hệ OR thành đáp án mới."""
    count = frame[modes].sum(axis=1)
    no_mode = frame["machine_failure"].eq(1) & count.eq(0)
    mode_only = frame["machine_failure"].eq(0) & count.gt(0)
    multiple = count.gt(1)
    flags = frame[["reading_id"]].copy()
    flags["failure_without_mode"] = no_mode
    flags["mode_without_failure"] = mode_only
    flags["multiple_modes"] = multiple
    summary = {"failure_without_mode": int(no_mode.sum()),
               "mode_without_failure": int(mode_only.sum()), "multiple_modes": int(multiple.sum())}
    return summary, flags.loc[no_mode | mode_only | multiple]


def analyze(root: Path) -> dict:
    """Trả bảng/metadata; danh sách ID chỉ xuất local, không nhúng vào notebook."""
    raw, metadata = read_source(root)
    schema = metadata["schema"]
    audit = audit_columns(raw, schema)
    frame = typed_view(raw, schema)
    modes = [c["name"] for c in schema["columns"] if c["role"] == "failure_mode"]
    numeric = [c["name"] for c in schema["columns"]
               if c["role"] == "feature" and c["dtype"] != "string"]
    label_summary, flags = label_diagnostics(frame, modes)
    labels = frame[schema["label_columns"]].sum().rename("positive_count").to_frame()
    labels["rate"] = labels["positive_count"] / len(frame)
    by_type = frame.groupby("product_type", observed=True).agg(
        records=("reading_id", "size"), failures=("machine_failure", "sum"))
    by_type["failure_rate"] = by_type["failures"] / by_type["records"]
    quartiles = frame[numeric].quantile([.25, .75])
    iqr = quartiles.loc[.75] - quartiles.loc[.25]
    outside = (frame[numeric].lt(quartiles.loc[.25] - 1.5 * iqr)
               | frame[numeric].gt(quartiles.loc[.75] + 1.5 * iqr))
    # Dùng thứ tự dòng nguồn chỉ để kiểm tra phụ thuộc, không biến thành thời gian.
    order = frame[numeric].apply(lambda values: values.autocorr(lag=1)).rename("lag1_source_order")
    summary = {"rows": len(frame), "columns": len(schema["columns"]),
               "dataset_version": metadata["dataset_version"], "schema_version": schema["schema_version"],
               "missing_cells": int(audit["missing"].sum()),
               "duplicate_reading_id": int(frame["reading_id"].duplicated().sum()),
               "duplicate_full_row": int(frame.duplicated().sum()),
               "duplicate_feature_rows": int(frame.duplicated(subset=schema["feature_columns"]).sum()),
               "target_positive": int(frame["machine_failure"].sum()),
               "target_rate": float(frame["machine_failure"].mean()), **label_summary,
               "scope": "full-source descriptive audit; no split or model selection",
               "source_sha256": metadata["sha256"]}
    return {"summary": summary, "frame": frame, "schema": schema,
            "column_audit": audit, "labels": labels, "by_type": by_type,
            "numeric_summary": frame[numeric].describe().T,
            "pearson": frame[numeric].corr(method="pearson"),
            "spearman": frame[numeric].corr(method="spearman"),
            "iqr_flags": outside.sum().rename("outside_1_5_iqr").to_frame(),
            "source_order": order.to_frame(), "label_flags": flags}


def export_analysis(result: dict, root: Path) -> None:
    """Xuất bảng tổng hợp lên reports; bằng chứng cấp bản ghi chỉ giữ local."""
    tables = root / "reports/tables/quality"
    local = root / "artifacts/metrics/quality"
    tables.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    (tables / "summary.json").write_text(
        json.dumps(result["summary"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for key in ("column_audit", "labels", "by_type", "numeric_summary", "pearson",
                "spearman", "iqr_flags", "source_order"):
        result[key].to_csv(tables / f"{key}.csv", index=key != "column_audit", encoding="utf-8")
    result["label_flags"].to_csv(local / "label_flags.csv", index=False)


def plot_analysis(result: dict, root: Path) -> list[Path]:
    """Biểu đồ mô tả nguồn; không phải dashboard Superset hoặc kết quả dự đoán."""
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    destination = root / "reports/figures/quality"
    destination.mkdir(parents=True, exist_ok=True)
    frame = result["frame"]
    paths = []

    def save(fig, name):
        path = destination / name
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    counts = frame["machine_failure"].value_counts().reindex([0, 1], fill_value=0)
    bars = axes[0].bar(["Không hỏng (0)", "Hỏng (1)"], counts, color=["#347e9b", "#d55e00"])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylim(0, counts.max() * 1.16)
    axes[0].set_title("Mất cân bằng nhãn tổng")
    axes[0].set_ylabel("Số bản ghi")
    result["labels"].drop(index="machine_failure")["positive_count"].plot.bar(
        ax=axes[1], color="#347e9b", rot=0)
    axes[1].set_title("Số nhãn chế độ hỏng (có thể chồng lấp)")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Số nhãn bằng 1")
    save(fig, "01-labels.png")

    names = list(result["numeric_summary"].index)
    titles = ["Không khí (K)", "Quá trình (K)", "Tốc độ (rpm)", "Mô-men (N·m)", "Độ mòn (min)"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), layout="constrained")
    for axis, name, title in zip(axes.flat, names, titles):
        axis.hist(frame[name], bins=35, color="#347e9b", edgecolor="white", linewidth=.3)
        axis.set_title(title)
        axis.set_ylabel("Số bản ghi")
    axes.flat[-1].axis("off")
    fig.suptitle("Phân phối thông số gốc — giữ nguyên cả các giá trị cực đoan")
    save(fig, "02-distributions.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for axis, method in zip(axes, ["pearson", "spearman"]):
        matrix = result[method]
        picture = axis.imshow(matrix, cmap="RdBu_r", vmin=-1, vmax=1)
        axis.set_xticks(range(len(names)), titles, rotation=45, ha="right")
        axis.set_yticks(range(len(names)), titles)
        axis.set_title(method.capitalize())
        for i in range(len(names)):
            for j in range(len(names)):
                value = matrix.iloc[i, j]
                axis.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=9,
                          color="white" if abs(value) > .6 else "black")
    fig.colorbar(picture, ax=axes, shrink=.7, label="Hệ số tương quan")
    save(fig, "03-correlations.png")

    fig, axes = plt.subplots(2, 1, figsize=(11, 5), layout="constrained")
    for axis, name, title in zip(axes, names[:2], titles[:2]):
        axis.plot(range(1, len(frame) + 1), frame[name], linewidth=.65, color="#347e9b")
        axis.set_ylabel(title)
    axes[0].set_title("Nhiệt độ theo thứ tự dòng nguồn — không phải trục thời gian")
    axes[-1].set_xlabel("Vị trí dòng trong CSV")
    save(fig, "04-source-order.png")
    return paths
