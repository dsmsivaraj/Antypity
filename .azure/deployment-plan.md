# Azure Deployment Plan

## Project Overview
- **Application**: Actypity - Full-stack app with Python backend, React frontend, agents, Azure OpenAI, Cosmos DB
- **Mode**: MODIFY (added database, Docker, Kubernetes, config files)
- **Target Services**: Azure Container Apps, Azure Cosmos DB, Azure OpenAI

## Requirements
- Database: Azure Cosmos DB for NoSQL data storage
- Containerization: Docker for backend and frontend
- Orchestration: Kubernetes for deployment
- Configuration: .env, config.py, secrets management
- Git: Scripts for operations, .gitignore for secrets

## Infrastructure Decisions
- Backend: Containerized with Docker, deployed to Azure Container Apps
- Frontend: Containerized, deployed to Azure Static Web Apps or Container Apps
- Database: Azure Cosmos DB
- Secrets: Azure Key Vault

## Deployment Steps
1. Build Docker images
2. Push to Azure Container Registry
3. Deploy to Azure Container Apps using Bicep
4. Configure Key Vault for secrets

## Validation Checklist
- [ ] Docker images build successfully
- [ ] Kubernetes manifests valid
- [ ] Secrets not in Git
- [ ] Config loads from .env