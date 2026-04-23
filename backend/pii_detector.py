"""PII detection and anonymization using Microsoft Presidio.

Falls back to regex-only detection if the spaCy NLP model is unavailable.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import List, Optional

_logger = logging.getLogger(__name__)

# Regex-based fallback patterns
_REGEX_PATTERNS = {
    "EMAIL": re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
    "PHONE": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"),
}


@dataclass
class PIIMatch:
    entity_type: str
    text: str
    start: int
    end: int
    score: float


class PIIDetector:
    """Detects PII in text, optionally anonymizing it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analyzer = None
        self._anonymizer = None
        self._init_presidio()

    def _init_presidio(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            _logger.info("PIIDetector: Presidio initialized.")
        except Exception as exc:
            _logger.warning("PIIDetector: Presidio unavailable (%s) — using regex fallback.", exc)

    @property
    def is_presidio_available(self) -> bool:
        return self._analyzer is not None

    def detect(self, text: str, language: str = "en") -> List[PIIMatch]:
        """Returns list of detected PII entities."""
        if not text or not text.strip():
            return []

        if self._analyzer is not None:
            try:
                with self._lock:
                    results = self._analyzer.analyze(text=text, language=language)
                return [
                    PIIMatch(
                        entity_type=r.entity_type,
                        text=text[r.start:r.end],
                        start=r.start,
                        end=r.end,
                        score=r.score,
                    )
                    for r in results
                ]
            except Exception as exc:
                _logger.warning("Presidio analyze failed: %s — falling back to regex", exc)

        # Regex fallback
        matches = []
        for entity_type, pattern in _REGEX_PATTERNS.items():
            for m in pattern.finditer(text):
                matches.append(PIIMatch(
                    entity_type=entity_type,
                    text=m.group(),
                    start=m.start(),
                    end=m.end(),
                    score=0.8,
                ))
        return matches

    def anonymize(self, text: str, language: str = "en") -> str:
        """Returns text with PII replaced by <ENTITY_TYPE> placeholders."""
        if not text or not text.strip():
            return text

        if self._analyzer is not None and self._anonymizer is not None:
            try:
                with self._lock:
                    results = self._analyzer.analyze(text=text, language=language)
                    anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
                return anonymized.text
            except Exception as exc:
                _logger.warning("Presidio anonymize failed: %s — using regex fallback", exc)

        # Regex fallback
        result = text
        for entity_type, pattern in _REGEX_PATTERNS.items():
            result = pattern.sub(f"<{entity_type}>", result)
        return result

    def has_pii(self, text: str, min_score: float = 0.6) -> bool:
        matches = self.detect(text)
        return any(m.score >= min_score for m in matches)

    def get_status(self) -> dict:
        return {
            "backend": "presidio" if self.is_presidio_available else "regex",
            "entities_supported": (
                list(_REGEX_PATTERNS.keys())
                if not self.is_presidio_available
                else ["EMAIL", "PHONE", "SSN", "CREDIT_CARD", "PERSON", "LOCATION", "NRP", "DATE_TIME", "IP_ADDRESS"]
            ),
        }


# Module singleton
_detector: Optional[PIIDetector] = None
_detector_lock = threading.Lock()


def get_pii_detector() -> PIIDetector:
    global _detector
    with _detector_lock:
        if _detector is None:
            _detector = PIIDetector()
        return _detector
