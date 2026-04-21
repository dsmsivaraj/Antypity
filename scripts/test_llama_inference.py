#!/usr/bin/env python3
"""Quick test for local LLaMA client.
Set LLAMA_MODEL_PATH to a GGML model file and run this script after installing backend/requirements-llama.txt
"""
import os

try:
    from backend.llama_client import LlamaClient
except Exception as e:
    print("LLaMA client import failed:", e)
    raise


def main():
    model_path = os.getenv("LLAMA_MODEL_PATH")
    if not model_path:
        print("Please set LLAMA_MODEL_PATH env var to the GGML model file path.")
        return
    client = LlamaClient(model_path=model_path)
    out = client.generate("Summarize: The quick brown fox jumps over the lazy dog.", max_tokens=64)
    print("Model output:\n", out)

if __name__ == '__main__':
    main()
