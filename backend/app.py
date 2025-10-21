from __future__ import annotations
"""
app.py — Flask backend for PII Detection → LLM → Denormalization pipeline
Apple-dark + Google Material inspired clean UI.
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

# ---------------------------------------------------------------------
# Core imports
# ---------------------------------------------------------------------
from scripts.llm_workflow import process_text_with_llm
from scripts.utils import ensure_dir, get_logger, write_json_file
from scripts.validation import run_validation

# ---------------------------------------------------------------------
# Flask configuration
# ---------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
logger = get_logger("backend_ui")

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
ensure_dir(OUTPUT_DIR)


# ---------------------------------------------------------------------
# Apple + Google UI Design
# ---------------------------------------------------------------------
@app.route("/")
def index():
    """Serve a polished, modern dark-mode UI."""
    return """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>LLM Anonymization Gateway</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      :root { color-scheme: dark; }
      body {
        font-family: 'SF Pro Display', 'Inter', sans-serif;
        background-color: #0d1117;
        color: #e5e7eb;
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 960px;
        margin: 60px auto;
        padding: 0 24px;
      }
      textarea {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        color: #f9fafb;
        font-size: 15px;
        width: 100%;
        resize: vertical;
        padding: 14px;
        transition: all 0.2s;
      }
      textarea:focus {
        outline: none;
        border-color: #58a6ff;
        box-shadow: 0 0 0 3px rgba(56, 139, 253, 0.3);
      }
      .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      }
      .badge {
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        color: #fff;
      }
      .tab-active {
        background: #1f6feb;
        color: white;
        box-shadow: 0 2px 6px rgba(31, 111, 235, 0.4);
      }
      .tab-inactive {
        background: #21262d;
        color: #8b949e;
      }
      button { transition: all 0.2s; }
      button:active { transform: scale(0.97); }
      .divider {
        height: 1px;
        background: #2f3439;
        margin: 32px 0;
      }
      pre {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px;
        font-size: 14px;
        white-space: pre-wrap;
        color: #d1d5db;
      }
    </style>
  </head>

  <body>
    <div class="container">
      <h1 class="text-3xl font-semibold mb-6 text-gray-100">LLM Gateway</h1>
      <p class="text-gray-400 mb-8">Analyze sensitive text securely using anonymization and validation pipeline.</p>

      <!-- Tabs -->
      <div class="flex space-x-2 mb-6">
        <button id="tab-analyze" class="tab-active px-5 py-2 rounded-md font-medium">Analyze</button>
        <button id="tab-history" class="tab-inactive px-5 py-2 rounded-md font-medium">History</button>
      </div>

      <!-- Analyze Tab -->
      <div id="analyze-tab" class="block">
        <textarea id="inputText" rows="6" placeholder="Enter text containing PII (e.g., name, email, credit card)..." class="mb-4"></textarea>
        <button id="analyzeBtn" class="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-md font-medium">Run Analysis</button>
        <p id="loading" class="hidden text-gray-400 mt-3">Analyzing... please wait</p>

        <div id="results" class="hidden mt-10">
          <h2 class="text-2xl font-semibold mb-3 text-gray-200">Results</h2>
          <div id="summary" class="card mb-5"></div>

          <div class="divider"></div>

          <h3 class="text-lg mb-2 text-gray-300">Detected Entities</h3>
          <div id="detections" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6"></div>

          <div class="divider"></div>

          <h3 class="text-lg mb-2 text-gray-300">Anonymized Output</h3>
          <pre id="anonymized" class="mb-6"></pre>

          <!-- 🆕 NEW BLOCK: Raw LLM Output -->
          <h3 class="text-lg mb-2 text-gray-300">LLM Raw Output (with Pseudonyms)</h3>
          <pre id="llmRaw" class="mb-6"></pre> <!-- 🆕 -->

          <!-- 🆕 EXISTING BLOCK stays below -->
          <h3 class="text-lg mb-2 text-gray-300">LLM Denormalized Output</h3>
          <pre id="denormalized"></pre>
        </div>
      </div>

      <!-- History Tab -->
      <div id="history-tab" class="hidden">
        <h2 class="text-2xl font-semibold mb-4 text-gray-200">Past Analyses</h2>
        <div id="reportsList" class="space-y-3"></div>
      </div>
    </div>

    <script>
      // Tabs
      const tabAnalyze = document.getElementById('tab-analyze');
      const tabHistory = document.getElementById('tab-history');
      const analyzeTab = document.getElementById('analyze-tab');
      const historyTab = document.getElementById('history-tab');

      tabAnalyze.onclick = () => {
        tabAnalyze.classList.replace('tab-inactive', 'tab-active');
        tabHistory.classList.replace('tab-active', 'tab-inactive');
        analyzeTab.classList.remove('hidden');
        historyTab.classList.add('hidden');
      };

      tabHistory.onclick = async () => {
        tabAnalyze.classList.replace('tab-active', 'tab-inactive');
        tabHistory.classList.replace('tab-inactive', 'tab-active');
        analyzeTab.classList.add('hidden');
        historyTab.classList.remove('hidden');
        await loadReports();
      };

      // Analysis Workflow
      const btn = document.getElementById('analyzeBtn');
      const input = document.getElementById('inputText');
      const loading = document.getElementById('loading');
      const results = document.getElementById('results');
      const summary = document.getElementById('summary');
      const detectionsDiv = document.getElementById('detections');
      const anonymized = document.getElementById('anonymized');
      const denormalized = document.getElementById('denormalized');
      const llmRaw = document.getElementById('llmRaw'); // 🆕 added element

      btn.onclick = async () => {
        const text = input.value.trim();
        if (!text) { alert('Please enter some text'); return; }

        results.classList.add('hidden');
        loading.classList.remove('hidden');

        try {
          const resp = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
          });
          const data = await resp.json();
          loading.classList.add('hidden');

          if (!data.ok) {
            alert('Error: ' + (data.error || 'Unknown error'));
            return;
          }

          // Summary
          results.classList.remove('hidden');
          summary.innerHTML = `
            <div class="flex justify-between items-center">
              <div>
                <div><span class="font-medium text-gray-300">Run ID:</span> ${data.run_id}</div>
                <div><span class="font-medium text-gray-300">Status:</span> ${data.validation?.overall_status || 'Pending'}</div>
              </div>
              <div class="text-blue-400 font-semibold">
                Detected: ${data.detections?.length || 0} items
              </div>
            </div>
          `;

          // Detections
          detectionsDiv.innerHTML = '';
          (data.detections || []).forEach(det => {
            const color = det.type === 'EMAIL' ? 'bg-blue-500' :
                          det.type === 'PHONE' ? 'bg-green-500' :
                          det.type === 'CREDIT_CARD' ? 'bg-red-500' :
                          det.type === 'IP_ADDRESS' ? 'bg-yellow-500' :
                          det.type === 'NAME' ? 'bg-purple-500' : 'bg-gray-600';
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `
              <div class="badge ${color}">${det.type}</div>
              <div class="text-sm mt-2 text-gray-300">${det.value}</div>
              <div class="text-xs text-gray-500 mt-1">Confidence: ${(det.confidence || 0).toFixed(2)}</div>
            `;
            detectionsDiv.appendChild(el);
          });

          anonymized.textContent = data.anonymized_text || 'No output';
          llmRaw.textContent = data.llm_text || 'No output'; // 🆕 show raw pseudonym output
          denormalized.textContent = data.llm_denormalized || 'No output';

        } catch (err) {
          loading.classList.add('hidden');
          alert('Error: ' + err.message);
        }
      };

      async function loadReports() {
        const list = document.getElementById('reportsList');
        list.innerHTML = '<p class="text-gray-500">Loading reports...</p>';
        const resp = await fetch('/api/reports');
        const data = await resp.json();
        list.innerHTML = '';
        (data.reports || []).forEach(r => {
          const color = r.status.includes('PASS') ? 'text-green-400' : 'text-red-400';
          list.innerHTML += `
            <div class="card flex justify-between items-center">
              <div>
                <div class="font-medium text-gray-200">${r.run_id}</div>
                <div class="text-sm text-gray-500">${r.pii_found} PII items detected</div>
              </div>
              <div class="${color} font-bold">${r.status}</div>
            </div>
          `;
        });
      }
    </script>
  </body>
</html>
    """


# ---------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------
@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Run full anonymization → LLM → denormalization pipeline."""
    try:
        data = request.get_json(force=True)
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "Empty text input"}), 400

        result = process_text_with_llm(text=text)
        if not result.get("ok"):
            return jsonify({"ok": False, "error": result.get("error")}), 500

        # 🆕 Ensure validation & both outputs are included
        validation = run_validation(result["run_id"], result["anonymized_text"], result["llm_denormalized"])
        result["validation"] = validation

        # 🆕 Return both anonymized and raw+denormalized LLM outputs
        run_dir = os.path.join(OUTPUT_DIR, result["run_id"])
        ensure_dir(run_dir)
        write_json_file(result, os.path.join(run_dir, "final_report.json"))
        return jsonify({
            "ok": True,
            "run_id": result["run_id"],
            "detections": result["detections"],
            "anonymized_text": result["anonymized_text"],
            "llm_text": result.get("llm_text", ""),  # 🆕 raw LLM output (with pseudos)
            "llm_denormalized": result.get("llm_denormalized", ""),  # 🆕 final restored output
            "validation": result["validation"],
        }), 200

    except Exception as e:
        logger.exception("❌ Error in /api/analyze")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """List previous runs."""
    reports = []
    for folder in sorted(os.listdir(OUTPUT_DIR)):
        path = os.path.join(OUTPUT_DIR, folder, "final_report.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
            reports.append({
                "run_id": folder,
                "status": report.get("validation", {}).get("overall_status", "UNKNOWN"),
                "pii_found": len(report.get("detections", []))
            })
    return jsonify({"ok": True, "reports": reports})


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🌐 Starting Flask backend at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
