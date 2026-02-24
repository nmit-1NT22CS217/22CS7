import os
import subprocess
import sys
from pathlib import Path
from flask import Flask, request, render_template, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import joblib

from analysis_engine import analyze_response, load_history_cache, update_history_cache
from data_store import append_interaction, load_interactions, update_interaction_label
from llm_client import GroqClient

load_dotenv()

app = Flask(__name__)

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    CORS(app, origins=allowed)
else:
    CORS(app)

api_key = os.getenv("GROQ_API_KEY")
client = GroqClient(api_key=api_key)
AUTO_LABEL_ENABLED = os.getenv("AUTO_LABEL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
AUTO_LABEL_MIN_CONFIDENCE = float(os.getenv("AUTO_LABEL_MIN_CONFIDENCE", "0.78"))
AUTO_LABEL_HIGH_RISK = float(os.getenv("AUTO_LABEL_HIGH_RISK", "0.85"))
AUTO_LABEL_LOW_RISK = float(os.getenv("AUTO_LABEL_LOW_RISK", "0.20"))
WEAK_LABEL_MIN_CONFIDENCE = float(os.getenv("WEAK_LABEL_MIN_CONFIDENCE", "0.68"))
WEAK_LABEL_HIGH_RISK = float(os.getenv("WEAK_LABEL_HIGH_RISK", "0.80"))
WEAK_LABEL_LOW_RISK = float(os.getenv("WEAK_LABEL_LOW_RISK", "0.22"))
TRAINING_MIN_SAMPLES = int(os.getenv("TRAINING_MIN_SAMPLES", "6"))

METRIC_KEYS = [
    "drift_score",
    "high_risk_probability",
    "confidence_score",
    "uncertainty_score",
    "semantic_drift",
    "sentiment_drift",
    "lexical_drift",
    "js_divergence",
    "mmd_drift",
    "mmd_stat",
    "mmd_pvalue",
    "mmd_pvalue_inv",
    "historical_drift",
    "domain_auc_shift",
    "anomaly_score",
    "trend_shift",
    "ewma_score",
    "page_hinkley_score",
    "volatility_risk",
    "ml_probability",
    "model_rule_disagreement",
    "risk_level",
]
MODEL_PATH = Path(__file__).resolve().parent / "models" / "drift_model.joblib"


def _build_history_points(records):
    points = []
    for record in records:
        analysis = record.get("analysis") or {}
        if not isinstance(analysis, dict):
            continue
        point = {"timestamp": record.get("timestamp")}
        for key in METRIC_KEYS:
            point[key] = analysis.get(key)
        points.append(point)
    return points


def _is_external_record(record):
    provider = str(record.get("provider") or "").strip().lower()
    prompt = str(record.get("prompt") or "").strip().lower()
    model_name = str(record.get("model") or "").strip().lower()
    if provider in {"github", "huggingface"}:
        return True
    if prompt.startswith("[external dataset]"):
        return True
    if model_name in {"sst2-bootstrap", "cognitive-distortion-hf"}:
        return True
    return False


def _load_operational_interactions(limit=120):
    records = load_interactions(limit=12000)
    filtered = [r for r in records if not _is_external_record(r)]
    return filtered[-limit:]


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


def _build_label_stats(records):
    manual_labels = []
    effective_labels = []
    for record in records:
        manual = _label_to_binary(record.get("label"))
        if manual is not None:
            manual_labels.append(manual)
            effective_labels.append(manual)
            continue

        weak = _infer_weak_label_from_analysis(record.get("analysis"))
        if weak is not None:
            effective_labels.append(weak)

    manual_total = len(manual_labels)
    total = len(effective_labels)
    positives = int(sum(effective_labels))
    negatives = int(total - positives)
    positive_ratio = (positives / total) if total else 0.0
    ready = total >= TRAINING_MIN_SAMPLES and positives > 0 and negatives > 0
    return {
        "manual_labeled_total": manual_total,
        "labeled_total": total,
        "positives": positives,
        "negatives": negatives,
        "positive_ratio": positive_ratio,
        "ready_for_training": ready,
        "recommended_min_samples": TRAINING_MIN_SAMPLES,
    }


def _infer_auto_label(analysis):
    if not AUTO_LABEL_ENABLED or not isinstance(analysis, dict):
        return None
    confidence = float(analysis.get("confidence_score", 0.0) or 0.0)
    risk_prob = float(analysis.get("high_risk_probability", 0.0) or 0.0)

    if confidence < AUTO_LABEL_MIN_CONFIDENCE:
        return None
    if risk_prob >= AUTO_LABEL_HIGH_RISK:
        return "drift"
    if risk_prob <= AUTO_LABEL_LOW_RISK:
        return "safe"
    return None


def _infer_weak_label_from_analysis(analysis):
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


def _get_model_status():
    if not MODEL_PATH.exists():
        return {
            "available": False,
            "path": str(MODEL_PATH),
            "metrics": None,
        }
    try:
        pack = joblib.load(MODEL_PATH)
        metrics = pack.get("metrics") if isinstance(pack, dict) else None
        return {
            "available": True,
            "path": str(MODEL_PATH),
            "metrics": metrics if isinstance(metrics, dict) else None,
        }
    except Exception as exc:
        return {
            "available": False,
            "path": str(MODEL_PATH),
            "metrics": None,
            "error": str(exc),
        }


@app.route("/", methods=["GET", "POST"])
def home():
    response_text = None
    analysis = None
    error = None

    history_records = _load_operational_interactions(limit=120)
    history_points = _build_history_points(history_records)
    model_status = _get_model_status()
    label_stats = _build_label_stats(load_interactions(limit=5000))

    if request.method == "POST":
        prompt = request.form.get("prompt")

        if not prompt or prompt.strip() == "":
            error = "Prompt cannot be empty."
        else:
            try:
                response_text = client.generate_response(prompt)
                recent_responses = [
                    r.get("response", "")
                    for r in history_records[-40:]
                    if isinstance(r.get("response"), str)
                ]
                recent_analyses = [
                    r.get("analysis", {})
                    for r in history_records[-60:]
                    if isinstance(r.get("analysis"), dict)
                ]

                analysis = analyze_response(
                    response_text,
                    history_texts=recent_responses,
                    history_scores=recent_analyses,
                    history_cache=load_history_cache(),
                )

                record = append_interaction(
                    prompt=prompt,
                    response=response_text,
                    analysis=analysis,
                    model=client.model,
                    provider=client.provider,
                )
                auto_label = _infer_auto_label(analysis)
                if auto_label:
                    update_interaction_label(timestamp=record["timestamp"], label=auto_label)
                update_history_cache(response_text)

                history_records = _load_operational_interactions(limit=120)
                history_points = _build_history_points(history_records)
                model_status = _get_model_status()
                label_stats = _build_label_stats(load_interactions(limit=5000))
            except Exception as exc:
                error = f"Error during processing: {str(exc)}"

    return render_template(
        "index.html",
        response=response_text,
        analysis=analysis,
        error=error,
        history_points=history_points,
        model_status=model_status,
        label_stats=label_stats,
    )


@app.route("/analyze", methods=["POST"])
def analyze_api():
    data = request.json
    if not data or "prompt" not in data:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        response_text = client.generate_response(data["prompt"])
        recent_records = _load_operational_interactions(limit=120)
        recent_responses = [
            r.get("response", "")
            for r in recent_records[-40:]
            if isinstance(r.get("response"), str)
        ]
        recent_analyses = [
            r.get("analysis", {})
            for r in recent_records
            if isinstance(r.get("analysis"), dict)
        ]
        analysis = analyze_response(
            response_text,
            history_texts=recent_responses,
            history_scores=recent_analyses,
            history_cache=load_history_cache(),
        )

        record = append_interaction(
            prompt=data["prompt"],
            response=response_text,
            analysis=analysis,
            model=client.model,
            provider=client.provider,
        )
        auto_label = _infer_auto_label(analysis)
        if auto_label:
            update_interaction_label(timestamp=record["timestamp"], label=auto_label)
        update_history_cache(response_text)

        return jsonify({
            "response": response_text,
            "analysis": analysis,
            "record": record,
            "auto_label": auto_label,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/history", methods=["GET"])
def history_api():
    limit = request.args.get("limit", default=120, type=int)
    records = _load_operational_interactions(limit=limit)
    return jsonify({"count": len(records), "records": records, "points": _build_history_points(records)})


@app.route("/feedback", methods=["POST"])
def feedback_api():
    data = request.json or {}
    timestamp = data.get("timestamp")
    label = data.get("label")
    if not timestamp or label is None:
        return jsonify({"error": "timestamp and label are required"}), 400

    ok = update_interaction_label(timestamp=timestamp, label=label)
    if not ok:
        return jsonify({"error": "matching interaction not found"}), 404
    return jsonify({"status": "ok", "timestamp": timestamp, "label": label})


@app.route("/train-model", methods=["POST"])
def train_model_api():
    try:
        result = subprocess.run(
            [sys.executable, "train_drift_model.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        status = 200 if result.returncode == 0 else 500
        return jsonify({
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "model_status": _get_model_status(),
        }), status
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/model-status", methods=["GET"])
def model_status_api():
    records = load_interactions(limit=5000)
    return jsonify({
        "model_status": _get_model_status(),
        "label_stats": _build_label_stats(records),
    })


if __name__ == "__main__":
    app.run(debug=True, port=8000)
