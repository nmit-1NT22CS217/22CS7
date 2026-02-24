import argparse
import json
import urllib.parse
import urllib.request

from analysis_engine import analyze_response
from data_store import append_interaction, load_interactions

DATASET = "danthareja/cognitive-distortion"
CONFIG = "default"
SPLIT = "train"
PAGE = 100
NO_DISTORTION_INDEX = 2


def fetch_rows(offset, length):
    params = urllib.parse.urlencode(
        {
            "dataset": DATASET,
            "config": CONFIG,
            "split": SPLIT,
            "offset": offset,
            "length": length,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{params}"
    payload = json.loads(urllib.request.urlopen(url, timeout=60).read().decode())
    return payload


def parse_args():
    parser = argparse.ArgumentParser(description="Import dedicated cognitive distortion dataset")
    parser.add_argument("--max-rows", type=int, default=2024)
    return parser.parse_args()


def main():
    args = parse_args()

    existing = load_interactions(limit=400000)
    seen = set()
    for record in existing:
        if record.get("provider") == "huggingface" and record.get("model") == "cognitive-distortion-hf":
            text = (record.get("response") or "").strip()
            if text:
                seen.add(text)

    offset = 0
    imported = 0
    total_target = max(1, args.max_rows)

    while imported < total_target:
        remaining = total_target - imported
        length = PAGE if remaining > PAGE else remaining
        payload = fetch_rows(offset, length)
        rows = payload.get("rows", [])
        if not rows:
            break

        for item in rows:
            row = item.get("row", {})
            text = (row.get(" patient_question") or "").strip()
            label_idx = row.get("dominant_distortion")
            if not text or text in seen:
                continue
            if not isinstance(label_idx, int):
                continue

            label = "safe" if label_idx == NO_DISTORTION_INDEX else "drift"
            analysis = analyze_response(text)
            append_interaction(
                prompt="[EXTERNAL DATASET] Cognitive Distortion sample",
                response=text,
                analysis=analysis,
                model="cognitive-distortion-hf",
                provider="huggingface",
                label=label,
            )
            seen.add(text)
            imported += 1

            if imported % 25 == 0:
                print(f"Imported {imported} dedicated samples...")
            if imported >= total_target:
                break

        offset += len(rows)
        if len(rows) < length:
            break

    print(f"Done. Imported {imported} dedicated samples.")


if __name__ == "__main__":
    main()
