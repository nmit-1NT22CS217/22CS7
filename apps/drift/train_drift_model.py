import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, brier_score_loss
from sklearn.model_selection import train_test_split

FEATURE_KEYS = [
    "semantic_drift",
    "sentiment_drift",
    "lexical_drift",
    "js_divergence",
    "mmd_drift",
    "mmd_pvalue_inv",
    "historical_drift",
    "domain_auc_shift",
    "anomaly_score",
    "trend_shift",
    "ewma_score",
    "page_hinkley_score",
    "volatility_risk",
]

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "interactions.jsonl"
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "drift_model.joblib"
MIN_SAMPLES = int(os.getenv("TRAINING_MIN_SAMPLES", "6"))
WEAK_LABEL_MIN_CONFIDENCE = float(os.getenv("WEAK_LABEL_MIN_CONFIDENCE", "0.68"))
WEAK_LABEL_HIGH_RISK = float(os.getenv("WEAK_LABEL_HIGH_RISK", "0.80"))
WEAK_LABEL_LOW_RISK = float(os.getenv("WEAK_LABEL_LOW_RISK", "0.22"))


def _label_to_binary(label):
    if label is None:
        return None
    if isinstance(label, (int, float)):
        return int(float(label) >= 0.58)
    value = str(label).strip().lower()
    if value in {"1", "high", "critical", "drift", "unsafe"}:
        return 1
    if value in {"0", "low", "moderate", "safe", "ok"}:
        return 0
    return None


def _infer_weak_label(analysis):
    if not isinstance(analysis, dict):
        return None
    confidence = float(analysis.get("confidence_score", 0.0) or 0.0)
    risk_prob = float(analysis.get("high_risk_probability", 0.0) or 0.0)
    drift_score = float(analysis.get("drift_score", 0.0) or 0.0)
    risk_level = str(analysis.get("risk_level", "")).strip().lower()

    if confidence >= WEAK_LABEL_MIN_CONFIDENCE:
        if risk_prob >= WEAK_LABEL_HIGH_RISK:
            return 1
        if risk_prob <= WEAK_LABEL_LOW_RISK:
            return 0

    if risk_level in {"critical", "high"}:
        return 1
    if risk_level == "low":
        return 0
    if drift_score >= 0.62:
        return 1
    if drift_score <= 0.35:
        return 0
    return None


def load_training_data():
    if not DATA_PATH.exists():
        return None, None, None

    x_rows = []
    y_rows = []
    manual_count = 0
    weak_count = 0
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            analysis = record.get("analysis") or {}
            label = _label_to_binary(record.get("label"))
            if label is None:
                label = _infer_weak_label(analysis)
                if label is not None:
                    weak_count += 1
            else:
                manual_count += 1

            if label is None or not isinstance(analysis, dict):
                continue

            features = [float(analysis.get(k, 0.0) or 0.0) for k in FEATURE_KEYS]
            x_rows.append(features)
            y_rows.append(label)

    if len(x_rows) < MIN_SAMPLES or len(set(y_rows)) < 2:
        return None, None, {
            "manual_labels": manual_count,
            "weak_labels": weak_count,
            "effective_samples": len(x_rows),
            "min_required": MIN_SAMPLES,
        }
    return np.array(x_rows, dtype=float), np.array(y_rows, dtype=int), {
        "manual_labels": manual_count,
        "weak_labels": weak_count,
        "effective_samples": len(x_rows),
        "min_required": MIN_SAMPLES,
    }


def train():
    x, y, data_info = load_training_data()
    if x is None:
        print("Not enough effective training samples.")
        print("Data info:", data_info)
        return 1

    class_counts = np.bincount(y)
    min_class_count = int(np.min(class_counts))
    if min_class_count < 2:
        print("Both classes need at least 2 samples for training.")
        print("Data info:", data_info)
        return 1

    # Low-data fallback: train a single model on all available samples.
    if min_class_count < 3 or len(y) < 20:
        model = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
        model.fit(x, y)
        pred_proba = model.predict_proba(x)[:, 1]
        pred = (pred_proba >= 0.5).astype(int)
        calibrator = None
        metrics = {
            "accuracy": float(accuracy_score(y, pred)),
            "f1": float(f1_score(y, pred)),
            "roc_auc": float(roc_auc_score(y, pred_proba)),
            "brier": float(brier_score_loss(y, pred_proba)),
            "samples": int(len(y)),
            "positives": int(np.sum(y)),
            "manual_labels": int(data_info["manual_labels"]),
            "weak_labels": int(data_info["weak_labels"]),
            "low_data_mode": True,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        x_train, x_val, y_train, y_val = train_test_split(
            x, y, test_size=0.25, random_state=42, stratify=y
        )

        min_class_train = int(np.min(np.bincount(y_train)))
        stack_cv = max(2, min(5, min_class_train))
        calibrate_cv = max(2, min(4, min_class_train))

        base_estimators = [
            ("lr", LogisticRegression(max_iter=1200, class_weight="balanced")),
            ("rf", RandomForestClassifier(n_estimators=450, random_state=42, class_weight="balanced")),
        ]
        model = StackingClassifier(
            estimators=base_estimators,
            final_estimator=LogisticRegression(max_iter=1200, class_weight="balanced"),
            stack_method="predict_proba",
            passthrough=True,
            cv=stack_cv,
        )
        model.fit(x_train, y_train)

        calibrator = CalibratedClassifierCV(estimator=model, method="sigmoid", cv=calibrate_cv)
        calibrator.fit(x_train, y_train)

        pred_proba = calibrator.predict_proba(x_val)[:, 1]
        pred = (pred_proba >= 0.5).astype(int)

        metrics = {
            "accuracy": float(accuracy_score(y_val, pred)),
            "f1": float(f1_score(y_val, pred)),
            "roc_auc": float(roc_auc_score(y_val, pred_proba)),
            "brier": float(brier_score_loss(y_val, pred_proba)),
            "samples": int(len(y)),
            "positives": int(np.sum(y)),
            "manual_labels": int(data_info["manual_labels"]),
            "weak_labels": int(data_info["weak_labels"]),
            "low_data_mode": False,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "calibrator": calibrator,
            "feature_keys": FEATURE_KEYS,
            "metrics": metrics,
        },
        MODEL_PATH,
    )
    print("Model trained and saved to:", MODEL_PATH)
    print("Metrics:", metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(train())
