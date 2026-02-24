import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import torch
from scipy.spatial.distance import jensenshannon
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity, rbf_kernel
from transformers import AutoModel, AutoTokenizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

MODEL_NAME_FALLBACK = "distilbert-base-uncased"
MODEL_NAME_ST = "all-MiniLM-L6-v2"
BASE_DIR = Path(__file__).resolve().parent
BASELINE_PATH = BASE_DIR / "baseline.txt"
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "drift_model.joblib"
DATA_DIR = BASE_DIR / "data"
HISTORY_CACHE_PATH = DATA_DIR / "history_cache.json"
EPS = 1e-12
MAX_RECENT_EMBEDDINGS = 80
MAX_RECENT_PROJECTIONS = 200

FEATURE_KEYS = [
    "semantic_drift",
    "sentiment_drift",
    "lexical_drift",
    "js_divergence",
    "mmd_drift",
    "mmd_pvalue_inv",
    "historical_drift",
    "domain_auc_shift",
    "anomaly_score",
    "trend_shift",
    "ewma_score",
    "page_hinkley_score",
    "volatility_risk",
]

sentiment_analyzer = SentimentIntensityAnalyzer()

if SENTENCE_TRANSFORMERS_AVAILABLE:
    st_model = SentenceTransformer(MODEL_NAME_ST)
    tokenizer = None
    model = None
else:
    st_model = None
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME_FALLBACK)
    model = AutoModel.from_pretrained(MODEL_NAME_FALLBACK)
    model.eval()


def _safe_text(text):
    text = (text or "").strip()
    return text if text else "No content."


def _clip01(x):
    return float(np.clip(x, 0.0, 1.0))


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def get_embedding(text):
    text = _safe_text(text)

    if SENTENCE_TRANSFORMERS_AVAILABLE and st_model is not None:
        return st_model.encode(text, convert_to_numpy=True, normalize_embeddings=True)

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256,
    )
    with torch.no_grad():
        outputs = model(**inputs)
    embedding = outputs.last_hidden_state.mean(dim=1).numpy()[0]
    norm = np.linalg.norm(embedding) + EPS
    return embedding / norm


def _load_baseline_text():
    if not BASELINE_PATH.exists():
        return "Balanced and neutral reasoning with acknowledged uncertainty."
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content or "Balanced and neutral reasoning with acknowledged uncertainty."


def compute_js_divergence(vec1, vec2):
    vec1 = np.abs(vec1) + EPS
    vec2 = np.abs(vec2) + EPS
    vec1 = vec1 / (np.sum(vec1) + EPS)
    vec2 = vec2 / (np.sum(vec2) + EPS)
    return float(jensenshannon(vec1, vec2))


def _rbf_gamma_from_median(data):
    dists = np.sum((data[:, None, :] - data[None, :, :]) ** 2, axis=2)
    positive = dists[dists > 0]
    if positive.size == 0:
        return 1.0
    return 1.0 / (2.0 * np.median(positive) + EPS)


def _mmd2_rbf(x, y, gamma):
    k_xx = rbf_kernel(x, x, gamma=gamma)
    k_yy = rbf_kernel(y, y, gamma=gamma)
    k_xy = rbf_kernel(x, y, gamma=gamma)
    return float(np.mean(k_xx) + np.mean(k_yy) - 2.0 * np.mean(k_xy))


def compute_mmd_with_pvalue(x, y, permutations=48):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    if y.ndim == 1:
        y = y.reshape(1, -1)

    if len(x) < 2 or len(y) < 2:
        return 0.0, 1.0

    all_data = np.vstack([x, y])
    gamma = _rbf_gamma_from_median(all_data)
    observed = max(0.0, _mmd2_rbf(x, y, gamma))

    n_x = len(x)
    count_ge = 0
    for _ in range(permutations):
        perm = np.random.permutation(len(all_data))
        x_p = all_data[perm[:n_x]]
        y_p = all_data[perm[n_x:]]
        stat = max(0.0, _mmd2_rbf(x_p, y_p, gamma))
        if stat >= observed:
            count_ge += 1
    pvalue = (count_ge + 1.0) / (permutations + 1.0)
    return float(np.sqrt(observed)), float(pvalue)


def compute_ewma(series, alpha=0.3):
    if not series:
        return 0.0
    value = float(series[0])
    for v in series[1:]:
        value = alpha * float(v) + (1.0 - alpha) * value
    return value


def compute_page_hinkley(series, delta=0.005, threshold=0.08):
    if not series:
        return 0.0, False
    mean = 0.0
    cum_sum = 0.0
    min_cum_sum = 0.0
    score = 0.0
    for i, x in enumerate(series, start=1):
        x = float(x)
        mean += (x - mean) / i
        cum_sum += x - mean - delta
        min_cum_sum = min(min_cum_sum, cum_sum)
        score = max(score, cum_sum - min_cum_sum)
    normalized = _clip01(score / threshold)
    return float(normalized), bool(score > threshold)


def compute_domain_auc_shift(reference_embeddings, current_embeddings):
    ref = np.asarray(reference_embeddings, dtype=float)
    cur = np.asarray(current_embeddings, dtype=float)
    if ref.ndim == 1:
        ref = ref.reshape(1, -1)
    if cur.ndim == 1:
        cur = cur.reshape(1, -1)

    if len(ref) < 6 or len(cur) < 6:
        return 0.0

    x = np.vstack([ref, cur])
    y = np.array([0] * len(ref) + [1] * len(cur), dtype=int)

    perm = np.random.permutation(len(x))
    x = x[perm]
    y = y[perm]

    split = int(0.7 * len(x))
    x_train, x_test = x[:split], x[split:]
    y_train, y_test = y[:split], y[split:]

    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        return 0.0

    clf = LogisticRegression(max_iter=600, class_weight="balanced")
    clf.fit(x_train, y_train)
    proba = clf.predict_proba(x_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    return _clip01(abs(float(auc) - 0.5) * 2.0)


def _text_profile(text):
    clean = _safe_text(text)
    words = [w for w in clean.split() if w.strip()]
    chars = [c for c in clean if not c.isspace()]
    unique_words = len(set(w.lower() for w in words))
    type_token_ratio = unique_words / (len(words) + EPS)
    avg_word_len = float(np.mean([len(w) for w in words])) if words else 0.0
    punctuation_ratio = sum(1 for c in chars if c in ".,;:!?-()[]{}\"'") / (len(chars) + EPS)
    return {
        "word_count": len(words),
        "type_token_ratio": type_token_ratio,
        "avg_word_len": avg_word_len,
        "punctuation_ratio": punctuation_ratio,
    }


baseline_text = _load_baseline_text()
baseline_sentiment = sentiment_analyzer.polarity_scores(baseline_text)["compound"]

baseline_variants = [
    baseline_text,
    baseline_text + " It avoids extreme claims.",
    baseline_text + " It presents both risks and benefits.",
    baseline_text + " It acknowledges uncertainty.",
    baseline_text + " It keeps language measured and evidence-oriented.",
]
baseline_embeddings = np.array([get_embedding(t) for t in baseline_variants])
baseline_center = np.mean(baseline_embeddings, axis=0)
baseline_center = baseline_center / (np.linalg.norm(baseline_center) + EPS)

baseline_projection = np.dot(baseline_embeddings, baseline_center)
baseline_js_reference = np.mean(baseline_embeddings, axis=0)
baseline_profile = _text_profile(baseline_text)

iso_forest = IsolationForest(contamination=0.1, random_state=42)
iso_forest.fit(baseline_embeddings)


def _load_model_pack():
    if not MODEL_PATH.exists():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


MODEL_PACK = _load_model_pack()


def _default_history_cache():
    return {
        "count": 0,
        "mean_embedding": None,
        "recent_embeddings": [],
        "recent_projections": [],
        "updated_at": None,
    }


def load_history_cache():
    if not HISTORY_CACHE_PATH.exists():
        return _default_history_cache()
    try:
        with open(HISTORY_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if not isinstance(cache, dict):
            return _default_history_cache()
        return {
            "count": int(cache.get("count", 0)),
            "mean_embedding": cache.get("mean_embedding"),
            "recent_embeddings": list(cache.get("recent_embeddings", [])),
            "recent_projections": list(cache.get("recent_projections", [])),
            "updated_at": cache.get("updated_at"),
        }
    except Exception:
        return _default_history_cache()


def _save_history_cache(cache):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=True)


def update_history_cache(text):
    cache = load_history_cache()
    embedding = get_embedding(text)

    count = int(cache.get("count", 0))
    mean_embedding = cache.get("mean_embedding")
    if mean_embedding is None:
        new_mean = embedding
    else:
        prev_mean = np.array(mean_embedding, dtype=float)
        new_mean = ((count * prev_mean) + embedding) / (count + 1.0)

    projection = float(np.dot(embedding, baseline_center))

    recent_embeddings = list(cache.get("recent_embeddings", []))
    recent_embeddings.append(embedding.tolist())
    recent_embeddings = recent_embeddings[-MAX_RECENT_EMBEDDINGS:]

    recent_projections = list(cache.get("recent_projections", []))
    recent_projections.append(projection)
    recent_projections = recent_projections[-MAX_RECENT_PROJECTIONS:]

    new_cache = {
        "count": count + 1,
        "mean_embedding": new_mean.tolist(),
        "recent_embeddings": recent_embeddings,
        "recent_projections": recent_projections,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_history_cache(new_cache)
    return new_cache


def _compute_rule_risk(feature_map):
    # Logistic risk function over statistically-grounded detector outputs.
    z = (
        -2.2
        + 2.8 * feature_map["semantic_drift"]
        + 1.1 * feature_map["sentiment_drift"]
        + 0.7 * feature_map["lexical_drift"]
        + 1.3 * feature_map["js_divergence"]
        + 1.9 * feature_map["mmd_drift"]
        + 1.2 * feature_map["mmd_pvalue_inv"]
        + 1.5 * feature_map["historical_drift"]
        + 1.9 * feature_map["domain_auc_shift"]
        + 1.8 * feature_map["anomaly_score"]
        + 1.2 * feature_map["trend_shift"]
        + 1.0 * feature_map["ewma_score"]
        + 1.5 * feature_map["page_hinkley_score"]
        + 1.1 * feature_map["volatility_risk"]
    )
    return _clip01(_sigmoid(z))


def analyze_response(text, history_texts=None, history_scores=None, history_cache=None):
    history_texts = history_texts or []
    history_scores = history_scores or []

    embedding = get_embedding(text)

    similarity = cosine_similarity(
        baseline_center.reshape(1, -1),
        embedding.reshape(1, -1),
    )[0][0]
    semantic_drift = _clip01((1.0 - similarity) / 2.0)

    js_div = _clip01(compute_js_divergence(baseline_js_reference, embedding))

    raw_anomaly = float(-iso_forest.score_samples(embedding.reshape(1, -1))[0])
    anomaly_score = _clip01(_sigmoid((raw_anomaly - 0.2) / 0.2))

    sentiment_score = sentiment_analyzer.polarity_scores(_safe_text(text))["compound"]
    sentiment_drift = _clip01(abs(sentiment_score - baseline_sentiment) / 2.0)

    current_profile = _text_profile(text)
    lexical_drift = _clip01(
        0.45 * abs(current_profile["type_token_ratio"] - baseline_profile["type_token_ratio"])
        + 0.35 * abs(current_profile["avg_word_len"] - baseline_profile["avg_word_len"]) / 6.0
        + 0.20 * abs(current_profile["punctuation_ratio"] - baseline_profile["punctuation_ratio"]) / 0.25
    )

    cached = history_cache if isinstance(history_cache, dict) else {}
    cached_recent_embeddings = cached.get("recent_embeddings") or []
    cached_mean_embedding = cached.get("mean_embedding")

    hist_embs = np.array(cached_recent_embeddings, dtype=float) if cached_recent_embeddings else np.array([])
    if hist_embs.size == 0 and history_texts:
        hist_embs = np.array([get_embedding(t) for t in history_texts if _safe_text(t)])

    historical_drift = 0.0
    if hist_embs.size > 0 and len(hist_embs) > 0:
        hist_center = np.mean(hist_embs, axis=0)
        hist_center = hist_center / (np.linalg.norm(hist_center) + EPS)
        hist_sim = cosine_similarity(hist_center.reshape(1, -1), embedding.reshape(1, -1))[0][0]
        historical_drift = _clip01((1.0 - hist_sim) / 2.0)
    elif cached_mean_embedding is not None:
        hist_center = np.array(cached_mean_embedding, dtype=float)
        hist_center = hist_center / (np.linalg.norm(hist_center) + EPS)
        hist_sim = cosine_similarity(hist_center.reshape(1, -1), embedding.reshape(1, -1))[0][0]
        historical_drift = _clip01((1.0 - hist_sim) / 2.0)

    current_window = np.vstack([hist_embs[-24:], embedding.reshape(1, -1)]) if hist_embs.size > 0 else embedding.reshape(1, -1)
    mmd_stat, mmd_pvalue = compute_mmd_with_pvalue(baseline_embeddings, current_window, permutations=48)
    mmd_drift = _clip01(mmd_stat / 0.75)
    mmd_pvalue_inv = _clip01(1.0 - mmd_pvalue)

    ref_for_domain = baseline_embeddings
    if hist_embs.size > 0 and len(hist_embs) >= 12:
        ref_for_domain = np.vstack([baseline_embeddings, hist_embs[: max(6, len(hist_embs) // 3)]])
    cur_for_domain = np.vstack([hist_embs[-24:], embedding.reshape(1, -1)]) if hist_embs.size > 0 else embedding.reshape(1, -1)
    domain_auc_shift = compute_domain_auc_shift(ref_for_domain, cur_for_domain)

    past_scores = [
        s.get("drift_score") for s in history_scores if isinstance(s, dict) and isinstance(s.get("drift_score"), (int, float))
    ]

    base_detector = _clip01(
        0.28 * semantic_drift
        + 0.10 * sentiment_drift
        + 0.08 * lexical_drift
        + 0.12 * js_div
        + 0.14 * mmd_drift
        + 0.08 * mmd_pvalue_inv
        + 0.08 * historical_drift
        + 0.12 * domain_auc_shift
    )

    series_with_current = (past_scores[-59:] + [base_detector]) if past_scores else [base_detector]

    if len(series_with_current) >= 6:
        x = np.arange(len(series_with_current), dtype=float)
        slope = np.polyfit(x, np.array(series_with_current), 1)[0]
        trend_shift = _clip01(_sigmoid(slope * 40.0))
    else:
        trend_shift = base_detector

    ewma_score = _clip01(compute_ewma(series_with_current, alpha=0.3))
    page_hinkley_score, change_detected = compute_page_hinkley(series_with_current, delta=0.004, threshold=0.08)
    volatility_risk = _clip01(np.std(series_with_current) / 0.25)

    feature_map = {
        "semantic_drift": semantic_drift,
        "sentiment_drift": sentiment_drift,
        "lexical_drift": lexical_drift,
        "js_divergence": js_div,
        "mmd_drift": mmd_drift,
        "mmd_pvalue_inv": mmd_pvalue_inv,
        "historical_drift": historical_drift,
        "domain_auc_shift": domain_auc_shift,
        "anomaly_score": anomaly_score,
        "trend_shift": trend_shift,
        "ewma_score": ewma_score,
        "page_hinkley_score": page_hinkley_score,
        "volatility_risk": volatility_risk,
    }

    rule_probability = _compute_rule_risk(feature_map)

    ml_probability = None
    if MODEL_PACK and isinstance(MODEL_PACK, dict):
        model_obj = MODEL_PACK.get("model")
        calibrator = MODEL_PACK.get("calibrator")
        feature_order = MODEL_PACK.get("feature_keys", FEATURE_KEYS)
        row = [feature_map.get(k, 0.0) for k in feature_order]
        try:
            if calibrator is not None:
                ml_probability = float(calibrator.predict_proba([row])[0][1])
            elif model_obj is not None:
                ml_probability = float(model_obj.predict_proba([row])[0][1])
        except Exception:
            ml_probability = None

    model_rule_disagreement = 0.0
    high_risk_probability = rule_probability
    if ml_probability is not None:
        model_rule_disagreement = abs(ml_probability - rule_probability)
        high_risk_probability = _clip01(0.80 * ml_probability + 0.20 * rule_probability)

    drift_score = _clip01(
        0.65 * high_risk_probability
        + 0.10 * anomaly_score
        + 0.10 * domain_auc_shift
        + 0.08 * page_hinkley_score
        + 0.07 * volatility_risk
    )

    consistency = 1.0 - np.std([
        semantic_drift,
        mmd_drift,
        domain_auc_shift,
        anomaly_score,
        page_hinkley_score,
    ]) / 0.35
    consistency = _clip01(consistency)
    history_factor = _clip01(len(series_with_current) / 30.0)
    model_factor = 1.0 if ml_probability is not None else 0.7

    confidence_score = _clip01(
        0.35
        + 0.35 * consistency
        + 0.20 * history_factor
        + 0.10 * model_factor
        - 0.25 * model_rule_disagreement
    )
    uncertainty_score = _clip01(1.0 - confidence_score)

    if drift_score >= 0.78:
        risk_level = "critical"
    elif drift_score >= 0.58:
        risk_level = "high"
    elif drift_score >= 0.38:
        risk_level = "moderate"
    else:
        risk_level = "low"

    return {
        "scoring_mode": "ml_calibrated" if ml_probability is not None else "detector_rule",
        "embedding_backend": "sentence-transformers" if SENTENCE_TRANSFORMERS_AVAILABLE else "transformers-fallback",
        "cosine_similarity": float(similarity),
        "semantic_drift": float(semantic_drift),
        "sentiment_score": float(sentiment_score),
        "sentiment_drift": float(sentiment_drift),
        "lexical_drift": float(lexical_drift),
        "js_divergence": float(js_div),
        "mmd_drift": float(mmd_drift),
        "mmd_stat": float(mmd_stat),
        "mmd_pvalue": float(mmd_pvalue),
        "mmd_pvalue_inv": float(mmd_pvalue_inv),
        "historical_drift": float(historical_drift),
        "domain_auc_shift": float(domain_auc_shift),
        "anomaly_score": float(anomaly_score),
        "trend_shift": float(trend_shift),
        "ewma_score": float(ewma_score),
        "page_hinkley_score": float(page_hinkley_score),
        "change_detected": bool(change_detected),
        "volatility_risk": float(volatility_risk),
        "ml_probability": float(ml_probability) if ml_probability is not None else None,
        "model_rule_disagreement": float(model_rule_disagreement),
        "high_risk_probability": float(high_risk_probability),
        "confidence_score": float(confidence_score),
        "uncertainty_score": float(uncertainty_score),
        "risk_level": risk_level,
        "word_count": int(current_profile["word_count"]),
        "drift_score": float(drift_score),
    }
