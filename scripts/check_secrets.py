#!/usr/bin/env python3
"""Simple repo secret scanner — checks for common patterns. Not a replacement for dedicated tools.

Usage: python scripts/check_secrets.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"(api_key|apikey|api-key)[\s=:]+[\w-]{16,}" , re.I),
    re.compile(r"(secret_key|SECRET_KEY|password)[\s=:]+[\w-]{8,}", re.I),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # openai-like sk-
]

IGNORE_PATHS = [
    ".git",
    "node_modules",
    "frontend/dist",
    "backend/data",
]


def scan_file(path: Path):
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    findings = []
    for p in PATTERNS:
        for m in p.finditer(text):
            findings.append((m.group(0), m.start(0)))
    return findings


def main():
    findings_total = 0
    for p in ROOT.rglob("*"):
        if any(ign in str(p) for ign in IGNORE_PATHS):
            continue
        if p.is_file():
            f = scan_file(p)
            if f:
                print(f"Potential secrets in {p}:")
                for val, pos in f:
                    print(f"  - {val} at {pos}")
                findings_total += len(f)
    if findings_total == 0:
        print("No obvious secrets found by simple scanner.")
    else:
        print(f"Found {findings_total} potential secrets — investigate before committing.")


if __name__ == '__main__':
    main()
