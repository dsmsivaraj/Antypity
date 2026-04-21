Local LLaMA Integration (draft)

Overview:
- Provide an optional, local LLaMA runtime for offline resume parsing, summarization, and chatbot workflows.
- Installation: pip install -r backend/requirements-llama.txt and provide LLAMA_MODEL_PATH to a GGML model.

Env vars:
- LLAMA_MODEL_PATH: path to ggml model file (required for local model runs)
- FIGMA_TOKEN: personal Figma token (for template designer integration)

Commands:
- Install optional deps: pip install -r backend/requirements-llama.txt
- Test local model: LLAMA_MODEL_PATH=/path/to/model.ggml python scripts/test_llama_inference.py

Notes:
- Model weights are not included. Recommend small-to-medium GGML models for local development.
- For production or cloud, prefer hosted LLM or vector search + smaller LLMs.
