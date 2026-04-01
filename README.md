# Simpli Sentiment

Customer health and sentiment tracker that detects escalation risk and measures emotional trajectory across interactions.

## Features

- **Sentiment timeline** — per-customer tracking across all interactions
- **Escalation risk scoring** — likelihood of escalation or churn
- **Frustration patterns** — repeated contacts, negative trends, trigger phrases
- **Real-time alerts** — high-risk conversations flagged for supervisor attention
- **CRM integration** — push sentiment scores to Salesforce, HubSpot, etc.

## Quick Start

```bash
pip install -e ".[dev]"
simpli-sentiment serve
```

## API

- `GET /customers/{id}/sentiment` — customer sentiment timeline
- `POST /analyze` — analyze sentiment of a message
- `GET /alerts` — active escalation risk alerts
- `GET /health` — health check

## Development

```bash
ruff check .
mypy src/
pytest
```
