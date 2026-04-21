"""Simple prompt registry with file-backed storage and optional DB hooks.
Usage:
  from backend.prompt_registry import get_prompt, register_prompt
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

DATA_DIR = Path(__file__).resolve().parent / "data" / "prompts"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _prompt_path(name: str, version: str) -> Path:
    return DATA_DIR / name / f"{version}.json"


def _prompt_dir(name: str) -> Path:
    return DATA_DIR / name


def register_prompt(name: str, text: str, meta: Optional[Dict] = None) -> Dict:
    """Register a new prompt version. Returns metadata including version id."""
    meta = meta or {}
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ver = f"v{now}"
    d = _prompt_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    payload = {"name": name, "version": ver, "text": text, "meta": meta, "created_at": now}
    p = _prompt_path(name, ver)
    p.write_text(json.dumps(payload, ensure_ascii=False))
    return payload


def list_prompt_versions(name: str):
    d = _prompt_dir(name)
    if not d.exists():
        return []
    return sorted([p.stem for p in d.glob("*.json")], reverse=True)


def get_prompt(name: str, version: Optional[str] = None) -> Dict:
    d = _prompt_dir(name)
    if not d.exists():
        raise FileNotFoundError(f"No prompt named {name}")
    versions = sorted([p.stem for p in d.glob("*.json")], reverse=True)
    if not versions:
        raise FileNotFoundError(f"No versions for prompt {name}")
    use = version or versions[0]
    p = _prompt_path(name, use)
    return json.loads(p.read_text(encoding='utf-8'))
