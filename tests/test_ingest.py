"""Tests for data ingest endpoints."""

import io
import json

from fastapi.testclient import TestClient

from simpli_sentiment.app import app

client = TestClient(app)


def test_ingest_csv() -> None:
    csv_content = (
        "customer_id,text\n"
        "cust-1,This product is terrible\n"
        "cust-2,Great service thanks\n"
    )
    file = io.BytesIO(csv_content.encode())
    response = client.post(
        "/api/v1/ingest",
        files={"file": ("data.csv", file, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["processed"] == 2
    assert len(data["results"]) == 2


def test_ingest_json() -> None:
    records = [
        {"customer_id": "cust-1", "text": "I am very frustrated"},
    ]
    file = io.BytesIO(json.dumps(records).encode())
    response = client.post(
        "/api/v1/ingest",
        files={"file": ("data.json", file, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["processed"] == 1


def test_ingest_salesforce_missing_credentials() -> None:
    response = client.post(
        "/api/v1/ingest/salesforce",
        json={"limit": 10},
    )
    assert response.status_code == 400
    assert "credentials" in response.json()["detail"].lower()
