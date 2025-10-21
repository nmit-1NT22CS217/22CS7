

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






# 🧠 Algorithms & Logic Overview

Your backend follows a structured **pipeline-based design**, where each step uses a specific algorithm or rule-based method to transform the text safely and intelligently.

---

## 1️⃣ **PII Detection Algorithm**

**📍 File:** `scripts/detect_pii.py`
**🎯 Purpose:** Identify personally identifiable information (PII) in user input text.

**⚙️ Technique Used:**

* **Regex-based pattern matching** for structured PII:

  * Emails → `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
  * Phones → `\+?\d[\d\s-]{7,}`
  * Credit Cards → `(?:\d[ -]*?){13,16}`
  * SSN → `\d{3}-\d{2}-\d{4}`
* **Keyword-based name detection** using capitalized word heuristics (for names/locations).
* Confidence scoring (0.0–1.0) assigned per detection type.

**🧩 Output:**
List of detected entities →
`[{ "type": "EMAIL", "value": "john.doe@example.com", "confidence": 0.98 }, ...]`

---

## 2️⃣ **Pseudonymization / Anonymization Algorithm**

**📍 File:** `scripts/anonymize.py`
**🎯 Purpose:** Replace all detected PII with unique pseudonyms like `PSEUDO_xxxxx`.

**⚙️ Technique Used:**

* **Hash-based pseudonym generation:**

  * Uses an MD5/SHA-like hash of each PII value (truncated for readability).
  * Each detection is replaced with `PSEUDO_<hash>`.
* Ensures **consistency** — the same PII always maps to the same pseudonym.
* Replacements are done using **non-overlapping regex substitution** to avoid conflicts.

**🧩 Example:**

```
Input: "My email is john.doe@example.com"
Output: "My email is PSEUDO_fb0b773de846"
```

---

## 3️⃣ **Pseudonym Mapping Algorithm**

**📍 File:** `scripts/pseudomap.py`
**🎯 Purpose:** Store and manage the mapping between original PII and pseudonyms.

**⚙️ Technique Used:**

* Generates a **run_id** for each analysis (timestamp-based unique ID).
* Creates a **key-value mapping**:

  ```json
  {
    "john.doe@example.com": "PSEUDO_fb0b773de846",
    "Jane Smith": "PSEUDO_76c7f44c8e62"
  }
  ```
* Stored as JSON under `outputs/<run_id>/map.json`.

**🧩 Use Case:** Required later for denormalization.

---

## 4️⃣ **LLM Invocation Logic**

**📍 File:** `scripts/llm_client.py`
**🎯 Purpose:** Send anonymized text to Gemini API (or mock mode) and fetch results.

**⚙️ Technique Used:**

* Uses **HTTP REST request** to Gemini endpoint:

  ```
  POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
  ```
* Payload follows **Google Generative Language Spec**:

  ```json
  { "contents": [{ "role": "user", "parts": [{ "text": "<anonymized_text>" }] }] }
  ```
* Implements:

  * **Retries with exponential backoff** (for 429, 5xx)
  * **Response parsing** for different formats (text or JSON)
  * **Code fence cleaning** (` ```json ... ``` ` removal)

**🧩 Output:**
Text response from Gemini model.

---

## 5️⃣ **Denormalization Algorithm**

**📍 File:** `scripts/denormalize.py`
**🎯 Purpose:** Replace pseudonyms in LLM output back with original sensitive data.

**⚙️ Technique Used:**

* Loads mapping file (`map.json`) from the current run.
* Iteratively scans the LLM text and replaces all `PSEUDO_xxx` keys with their real values.
* Backup is created before overwrite for safety.
* Handles multiple pseudonyms in large texts efficiently.

**🧩 Example:**

```
LLM Output: "Hello PSEUDO_161b33881db7!"
Restored: "Hello John Doe!"
```

---

## 6️⃣ **Validation Algorithm**

**📍 File:** `scripts/validation.py`
**🎯 Purpose:** Ensure that no PII remains in anonymized text and that denormalization was correct.

**⚙️ Technique Used:**

* Runs detection again on both anonymized and final outputs.
* Confirms:

  * No original PII remains in anonymized text ✅
  * All pseudonyms correctly replaced in denormalized output ✅
  * Checks consistency of counts and mapping integrity.
* Produces a **status report** (PASS / FAIL).

**🧩 Example Output:**

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

## 7️⃣ **Utility Functions**

**📍 File:** `scripts/utils.py`
**🎯 Purpose:** Support core algorithms with common tools.

**Includes:**

* `get_logger()` → Standardized colored logging
* `ensure_dir()` → Auto-create output folders
* `write_text_file()` / `write_json_file()` → Reliable file persistence

---

# 🧭 Summary Table

| Step | File           | Algorithm Type         | Goal                           |
| ---- | -------------- | ---------------------- | ------------------------------ |
| 1    | detect_pii.py  | Regex + Heuristics     | Find PII (email, phone, etc.)  |
| 2    | anonymize.py   | Hash-based Replacement | Mask sensitive data            |
| 3    | pseudomap.py   | Mapping Table          | Store pseudonym links          |
| 4    | llm_client.py  | REST API Request       | Send anonymized text to Gemini |
| 5    | denormalize.py | Reverse Mapping        | Restore original values        |
| 6    | validation.py  | Verification Checks    | Ensure data privacy integrity  |
| 7    | utils.py       | Helper Tools           | Logging & file ops             |

---




