import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INTERACTIONS_PATH = DATA_DIR / "interactions.jsonl"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_interaction(prompt, response, analysis, model=None, provider=None, label=None):
    _ensure_data_dir()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "response": response,
        "analysis": analysis,
        "model": model,
        "provider": provider,
    }
    if label is not None:
        record["label"] = label
    with open(INTERACTIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")
    return record


def load_interactions(limit=100):
    if not INTERACTIONS_PATH.exists():
        return []

    records = []
    with open(INTERACTIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit and limit > 0:
        records = records[-limit:]
    return records


def update_interaction_label(timestamp, label):
    if not INTERACTIONS_PATH.exists():
        return False

    updated = False
    records = []
    with open(INTERACTIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("timestamp") == timestamp:
                record["label"] = label
                updated = True
            records.append(record)

    if not updated:
        return False

    with open(INTERACTIONS_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
    return True
