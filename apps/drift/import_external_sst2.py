import argparse
import random
import urllib.request

from analysis_engine import analyze_response
from data_store import append_interaction, load_interactions

SST2_URLS = [
    "https://raw.githubusercontent.com/clairett/pytorch-sentiment-classification/master/data/SST2/train.tsv",
    "https://raw.githubusercontent.com/clairett/pytorch-sentiment-classification/master/data/SST2/dev.tsv",
]
MAX_PER_CLASS = 80
RANDOM_SEED = 42


def download_sst2_lines(urls):
    rows = []
    for url in urls:
        raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", errors="ignore")
        for line in raw.splitlines():
            line = line.strip()
            if not line or "\t" not in line:
                continue
            text, label = line.rsplit("\t", 1)
            label = label.strip()
            if label not in {"0", "1"}:
                continue
            rows.append((text.strip(), int(label)))
    return rows


def parse_args():
    parser = argparse.ArgumentParser(description="Import external SST2 samples for drift training.")
    parser.add_argument("--per-class", type=int, default=MAX_PER_CLASS, help="Max samples per class to import")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(RANDOM_SEED)

    existing = load_interactions(limit=200000)
    existing_texts = set()
    for record in existing:
        if record.get("provider") == "github" and record.get("model") == "sst2-bootstrap":
            txt = (record.get("response") or "").strip()
            if txt:
                existing_texts.add(txt)

    rows = download_sst2_lines(SST2_URLS)
    negatives = [t for t, y in rows if y == 0 and t not in existing_texts]
    positives = [t for t, y in rows if y == 1 and t not in existing_texts]

    random.shuffle(negatives)
    random.shuffle(positives)

    negatives = negatives[:args.per_class]
    positives = positives[:args.per_class]

    imported = 0
    for text, label in [(t, "drift") for t in negatives] + [(t, "safe") for t in positives]:
        analysis = analyze_response(text)
        append_interaction(
            prompt="[EXTERNAL DATASET] SST2 sentiment sample",
            response=text,
            analysis=analysis,
            model="sst2-bootstrap",
            provider="github",
            label=label,
        )
        imported += 1
        if imported % 20 == 0:
            print(f"Imported {imported} samples...")

    print(f"Done. Imported {imported} samples from external dataset sources.")


if __name__ == "__main__":
    main()
