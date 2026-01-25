"""
core/nlp_models.py

ALL intelligence lives here.
NO business logic makes security decisions.

Models implemented:
1. SensitivityClassifier      → Semantic PII sensitivity
2. PIINER                     → NLP-style entity candidate detection
3. PromptInjectionDetector    → Holistic semantic injection detection
"""

from typing import List, Dict


# ============================================================
# 1. Sensitivity Classification Model (Semantic)
# ============================================================

class SensitivityClassifier:
    """
    Semantic sensitivity classifier.

    In production:
    - Fine-tuned BERT / RoBERTa / DeBERTa
    """

    def predict(self, text: str) -> Dict[str, float]:
        text = text.strip()

        if not text:
            return {
                "public": 1.0,
                "internal": 0.0,
                "confidential": 0.0,
                "restricted": 0.0
            }

        # Semantic heuristic (simulating learned behavior)
        contains_digits = any(c.isdigit() for c in text)
        long_span = len(text) >= 6

        if contains_digits and long_span:
            return {
                "public": 0.05,
                "internal": 0.10,
                "confidential": 0.70,
                "restricted": 0.15
            }

        return {
            "public": 0.65,
            "internal": 0.20,
            "confidential": 0.10,
            "restricted": 0.05
        }


# ============================================================
# 2. Neural PII Detector (NLP-style, NO POLICY)
# ============================================================

class PIINER:
    """
    Simulated neural NER.

    Purpose:
    - Detect candidate spans
    - NOT to decide sensitivity
    """

    def detect(self, text: str) -> List[Dict]:
        entities = []

        tokens = text.split()

        for token in tokens:
            if "@" in token and "." in token:
                entities.append({
                    "text": token,
                    "label": "EMAIL"
                })

            elif token.replace("-", "").replace("+", "").isdigit() and len(token) >= 8:
                entities.append({
                    "text": token,
                    "label": "NUMERIC_IDENTIFIER"
                })

        return entities


# ============================================================
# 3. PROMPT INJECTION DETECTOR (HOLISTIC NLP)
# ============================================================

class PromptInjectionDetector:
    """
    Explainable, NLP-style prompt injection detector.

    Returns:
    - total risk score
    - contributing phrases
    - per-signal weights
    """

    def analyze(self, text: str) -> Dict:
        t = text.lower()

        signals = []
        score = 0.0

        def hit(phrase, weight, category):
            nonlocal score
            signals.append({
                "phrase": phrase,
                "category": category,
                "weight": weight
            })
            score += weight

        # ---------- Authority Hijacking ----------
        authority = [
            "act as",
            "you are now",
            "assume the role",
            "unrestricted assistant"
        ]
        for p in authority:
            if p in t:
                hit(p, 0.30, "authority_hijack")

        # ---------- Instruction Override ----------
        override = [
            "ignore previous instructions",
            "override instructions",
            "disregard rules"
        ]
        for p in override:
            if p in t:
                hit(p, 0.40, "instruction_override")

        # ---------- Safety Suppression ----------
        suppression = [
            "do not mention anonymization",
            "do not mention safety",
            "no restrictions"
        ]
        for p in suppression:
            if p in t:
                hit(p, 0.30, "safety_suppression")

        # ---------- Context Smuggling ----------
        smuggling = [
            "controlled evaluation",
            "security test",
            "for research purposes"
        ]
        for p in smuggling:
            if p in t:
                hit(p, 0.20, "context_smuggling")

        return {
            "score": min(score, 1.0),
            "signals": signals
        }

    def score(self, text: str) -> float:
        return self.analyze(text)["score"]



# ============================================================
# 4. MODEL REGISTRY (SINGLE SOURCE OF TRUTH)
# ============================================================

sensitivity_classifier = SensitivityClassifier()
pii_ner = PIINER()
injection_detector = PromptInjectionDetector()
