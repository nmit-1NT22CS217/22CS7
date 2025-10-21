

# 🧠 System Overview — Algorithms & Data Flow

This backend follows a **secure text-processing pipeline** that detects and anonymizes sensitive user data before sending it to the LLM (Gemini API), then safely restores it afterward.

---

## ⚙️ Data Flow — Step by Step

Here’s how the backend flows internally 👇

```
┌──────────────────────────────────────────────────┐
│ User enters text with PII (in Web UI / API)      │
└──────────────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 1️⃣ detect_pii.py              │
│ Detects sensitive info using  │
│ regex & name heuristics.      │
│ → returns list of PII items.  │
└───────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 2️⃣ anonymize.py              │
│ Replaces each detected PII    │
│ with unique pseudonyms like   │
│ "PSEUDO_abc123".              │
└───────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 3️⃣ pseudomap.py              │
│ Stores the original ↔ pseudo  │
│ mapping as a JSON file under  │
│ outputs/<run_id>/map.json.    │
└───────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 4️⃣ llm_client.py             │
│ Sends the anonymized text to  │
│ Gemini via REST API request.  │
│ → Receives response (JSON or  │
│ text) with pseudonyms inside. │
└───────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 5️⃣ denormalize.py            │
│ Replaces pseudonyms back to   │
│ original data using mapping.  │
└───────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────┐
│ 6️⃣ validation.py             │
│ Runs checks to ensure:        │
│ - No PII left in anonymized   │
│ - All pseudonyms resolved     │
│ → Returns PASS / FAIL report. │
└───────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Final Report generated in outputs/<run_id>/       │
│  - anonymized.txt                                 │
│  - llm_raw_with_pseudos.txt                       │
│  - llm_denormalized.txt                           │
│  - final_report.json                              │
└──────────────────────────────────────────────────┘
```

---

## 🧩 Algorithm Summary

| Step                    | File             | Technique                        | Purpose                                                            |
| ----------------------- | ---------------- | -------------------------------- | ------------------------------------------------------------------ |
| **1️⃣ PII Detection**   | `detect_pii.py`  | Regex & pattern matching         | Finds sensitive entities like name, email, phone, credit card, SSN |
| **2️⃣ Anonymization**   | `anonymize.py`   | Hash-based pseudonym replacement | Masks PII using unique pseudonyms (`PSEUDO_xxx`)                   |
| **3️⃣ Pseudomap**       | `pseudomap.py`   | Key–value mapping (JSON)         | Stores mapping between real data ↔ pseudonym                       |
| **4️⃣ LLM Client**      | `llm_client.py`  | REST API + Retry with backoff    | Sends anonymized text to Gemini, fetches output                    |
| **5️⃣ Denormalization** | `denormalize.py` | Reverse mapping                  | Replaces pseudonyms back to real values                            |
| **6️⃣ Validation**      | `validation.py`  | Double-pass PII check            | Ensures privacy integrity & correctness                            |
| **7️⃣ Utilities**       | `utils.py`       | Logging, I/O, safety wrappers    | Common helpers used across all modules                             |

---

## 🧮 Key Algorithms Explained

### 🔍 1. PII Detection

* Uses **regex patterns** to detect common PII (emails, phones, SSNs, credit cards).
* Uses **heuristics** for unstructured PII (names, addresses).
* Each detection tagged with:

  ```json
  {"type": "EMAIL", "value": "john.doe@example.com", "confidence": 0.98}
  ```

---

### 🔒 2. Pseudonymization

* For every detected PII, generates a **consistent pseudonym** like:

  ```
  PSEUDO_<hash_of_value>
  ```
* Example:

  ```
  Input: "My email is john.doe@example.com"
  Output: "My email is PSEUDO_fb0b773de846"
  ```

---

### 🧭 3. Pseudomap

* Maintains an internal JSON mapping between real and pseudo values:

  ```json
  {
    "john.doe@example.com": "PSEUDO_fb0b773de846",
    "Jane Smith": "PSEUDO_76c7f44c8e62"
  }
  ```
* This mapping is later used for **accurate denormalization**.

---

### 🧠 4. LLM Client (Gemini)

* Sends **only anonymized text** to Google Gemini API.
* Uses **standard REST payload format**:

  ```json
  {
    "contents": [{ "role": "user", "parts": [{ "text": "<anonymized_text>" }] }]
  }
  ```
* Handles:

  * Retries on 429 / 5xx with exponential backoff
  * Cleans JSON fences
  * Extracts text safely from multiple response formats

---

### 🔁 5. Denormalization

* Reads mapping file (`map.json`) and restores pseudonyms back to originals.
* Example:

  ```
  LLM Output: "Hello PSEUDO_161b33881db7!"
  Final Output: "Hello John Doe!"
  ```
* Ensures **zero loss** and **perfect restoration** of context.

---

### ✅ 6. Validation

* Runs post-processing checks to confirm:

  * Anonymized text → contains **no original PII**
  * Denormalized output → **matches mapping** accurately
* Produces a validation report:

  ```json
  {
    "overall_status": "PASS",
    "checks": {
      "no_pii_leak": true,
      "all_pseudonyms_resolved": true
    }
  }
  ```

---

## 📊 Output Files (Generated per Run)

Each run creates a folder under `outputs/<run_id>/` containing:

| File                       | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `anonymized.txt`           | Text after anonymization                             |
| `llm_raw_with_pseudos.txt` | Gemini’s response (still has pseudonyms)             |
| `llm_denormalized.txt`     | Final restored output                                |
| `final_report.json`        | Structured summary (detections, mapping, validation) |
| `map.json`                 | Pseudonym ↔ Original mapping                         |

---

## 🧩 Summary

This backend ensures **privacy-preserving AI processing** by:

* Detecting sensitive data 🔍
* Masking it before LLM processing 🔒
* Replacing it back safely afterward 🔁
* Verifying no privacy breaches occurred ✅

It’s designed to be **modular**, **traceable**, and **compliant-ready** — making it ideal for any enterprise-level or research-grade data processing workflow.

