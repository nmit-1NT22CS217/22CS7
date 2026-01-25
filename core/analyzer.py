"""
core/analyzer.py

PURE NLP PII Candidate Extraction Engine.

Key guarantees:
- ❌ NO regex
- ❌ NO rule-based sensitivity decisions
- ✅ Uses statistical NLP only (spaCy)
- ✅ Provides PIIAnonymizer class (import-safe)
"""

from typing import List, Tuple, Set
import spacy
from spacy.matcher import Matcher


class PIIAnonymizer:
    """
    NLP-only PII candidate extractor.

    This class ONLY finds possible PII spans.
    It does NOT decide whether something is sensitive.
    """

    # spaCy NER → internal semantic labels
    SPACY_PII_ENTITIES = {
        "PERSON": "PERSON_NAME",
        "GPE": "LOCATION",
        "ORG": "ORGANIZATION",
        "DATE": "DATE_TIME",
        "TIME": "DATE_TIME",
        "MONEY": "FINANCIAL_AMOUNT",
        "FAC": "FACILITY_NAME",
        "NORP": "NATIONALITY_GROUP",
        "EVENT": "EVENT_NAME",
        "LAW": "LEGAL_DOCUMENT",
        "LANGUAGE": "LANGUAGE_NAME",
        "WORK_OF_ART": "ARTWORK_TITLE",
        "PRODUCT": "PRODUCT_NAME",
    }

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Load spaCy NLP pipeline.
        """
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            import subprocess
            subprocess.run(
                ["python", "-m", "spacy", "download", model_name],
                check=True
            )
            self.nlp = spacy.load(model_name)

        # Linguistic matcher (NOT regex)
        self.matcher = Matcher(self.nlp.vocab)
        self._setup_patterns()

    # -------------------------------------------------
    # Linguistic (non-regex) patterns
    # -------------------------------------------------
    def _setup_patterns(self):
        """
        Define linguistic patterns using spaCy tokens.
        These are grammar-based, not regex-based.
        """

        # Multi-token person names: John A Smith, Dr John Smith
        self.matcher.add(
            "MULTI_PERSON",
            [
                [{"IS_TITLE": True}, {"IS_TITLE": True, "OP": "+"}],
                [{"LOWER": {"IN": ["mr", "mrs", "ms", "dr", "prof"]}},
                 {"IS_TITLE": True}, {"IS_TITLE": True, "OP": "?"}]
            ]
        )

    # -------------------------------------------------
    # NLP-only PII detection
    # -------------------------------------------------
    def detect_pii(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Detect potential PII spans using ONLY NLP.

        Returns:
            List of tuples:
            (entity_text, entity_type, start_char, end_char)
        """
        doc = self.nlp(text)
        entities: List[Tuple[str, str, int, int]] = []
        seen: Set[Tuple[int, int]] = set()

        # 1️⃣ spaCy Named Entity Recognition (statistical NLP)
        for ent in doc.ents:
            if ent.label_ in self.SPACY_PII_ENTITIES:
                label = self.SPACY_PII_ENTITIES[ent.label_]
                span = (ent.start_char, ent.end_char)

                if span in seen:
                    continue

                entities.append((ent.text, label, ent.start_char, ent.end_char))
                seen.add(span)

        # 2️⃣ Linguistic matcher (grammar-based, not regex)
        for match_id, start, end in self.matcher(doc):
            span = doc[start:end]
            span_tuple = (span.start_char, span.end_char)

            if span_tuple in seen:
                continue

            entities.append((span.text, "PERSON_NAME", span.start_char, span.end_char))
            seen.add(span_tuple)

        # Sort for deterministic downstream replacement
        entities.sort(key=lambda x: x[2])
        return entities

    # -------------------------------------------------
    # Transformations (used by orchestrator)
    # -------------------------------------------------
    def pseudonymize(self, text: str):
        """
        Replace detected entities with placeholders.
        """
        entities = self.detect_pii(text)
        mappings = {}
        result = text
        offset = 0
        counter = 1

        for value, etype, start, end in entities:
            placeholder = f"<{etype}_{counter}>"
            mappings[placeholder] = value

            result = (
                result[: start + offset]
                + placeholder
                + result[end + offset :]
            )
            offset += len(placeholder) - (end - start)
            counter += 1

        return result, mappings

    def mask(self, text: str):
        """
        Irreversible masking.
        """
        entities = self.detect_pii(text)
        result = text
        offset = 0

        for value, _, start, end in entities:
            masked = value[0] + "*" * (len(value) - 1)

            result = (
                result[: start + offset]
                + masked
                + result[end + offset :]
            )
            offset += len(masked) - (end - start)

        return result, {}

    def replace(self, text: str):
        """
        Replace entities with semantic labels.
        """
        entities = self.detect_pii(text)
        result = text
        offset = 0

        for _, etype, start, end in entities:
            replacement = f"[{etype}]"

            result = (
                result[: start + offset]
                + replacement
                + result[end + offset :]
            )
            offset += len(replacement) - (end - start)

        return result, {}
