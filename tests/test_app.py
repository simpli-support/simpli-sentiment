"""Tests for the FastAPI application."""

from fastapi.testclient import TestClient
from simpli_sentiment.app import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze() -> None:
    response = client.post("/analyze", json={"customer_id": "C-001", "text": "This is frustrating"})
    assert response.status_code == 200
    assert "score" in response.json()
