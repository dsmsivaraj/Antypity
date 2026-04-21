# Security & Secrets Handling — Actypity

This document explains how to manage secrets and configuration for Actypity safely.

1. Do not commit secrets
- Never commit `.env` or any file containing API keys, passwords, or private tokens. `.gitignore` already excludes `.env` and common secret files.

2. Use .env.example for local development
- Copy `.env.example` -> `.env` for local testing. Fill values there.
- Example values are placeholders and not secrets.

3. CI/CD and production
- Use your CI/CD provider's secret store (GitHub Actions Secrets, Azure Key Vault, HashiCorp Vault, etc.).
- Do not store secrets in repository YAML or plaintext files. Replace any placeholders in `k8s/secrets.yaml` at deploy-time with base64-encoded values from your secret manager.

4. Kubernetes
- `k8s/secrets.yaml` in this repo contains placeholders only. Deploy using `kubectl create secret generic` or your helm/terraform pipeline to inject real values.

5. Rotating and auditing
- Rotate keys periodically and revoke unused keys.
- Use short-lived credentials where possible.

6. Scanning for secrets
- Run tools like `git-secrets`, `truffleHog`, or `detect-secrets` on CI to prevent accidental commits.
- A simple script `scripts/check_secrets.py` is included to detect obvious leaks (API_KEY, SECRET_KEY, password patterns). Use it as a pre-commit check.

7. Logging and telemetry
- Avoid logging raw PII or secrets. The app's log handler scrubs sensitive fields by default, but review log statements when adding features.

8. Contact
- For any security incident, rotate keys immediately and notify the platform admin.
