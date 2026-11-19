"""Biến vật lý không học thống kê; pipeline scaling được fit sau khi chia tập."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE_NUMERIC = ("air_temperature_k", "process_temperature_k", "rotational_speed_rpm",
                "torque_nm", "tool_wear_min")
BASE_FEATURES = ("product_type", *BASE_NUMERIC)
DERIVED = ("temperature_difference_k", "power_w", "wear_torque_min_nm")
PRODUCT_TYPES = ("L", "M", "H")


def select_inputs(frame: pd.DataFrame) -> pd.DataFrame:
    """Điểm tách đầu vào từ bảng đầy đủ; nhãn/ID không truyền vào transformer."""
    if frame.columns.duplicated().any():
        raise ValueError("Tên cột trùng.")
    return frame.loc[:, list(BASE_FEATURES)].copy()


def validate_inputs(frame: pd.DataFrame) -> None:
    """Chỉ nhận đúng sáu đầu vào; giữ ngoại lệ hữu hạn, dừng khi sai cấu trúc."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Đầu vào phải là DataFrame có tên cột.")
    if frame.columns.duplicated().any() or set(frame.columns) != set(BASE_FEATURES):
        raise ValueError("Cần đúng sáu feature, không kèm ID, nhãn hoặc feature đã tính sẵn.")
    if not frame["product_type"].isin(PRODUCT_TYPES).all():
        raise ValueError("Type thiếu hoặc ngoài miền L/M/H.")
    for name in BASE_NUMERIC:
        values = frame[name]
        if not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values):
            raise ValueError(f"Cột {name} cần có kiểu số đã kiểm tra.")
        if not np.isfinite(values.to_numpy(dtype=float, na_value=np.nan)).all():
            raise ValueError(f"Cột {name} thiếu hoặc không hữu hạn.")
        if name in {"rotational_speed_rpm", "tool_wear_min"} and values.mod(1).ne(0).any():
            raise ValueError(f"Cột {name} phải có giá trị nguyên.")


def physical_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Tính W, K và min·N·m theo từng dòng, không dùng nhãn hoặc thống kê tập."""
    validate_inputs(frame)
    result = frame.loc[:, list(BASE_FEATURES)].copy()
    result["temperature_difference_k"] = result["process_temperature_k"] - result["air_temperature_k"]
    with np.errstate(over="ignore", invalid="ignore"):
        result["power_w"] = result["torque_nm"] * result["rotational_speed_rpm"] * (2 * np.pi / 60)
        result["wear_torque_min_nm"] = result["tool_wear_min"] * result["torque_nm"]
    if not np.isfinite(result.loc[:, list(DERIVED)].to_numpy(dtype=float)).all():
        raise ValueError("Phép tính biến vật lý tạo giá trị không hữu hạn.")
    return result


class FeatureBuilder(TransformerMixin, BaseEstimator):
    """Bước đầu của pipeline: kiểm tra whitelist và tính feature theo cấu hình."""
    def __init__(self, feature_set="physical"):
        self.feature_set = feature_set

    def fit(self, X, y=None):
        self.transform(X)
        return self

    def transform(self, X):
        if self.feature_set not in {"base", "physical"}:
            raise ValueError("feature_set phải là base hoặc physical.")
        validate_inputs(X)
        return physical_features(X) if self.feature_set == "physical" else select_inputs(X)

    def get_feature_names_out(self, input_features=None):
        return np.array([*BASE_FEATURES, *(DERIVED if self.feature_set == "physical" else ())], dtype=object)


def make_preprocessor(feature_set="physical", scale_numeric=True) -> Pipeline:
    """Tạo pipeline CHƯA FIT; caller chỉ fit trên train sau khi có split chung."""
    if feature_set not in {"base", "physical"}:
        raise ValueError("feature_set phải là base hoặc physical.")
    numeric = [*BASE_NUMERIC, *(DERIVED if feature_set == "physical" else ())]
    transformer = ColumnTransformer([
        ("numeric", StandardScaler() if scale_numeric else "passthrough", numeric),
        ("type", OneHotEncoder(categories=[list(PRODUCT_TYPES)], handle_unknown="error",
                               sparse_output=False), ["product_type"]),
    ], remainder="drop", verbose_feature_names_out=False)
    return Pipeline([("features", FeatureBuilder(feature_set)), ("encode", transformer)])
