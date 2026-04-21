"""Embedding recall@k evaluation script for local dev.
Run this after FAISS and sentence-transformers are installed.
Usage: python3 backend/scripts/eval_recall.py
"""
from backend.embeddings_service import get_embedding_service

# Small synthetic dataset: doc_id -> text
DOCS = {
    "doc1": "Senior Python backend engineer with experience in FastAPI, PostgreSQL, and distributed systems.",
    "doc2": "Frontend engineer skilled in React, TypeScript, Vite, and UI/UX design.",
    "doc3": "Machine learning engineer experienced with PyTorch, model training, and MLOps.",
    "doc4": "DevOps engineer, CI/CD, Kubernetes, Docker, and AWS infrastructure.",
    "doc5": "Data scientist with experience in NLP, embeddings, and semantic search.",
}

# Queries -> ground truth doc ids
QUERIES = {
    "python backend fastapi": ["doc1"],
    "react typescript frontend": ["doc2"],
    "nlp embeddings semantic search": ["doc5"],
    "pytorch model training": ["doc3"],
}


def recall_at_k(svc, queries, k=3):
    hits = 0
    total = 0
    for q, gts in queries.items():
        total += 1
        results = svc.query(q, top_k=k)
        returned_ids = [r.get("doc_id") for r in results]
        if any(rid in gts for rid in returned_ids):
            hits += 1
    return hits / total if total else 0.0


def main():
    svc = get_embedding_service()
    print('Embedding service status:', svc.status())
    print('Indexing docs...')
    for did, text in DOCS.items():
        svc.index_document(doc_id=did, section_id='s1', text=text)
    print('Running recall@k eval...')
    for k in (1, 3, 5):
        r = recall_at_k(svc, QUERIES, k=k)
        print(f'recall@{k}: {r:.2f}')

if __name__ == '__main__':
    main()
