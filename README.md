

# ⚙️ Steps to Run the Backend

Follow these steps to set up and run the backend on your local machine 👇

---

### 🧩 1️⃣ Clone the Repository

```bash
git clone git@github.com:nmit-1NT22CS217/22CS7.git
cd 22CS7
```

---

### 🧱 2️⃣ Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment:

**Windows:**

```bash
venv\Scripts\activate
```

**Mac/Linux:**

```bash
source venv/bin/activate
```

---

### 📦 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, install manually:

```bash
pip install flask flask-cors requests python-dotenv
```

---

### 🔑 4️⃣ Set Up Environment Variables

Create a `.env` file in the project root directory and add your Gemini API details:

```bash
LLM_API_KEY=YOUR_GEMINI_API_KEY
LLM_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
LLM_MODEL=gemini-2.5-flash
LLM_MOCK_MODE=false
LLM_TIMEOUT_SEC=60
```

> ⚠️ Replace `YOUR_GEMINI_API_KEY` with your real API key from [Google AI Studio](https://aistudio.google.com).

---

### ▶️ 5️⃣ Run the Backend

```bash
python app.py
```

You should see something like:

```
🌐 Starting Flask backend at http://127.0.0.1:5000
```

---

### 🌐 6️⃣ Open the Web UI

Open your browser and go to:

👉 [http://127.0.0.1:5000](http://127.0.0.1:5000)

You’ll see a **modern dark interface** where you can:

* Paste any text containing PII (e.g., name, email, credit card)
* Click **Run Analysis**
* View:

  * Detected Entities
  * Anonymized Text
  * LLM Raw Output (with pseudonyms)
  * LLM Denormalized Output (restored text)

---

### 🧾 7️⃣ View Results

Every run generates a report in:

```
outputs/<run_id>/
```

Each folder contains:

* `anonymized.txt`
* `llm_raw_with_pseudos.txt`
* `llm_denormalized.txt`
* `final_report.json`

---

### ✅ 8️⃣ (Optional) Run Self-Test

To confirm everything works:

```bash
python scripts/llm_workflow.py
```

---

That’s it 🎉
Your backend is now live and fully functional — ready to detect, anonymize, analyze, and denormalize!

