# Simpli Sentiment

Keyword-based sentiment analysis and escalation risk detection for customer support. Part of the [Simpli Support](https://simpli.support) platform.

## Features

- **Sentiment analysis** — score message sentiment using keyword matching (no ML dependencies)
- **Escalation risk detection** — flag conversations likely to escalate based on trigger phrases
- **Customer sentiment timeline** — track sentiment history per customer with trend detection
- **Real-time alerts** — automatically create alerts when escalation risk is high
- **Channel-aware tracking** — record sentiment source by channel (email, chat, phone, etc.)

## Quick start

```bash
cp .env.example .env
pip install -e ".[dev]"
simpli-sentiment serve
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Analyze sentiment of a message |
| GET | `/customers/{customer_id}/sentiment` | Get sentiment timeline for a customer |
| GET | `/alerts` | Get active escalation risk alerts |
| GET | `/health` | Health check |

## Configuration

All settings are loaded from environment variables or `.env` files via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | `0.0.0.0` | Host to bind the server to |
| `APP_PORT` | `8000` | Port to bind the server to |
| `APP_LOG_LEVEL` | `info` | Log level |
| `WORKERS` | `1` | Number of worker processes |
| `DATABASE_URL` | `None` | Database connection URL |
| `REDIS_URL` | `None` | Redis connection URL |

## Development

```bash
pytest tests/ -q
ruff check .
ruff format --check .
mypy src/
```

## Docker

```bash
docker build -t simpli-sentiment .
docker run -p 8000:8000 simpli-sentiment
```

## License

MIT
