"""Lightweight embedding and vector store for local dev.
Implements simple token-count vectors and a JSON-persisted index.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

INDEX_PATH = Path(__file__).resolve().parent / "data" / "embeddings.json"
INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)


def _tokenize(text: str) -> List[str]:
    tokens = [t for t in ''.join(c if c.isalnum() else ' ' for c in text.lower()).split() if len(t) > 1]
    return tokens


def text_to_vector(text: str) -> Dict[str, float]:
    tokens = _tokenize(text)
    counts = Counter(tokens)
    # convert to tf (term frequency)
    max_c = max(counts.values()) if counts else 1
    vec = {tok: cnt / max_c for tok, cnt in counts.items()}
    return vec


def dot(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    return sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in v1.keys())


def norm(v: Dict[str, float]) -> float:
    return math.sqrt(sum(val * val for val in v.values()))


class VectorIndex:
    def __init__(self, path: Path = INDEX_PATH):
        self.path = path
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
            except Exception:
                self.index = {}
        else:
            self.index = {}

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f)

    def add(self, doc_id: str, section_id: str, text: str):
        vec = text_to_vector(text)
        self.index[f"{doc_id}:{section_id}"] = {
            "doc_id": doc_id,
            "section_id": section_id,
            "text": text[:1000],
            "vec": vec,
        }
        self._save()

    def query(self, text: str, top_k: int = 5) -> List[Dict[str, object]]:
        qv = text_to_vector(text)
        scores: List[Tuple[str, float]] = []
        for key, entry in self.index.items():
            score = 0.0
            try:
                score = dot(qv, entry.get('vec', {})) / (norm(qv) * norm(entry.get('vec', {})) + 1e-9)
            except Exception:
                score = 0.0
            scores.append((key, score))
        scores.sort(key=lambda t: t[1], reverse=True)
        results = []
        for key, score in scores[:top_k]:
            entry = self.index[key]
            results.append({
                "doc_id": entry.get('doc_id'),
                "section_id": entry.get('section_id'),
                "text": entry.get('text'),
                "score": score,
            })
        return results


# Singleton default index
_default_index = VectorIndex()


def add_resume_section_embeddings(resume_id: str, section_id: str, text: str):
    _default_index.add(resume_id, section_id, text)


def query_resume_sections(query_text: str, top_k: int = 5):
    return _default_index.query(query_text, top_k=top_k)
