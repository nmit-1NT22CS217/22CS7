"""
backend/app.py

Flask Application – AI-Driven PII Security Gateway

Single entry point for:
- User input
- AI security pipeline
- Role-aware responses
"""

import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

# 🔑 AI Orchestrator (single source of truth)
from core.anonymizer import process_prompt

# 🔐 Storage utilities
from core.storage import clear_store

# -------------------------------------------------
# INIT
# -------------------------------------------------

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)

# -------------------------------------------------
# SECURITY / CONFIG
# -------------------------------------------------

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24))

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    CORS(app, origins=[o.strip() for o in allowed_origins_env.split(",") if o.strip()])
else:
    # Dev-friendly default (lock down in production)
    CORS(app)

# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# =================================================
# MAIN API ENDPOINT
# =================================================
@app.route("/api/anonymize", methods=["POST"])
def anonymize():
    """
    Unified AI-driven anonymization endpoint.

    Request JSON:
    {
        "text": "...",
        "mode": "pseudonymize|mask|replace",
        "role": "user|admin",
        "call_llm": true
    }
    """
    try:
        data = request.get_json(force=True)

        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Text is required"}), 400

        role = data.get("role", "user")
        mode = data.get("mode", "pseudonymize")
        call_llm = bool(data.get("call_llm", True))

        # 🔑 PIPELINE ENTRY (STRUCTURED RESPONSE)
        result = process_prompt(
            text=text,
            role=role,
            mode=mode,
            call_llm=call_llm
        )

        # 🔒 Defensive validation (prevents UI crashes)
        if not isinstance(result, dict):
            raise ValueError("AI pipeline returned invalid response format")

        return jsonify({
            # 🔹 anonymized user input (before LLM)
            "anonymized_text": result.get("anonymized_text"),

            # 🔹 LLM response (already safe)
            "llm_response_anonymized": result.get("llm_response"),

            # 🔹 admin-only deanonymized output
            "deanonymized_output": result.get("deanonymized_text"),

            # 🔹 real mapping count from pipeline
            "mappings_count": result.get("mappings_count", 0),

            "role": role,
            "mode": mode,
            "ai_pipeline": "enabled"
        })

    except Exception as e:
        # Log full error server-side
        print("❌ /api/anonymize error:", str(e))

        return jsonify({
            "error": "Server error during anonymization",
            "details": str(e)
        }), 500


# =================================================
# MAINTENANCE ENDPOINTS
# =================================================

@app.route("/api/clear-mappings", methods=["POST"])
def clear_mappings():
    clear_store()
    return jsonify({"message": "All mappings cleared"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "AI-Driven PII Security Gateway",
        "llm_mode": "mock" if not os.getenv("GROQ_API_KEY") else "api",
        "version": "3.1.0"
    })


# =================================================
# DEV ENTRY POINT
# =================================================
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", 5000))

    print("🚀 Starting AI-Driven PII Gateway")
    print(f"   Debug: {debug}")
    print(f"   Port: {port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
