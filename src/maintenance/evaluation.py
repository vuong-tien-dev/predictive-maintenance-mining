"""Chỉ số dùng chung: điểm cao ưu tiên cao, lớp dương hỏng = 1."""
import hashlib

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score


def checked_arrays(y, scores):
    truth, values = np.asarray(y), np.asarray(scores, dtype=float)
    if truth.ndim != 1 or values.ndim != 1 or len(truth) != len(values) or not len(truth):
        raise ValueError("Nhãn/điểm phải là vector cùng độ dài, không rỗng.")
    if not np.isin(truth, [0, 1]).all() or not np.isfinite(values).all():
        raise ValueError("Nhãn cần 0/1, điểm cần hữu hạn.")
    return truth.astype(int), values


def ranking_order(scores, reading_ids):
    values, ids = np.asarray(scores, dtype=float), np.asarray(reading_ids)
    if values.ndim != 1 or ids.ndim != 1 or len(values) != len(ids):
        raise ValueError("Điểm và ID cần vector cùng độ dài.")
    if not np.isfinite(values).all() or len(np.unique(ids)) != len(ids):
        raise ValueError("Điểm không hữu hạn hoặc ID trùng trong phạm vi.")
    return np.lexsort((ids, -values))


def binary_counts(y, predicted):
    truth = np.asarray(y)
    predicted = np.asarray(predicted)
    if truth.ndim != 1 or predicted.ndim != 1 or len(truth) != len(predicted):
        raise ValueError("Nhãn thực/dự đoán phải là vector cùng độ dài.")
    if not np.isin(truth, [0, 1]).all() or not np.isin(predicted, [0, 1]).all():
        raise ValueError("Nhãn thực/dự đoán cần 0/1.")
    tp = int(((truth == 1) & (predicted == 1)).sum())
    fp = int(((truth == 0) & (predicted == 1)).sum())
    fn = int(((truth == 1) & (predicted == 0)).sum())
    tn = int(((truth == 0) & (predicted == 0)).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            "precision_defined": bool(tp+fp), "recall_defined": bool(tp+fn),
            "f1_defined": bool(2*tp+fp+fn)}


def score_metrics(y, scores, reading_ids, threshold, budgets=(20, 50, 100)):
    truth, values = checked_arrays(y, scores)
    if not np.isfinite(threshold):
        raise ValueError("Ngưỡng phải hữu hạn.")
    order = ranking_order(values, reading_ids)
    result = {"n_samples": len(truth), "n_failures": int(truth.sum()),
              "threshold": float(threshold), **binary_counts(truth, values >= threshold),
              "roc_auc": float(roc_auc_score(truth, values)) if len(np.unique(truth)) == 2 else None,
              "average_precision": float(average_precision_score(truth, values)) if truth.sum() else None}
    for k in budgets:
        if not isinstance(k, int) or k < 1:
            raise ValueError("k phải là số nguyên dương.")
        available = k <= len(truth)
        hits = int(truth[order[:k]].sum()) if available else None
        result.update({f"tp_at_{k}": hits, f"precision_at_{k}": hits/k if available else None,
                       f"recall_at_{k}": hits/int(truth.sum()) if available and truth.sum() else None,
                       f"k_{k}_available": available})
    return result


def choose_threshold(y_validation, scores_validation):
    """Tối đa F1 tại ngưỡng quan sát; caller phải truyền validation, không test."""
    truth, values = checked_arrays(y_validation, scores_validation)
    if len(np.unique(truth)) != 2:
        raise ValueError("Cần đủ hai lớp validation để chọn ngưỡng theo giao thức.")
    precision, recall, thresholds = precision_recall_curve(truth, values)
    denominator = precision[:-1] + recall[:-1]
    f1 = np.divide(2*precision[:-1]*recall[:-1], denominator,
                   out=np.zeros_like(denominator), where=denominator != 0)
    best = np.flatnonzero(f1 == f1.max())[-1]
    return float(thresholds[best])


def random_priority(keys, seed):
    """Baseline ngẫu nhiên giả lập bằng hash khóa/seed, ổn định khi đổi thứ tự dòng."""
    return np.array([int.from_bytes(hashlib.sha256(
        f"{seed}|{version}|{int(identifier)}".encode()).digest()[:8], "big") / 2**64
        for version, identifier in keys[["dataset_version", "reading_id"]].itertuples(index=False, name=None)])
