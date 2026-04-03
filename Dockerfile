FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

FROM python:3.12-slim
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app .

USER appuser
EXPOSE 8006
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8006/health')"
CMD ["uvicorn", "simpli_sentiment.app:app", "--host", "0.0.0.0", "--port", "8006"]
