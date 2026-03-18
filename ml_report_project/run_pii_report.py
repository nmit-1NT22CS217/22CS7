import argparse
import ast
import os
import sys
from collections import Counter, defaultdict

import pandas as pd


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip('"').strip("'")
    return " ".join(text.lower().split())


def load_gold_labels(raw_value):
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return []
    if isinstance(raw_value, dict):
        data = raw_value
    else:
        data = ast.literal_eval(str(raw_value))

    gold = []
    for label, items in data.items():
        if items is None:
            continue
        if isinstance(items, (list, tuple)):
            clean_items = [normalize_text(x) for x in items if normalize_text(x)]
            for item in clean_items:
                gold.append((item, label))
            if len(clean_items) > 1:
                joined = normalize_text(" ".join(clean_items))
                if joined:
                    gold.append((joined, label))
        else:
            item = normalize_text(items)
            if item:
                gold.append((item, label))
    return gold


def build_gold_maps(gold_list):
    gold_set = set()
    gold_labels_by_text = defaultdict(set)
    for text, label in gold_list:
        gold_set.add(text)
        gold_labels_by_text[text].add(label)
    return gold_set, gold_labels_by_text


def map_project_label(label: str) -> str | None:
    mapping = {
        "EMAIL": "EMAIL",
        "PHONE": "PHONE_NUM",
        "URL": "URL_PERSONAL",
        "PERSON_NAME": "NAME_STUDENT",
        "ADDRESS": "STREET_ADDRESS",
        "IP_ADDRESS": "ID_NUM",
        "ACCOUNT_ID": "ID_NUM",
        "SSN": "ID_NUM",
        "IBAN": "ID_NUM",
    }
    return mapping.get(label)


def map_presidio_label(label: str) -> str | None:
    mapping = {
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE_NUM",
        "URL": "URL_PERSONAL",
        "PERSON": "NAME_STUDENT",
        "USERNAME": "USERNAME",
        "LOCATION": "STREET_ADDRESS",
        "CREDIT_CARD": "ID_NUM",
        "US_SSN": "ID_NUM",
        "IP_ADDRESS": "ID_NUM",
    }
    return mapping.get(label)


def compute_metrics(rows):
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    precision = tp / (tp + fp + 1e-9)
    recall = tp / (tp + fn + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    return precision, recall, f1, tp, fp, fn


def macro_avg(df, metric_col):
    if df.empty:
        return 0.0
    return float(df[metric_col].mean())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data", "ai_data.csv"))
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "outputs"))
    parser.add_argument("--text-col", default="0")
    parser.add_argument("--label-col", default="1")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    plots_dir = os.path.join(args.out, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid")

    df = pd.read_csv(args.data)
    if args.text_col not in df.columns or args.label_col not in df.columns:
        raise ValueError(
            f"Columns not found. Available: {list(df.columns)}. "
            f"Got text-col={args.text_col}, label-col={args.label_col}."
        )

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, repo_root)

    from apps.api.anonymizer import PIIAnonymizer
    project_model = PIIAnonymizer()

    try:
        from presidio_analyzer import AnalyzerEngine
        presidio = AnalyzerEngine()
        presidio_available = True
    except Exception:
        presidio = None
        presidio_available = False

    per_row_detection = {"project": [], "presidio": []}
    per_row_classification = {"project": [], "presidio": []}
    per_label_counts = {
        "project": defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0}),
        "presidio": defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0}),
    }

    pred_type_counts = {"project": Counter(), "presidio": Counter()}
    gold_type_counts = Counter()

    sample_rows = []
    error_samples = {"project": [], "presidio": []}
    text_lengths = []
    gold_counts_per_text = []
    pred_counts_per_text = {"project": [], "presidio": []}

    for _, row in df.iterrows():
        text = str(row[args.text_col])
        text_lengths.append(len(text))
        gold = load_gold_labels(row[args.label_col])
        gold_set, gold_labels_by_text = build_gold_maps(gold)
        gold_counts_per_text.append(len(gold_set))
        for _, lbl in gold:
            gold_type_counts[lbl] += 1

        project_raw = project_model.detect_pii(text)
        project_preds = [(normalize_text(t), map_project_label(lbl), lbl) for t, lbl, _, _ in project_raw]
        project_preds = [(t, mapped, raw) for t, mapped, raw in project_preds if t]

        if presidio_available:
            presidio_raw = presidio.analyze(text=text, language="en")
            presidio_preds = [
                (normalize_text(text[r.start:r.end]), map_presidio_label(r.entity_type), r.entity_type)
                for r in presidio_raw
            ]
            presidio_preds = [(t, mapped, raw) for t, mapped, raw in presidio_preds if t]
        else:
            presidio_preds = []

        for t, mapped, raw in project_preds:
            pred_type_counts["project"][mapped or raw] += 1
        for t, mapped, raw in presidio_preds:
            pred_type_counts["presidio"][mapped or raw] += 1

        # Detection (text match)
        project_pred_texts = {t for t, _, _ in project_preds}
        presidio_pred_texts = {t for t, _, _ in presidio_preds}
        pred_counts_per_text["project"].append(len(project_pred_texts))
        pred_counts_per_text["presidio"].append(len(presidio_pred_texts))

        for name, pred_texts in [("project", project_pred_texts), ("presidio", presidio_pred_texts)]:
            tp = len(pred_texts & gold_set)
            fp = len(pred_texts - gold_set)
            fn = len(gold_set - pred_texts)
            per_row_detection[name].append({"tp": tp, "fp": fp, "fn": fn})

        # Classification (text + label match)
        for name, preds in [("project", project_preds), ("presidio", presidio_preds)]:
            tp = fp = fn = 0
            matched_gold = set()
            for t, mapped_label, _ in preds:
                if not mapped_label:
                    continue
                gold_labels = gold_labels_by_text.get(t, set())
                if mapped_label in gold_labels:
                    tp += 1
                    matched_gold.add((t, mapped_label))
                    per_label_counts[name][mapped_label]["tp"] += 1
                else:
                    fp += 1
                    per_label_counts[name][mapped_label]["fp"] += 1

            for t, labels in gold_labels_by_text.items():
                for label in labels:
                    if (t, label) not in matched_gold:
                        fn += 1
                        per_label_counts[name][label]["fn"] += 1
            per_row_classification[name].append({"tp": tp, "fp": fp, "fn": fn})

        if len(sample_rows) < 5:
            sample_rows.append(
                {
                    "text": text[:200],
                    "gold_labels": "; ".join(sorted({lbl for _, lbl in gold})),
                    "project_pred_types": "; ".join(sorted({mapped or raw for _, mapped, raw in project_preds})),
                    "presidio_pred_types": "; ".join(sorted({mapped or raw for _, mapped, raw in presidio_preds})),
                }
            )
        # Collect error samples for qualitative analysis
        for name, pred_texts in [("project", project_pred_texts), ("presidio", presidio_pred_texts)]:
            fp_texts = list(pred_texts - gold_set)[:3]
            fn_texts = list(gold_set - pred_texts)[:3]
            if fp_texts or fn_texts:
                if len(error_samples[name]) < 20:
                    error_samples[name].append(
                        {
                            "text_snippet": text[:200],
                            "false_positives": "; ".join(fp_texts),
                            "false_negatives": "; ".join(fn_texts),
                        }
                    )

    summary_rows = []
    for name in ["project", "presidio"]:
        p, r, f1, tp, fp, fn = compute_metrics(per_row_detection[name])
        summary_rows.append(
            {
                "model": name,
                "metric": "detection_text_match",
                "precision": p,
                "recall": r,
                "f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )
        p, r, f1, tp, fp, fn = compute_metrics(per_row_classification[name])
        summary_rows.append(
            {
                "model": name,
                "metric": "classification_text_and_type",
                "precision": p,
                "recall": r,
                "f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(os.path.join(args.out, "summary_metrics.csv"), index=False)
    summary_df.to_csv(os.path.join(args.out, "summary_metrics.csv"), index=False)

    per_label_rows = []
    for name in ["project", "presidio"]:
        for label, counts in per_label_counts[name].items():
            tp = counts["tp"]
            fp = counts["fp"]
            fn = counts["fn"]
            precision = tp / (tp + fp + 1e-9)
            recall = tp / (tp + fn + 1e-9)
            f1 = 2 * precision * recall / (precision + recall + 1e-9)
            per_label_rows.append(
                {
                    "model": name,
                    "label": label,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                }
            )

    per_label_df = pd.DataFrame(per_label_rows)
    per_label_df.to_csv(os.path.join(args.out, "per_label_metrics.csv"), index=False)

    macro_rows = []
    for name in ["project", "presidio"]:
        model_df = per_label_df[per_label_df["model"] == name]
        macro_rows.append(
            {
                "model": name,
                "metric": "macro_avg",
                "precision": macro_avg(model_df, "precision"),
                "recall": macro_avg(model_df, "recall"),
                "f1": macro_avg(model_df, "f1"),
            }
        )
    macro_df = pd.DataFrame(macro_rows)
    macro_df.to_csv(os.path.join(args.out, "macro_metrics.csv"), index=False)

    type_counts_df = pd.DataFrame(
        {
            "label": sorted(set(list(gold_type_counts.keys()) + list(pred_type_counts["project"].keys()) + list(pred_type_counts["presidio"].keys()))),
        }
    )
    type_counts_df["gold_count"] = type_counts_df["label"].map(gold_type_counts).fillna(0).astype(int)
    type_counts_df["project_pred_count"] = type_counts_df["label"].map(pred_type_counts["project"]).fillna(0).astype(int)
    type_counts_df["presidio_pred_count"] = type_counts_df["label"].map(pred_type_counts["presidio"]).fillna(0).astype(int)
    type_counts_df.to_csv(os.path.join(args.out, "type_counts.csv"), index=False)

    pd.DataFrame(sample_rows).to_csv(os.path.join(args.out, "sample_predictions.csv"), index=False)
    pd.DataFrame(error_samples["project"]).to_csv(os.path.join(args.out, "project_error_samples.csv"), index=False)
    pd.DataFrame(error_samples["presidio"]).to_csv(os.path.join(args.out, "presidio_error_samples.csv"), index=False)

    dataset_stats = pd.DataFrame(
        [
            {"stat": "num_rows", "value": len(df)},
            {"stat": "avg_text_length", "value": sum(text_lengths) / max(len(text_lengths), 1)},
            {"stat": "avg_gold_entities_per_text", "value": sum(gold_counts_per_text) / max(len(gold_counts_per_text), 1)},
            {"stat": "avg_project_entities_per_text", "value": sum(pred_counts_per_text["project"]) / max(len(pred_counts_per_text["project"]), 1)},
            {"stat": "avg_presidio_entities_per_text", "value": sum(pred_counts_per_text["presidio"]) / max(len(pred_counts_per_text["presidio"]), 1)},
        ]
    )
    dataset_stats.to_csv(os.path.join(args.out, "dataset_stats.csv"), index=False)

    # Plot: overall metrics
    plt.figure(figsize=(7, 4))
    plot_df = summary_df.copy()
    plot_df["model"] = plot_df["model"].str.title()
    sns.barplot(
        data=plot_df,
        x="metric",
        y="f1",
        hue="model",
    )
    plt.xticks(rotation=20, ha="right")
    plt.title("Overall F1 Comparison")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "overall_f1.png"), dpi=200)
    plt.close()

    # Plot: per-label F1
    if not per_label_df.empty:
        plt.figure(figsize=(9, 4.5))
        plot_df = per_label_df.copy()
        plot_df["model"] = plot_df["model"].str.title()
        sns.barplot(
            data=plot_df,
            x="label",
            y="f1",
            hue="model",
        )
        plt.xticks(rotation=30, ha="right")
        plt.title("Per-Label F1 (Text + Type Match)")
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, "per_label_f1.png"), dpi=200)
        plt.close()

    # Plot: label support counts
    plt.figure(figsize=(9, 4.5))
    plot_df = type_counts_df.copy()
    plot_df = plot_df.melt(id_vars=["label"], value_vars=["gold_count", "project_pred_count", "presidio_pred_count"],
                           var_name="source", value_name="count")
    sns.barplot(data=plot_df, x="label", y="count", hue="source")
    plt.xticks(rotation=30, ha="right")
    plt.title("PII Label Support (Gold vs Predictions)")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "label_support.png"), dpi=200)
    plt.close()

    # Plot: text length distribution
    plt.figure(figsize=(7, 4))
    sns.histplot(text_lengths, bins=20, kde=True)
    plt.title("Text Length Distribution")
    plt.xlabel("Characters")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "text_length_distribution.png"), dpi=200)
    plt.close()

    # Plot: entities per text
    plt.figure(figsize=(7, 4))
    sns.histplot(gold_counts_per_text, bins=15, color="black", label="gold", kde=False)
    sns.histplot(pred_counts_per_text["project"], bins=15, color="blue", label="project", kde=False, alpha=0.6)
    sns.histplot(pred_counts_per_text["presidio"], bins=15, color="orange", label="presidio", kde=False, alpha=0.6)
    plt.legend()
    plt.title("Entities per Text")
    plt.xlabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "entities_per_text.png"), dpi=200)
    plt.close()

    with open(os.path.join(args.out, "analysis.md"), "w", encoding="utf-8") as f:
        f.write("# PII Detection and Classification Report\n\n")
        f.write("## Summary Metrics\n\n")
        f.write(summary_df.to_markdown(index=False))
        f.write("\n\n")
        f.write("## Macro-Averaged Metrics\n\n")
        f.write(macro_df.to_markdown(index=False))
        f.write("\n\n")
        f.write("## Dataset Statistics\n\n")
        f.write(dataset_stats.to_markdown(index=False))
        f.write("\n\n")
        f.write("## Per-Label Metrics\n\n")
        if per_label_df.empty:
            f.write("No per-label metrics available.\n\n")
        else:
            f.write(per_label_df.to_markdown(index=False))
            f.write("\n\n")
        f.write("## Notes\n\n")
        f.write("- Detection uses exact text match after normalization (lowercased, whitespace normalized).\n")
        f.write("- Classification requires both text and mapped label to match the gold label.\n")
        if not presidio_available:
            f.write("- Presidio analyzer was not available; baseline predictions are empty.\n")


if __name__ == "__main__":
    main()
