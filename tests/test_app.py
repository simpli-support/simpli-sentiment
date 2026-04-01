"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from simpli_sentiment.app import (
    _alerts_store,
    _analyze_text,
    _escalation_risk,
    _score_to_label,
    _sentiment_store,
    app,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_stores() -> None:  # type: ignore[misc]
    """Clear in-memory stores between tests."""
    _sentiment_store.clear()
    _alerts_store.clear()


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Analyze endpoint
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_analyze_negative_text(self) -> None:
        response = client.post(
            "/analyze",
            json={"customer_id": "C-001", "text": "This is frustrating and terrible"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] < 0
        assert data["label"] == "negative"
        assert data["escalation_risk"] >= 0
        assert isinstance(data["triggers"], list)

    def test_analyze_positive_text(self) -> None:
        response = client.post(
            "/analyze",
            json={"customer_id": "C-002", "text": "This is amazing and wonderful"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] > 0
        assert data["label"] == "positive"

    def test_analyze_neutral_text(self) -> None:
        response = client.post(
            "/analyze",
            json={"customer_id": "C-003", "text": "I received the package today"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "neutral"

    def test_analyze_with_escalation_triggers(self) -> None:
        response = client.post(
            "/analyze",
            json={
                "customer_id": "C-004",
                "text": "This is terrible, I want to cancel and get a refund",
            },
        )
        data = response.json()
        assert data["escalation_risk"] > 0
        assert "cancel" in data["triggers"]
        assert "refund" in data["triggers"]

    def test_analyze_with_channel(self) -> None:
        response = client.post(
            "/analyze",
            json={
                "customer_id": "C-005",
                "text": "Great service",
                "channel": "email",
            },
        )
        assert response.status_code == 200

    def test_analyze_stores_sentiment(self) -> None:
        client.post(
            "/analyze",
            json={"customer_id": "C-010", "text": "Good experience"},
        )
        assert "C-010" in _sentiment_store
        assert len(_sentiment_store["C-010"]) == 1

    def test_analyze_creates_alert_on_high_risk(self) -> None:
        client.post(
            "/analyze",
            json={
                "customer_id": "C-011",
                "text": "Terrible awful, I want to cancel and sue and get a refund",
            },
        )
        assert len(_alerts_store) >= 1
        assert _alerts_store[0]["customer_id"] == "C-011"

    def test_analyze_missing_customer_id(self) -> None:
        response = client.post("/analyze", json={"text": "Hello"})
        assert response.status_code == 422

    def test_analyze_missing_text(self) -> None:
        response = client.post("/analyze", json={"customer_id": "C-001"})
        assert response.status_code == 422

    def test_analyze_empty_text(self) -> None:
        response = client.post("/analyze", json={"customer_id": "C-001", "text": ""})
        assert response.status_code == 422

    def test_analyze_invalid_customer_id_format(self) -> None:
        response = client.post(
            "/analyze", json={"customer_id": "../../etc", "text": "Hello"}
        )
        assert response.status_code == 422

    def test_analyze_text_too_long(self) -> None:
        response = client.post(
            "/analyze", json={"customer_id": "C-001", "text": "x" * 10001}
        )
        assert response.status_code == 422

    def test_analyze_invalid_json(self) -> None:
        response = client.post(
            "/analyze",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Customer sentiment endpoint
# ---------------------------------------------------------------------------


class TestCustomerSentiment:
    def test_get_empty_customer(self) -> None:
        response = client.get("/customers/C-100/sentiment")
        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "C-100"
        assert data["current_score"] == 0.0
        assert data["trend"] == "stable"
        assert data["timeline"] == []

    def test_get_customer_with_history(self) -> None:
        client.post("/analyze", json={"customer_id": "C-200", "text": "Great product"})
        client.post(
            "/analyze", json={"customer_id": "C-200", "text": "Excellent service"}
        )
        response = client.get("/customers/C-200/sentiment")
        assert response.status_code == 200
        data = response.json()
        assert len(data["timeline"]) == 2
        assert data["current_score"] > 0

    def test_pagination_limit(self) -> None:
        for i in range(5):
            client.post(
                "/analyze",
                json={"customer_id": "C-300", "text": f"Message {i} is good"},
            )
        response = client.get("/customers/C-300/sentiment?limit=2")
        data = response.json()
        assert len(data["timeline"]) == 2

    def test_pagination_offset(self) -> None:
        for i in range(5):
            client.post(
                "/analyze",
                json={"customer_id": "C-301", "text": f"Message {i} is good"},
            )
        response = client.get("/customers/C-301/sentiment?limit=2&offset=3")
        data = response.json()
        assert len(data["timeline"]) == 2

    def test_invalid_customer_id_special_chars(self) -> None:
        response = client.get("/customers/@invalid!/sentiment")
        assert response.status_code == 400

    def test_invalid_customer_id_empty(self) -> None:
        response = client.get("/customers/%20/sentiment")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Alerts endpoint
# ---------------------------------------------------------------------------


class TestAlerts:
    def test_empty_alerts(self) -> None:
        response = client.get("/alerts")
        assert response.status_code == 200
        assert response.json() == []

    def test_alerts_after_escalation(self) -> None:
        client.post(
            "/analyze",
            json={
                "customer_id": "C-400",
                "text": "Terrible, I want to cancel and sue and get a refund now",
            },
        )
        response = client.get("/alerts")
        data = response.json()
        assert len(data) >= 1
        assert data[0]["customer_id"] == "C-400"

    def test_alerts_filter_by_customer(self) -> None:
        client.post(
            "/analyze",
            json={
                "customer_id": "C-500",
                "text": "Awful, I want to cancel and sue",
            },
        )
        client.post(
            "/analyze",
            json={
                "customer_id": "C-501",
                "text": "Terrible, need a refund and manager",
            },
        )
        response = client.get("/alerts?customer_id=C-500")
        data = response.json()
        assert all(a["customer_id"] == "C-500" for a in data)

    def test_alerts_filter_by_severity(self) -> None:
        client.post(
            "/analyze",
            json={
                "customer_id": "C-600",
                "text": "Terrible awful, cancel and sue and refund and lawyer",
            },
        )
        response = client.get("/alerts?severity=high")
        data = response.json()
        assert all(a["severity"] == "high" for a in data)

    def test_alerts_pagination(self) -> None:
        for i in range(5):
            client.post(
                "/analyze",
                json={
                    "customer_id": f"C-7{i:02d}",
                    "text": "Terrible, I want to cancel and sue and refund",
                },
            )
        response = client.get("/alerts?limit=2")
        data = response.json()
        assert len(data) <= 2

    def test_alerts_invalid_severity(self) -> None:
        response = client.get("/alerts?severity=critical")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Request middleware
# ---------------------------------------------------------------------------


class TestMiddleware:
    def test_request_id_header(self) -> None:
        response = client.get("/health")
        assert "x-request-id" in response.headers


# ---------------------------------------------------------------------------
# Internal functions
# ---------------------------------------------------------------------------


class TestSentimentAnalysis:
    def test_analyze_text_negative(self) -> None:
        score, triggers = _analyze_text("I am frustrated and angry")
        assert score < 0
        assert triggers == []

    def test_analyze_text_positive(self) -> None:
        score, _ = _analyze_text("This is great and amazing")
        assert score > 0

    def test_analyze_text_empty(self) -> None:
        score, triggers = _analyze_text("")
        assert score == 0.0
        assert triggers == []

    def test_analyze_text_with_triggers(self) -> None:
        _, triggers = _analyze_text("I want to cancel my subscription")
        assert "cancel" in triggers

    def test_score_to_label(self) -> None:
        assert _score_to_label(0.5) == "positive"
        assert _score_to_label(-0.5) == "negative"
        assert _score_to_label(0.0) == "neutral"
        assert _score_to_label(0.3) == "positive"
        assert _score_to_label(-0.3) == "negative"
        assert _score_to_label(0.29) == "neutral"
        assert _score_to_label(-0.29) == "neutral"

    def test_escalation_risk(self) -> None:
        assert _escalation_risk(0.5, []) == 0.0
        assert _escalation_risk(-0.5, []) > 0
        assert _escalation_risk(-0.5, ["cancel", "refund"]) > _escalation_risk(-0.5, [])

    def test_escalation_risk_capped_at_one(self) -> None:
        risk = _escalation_risk(-1.0, ["a", "b", "c", "d", "e", "f", "g"])
        assert risk <= 1.0
