"""FastAPI application."""

import re
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from simpli_core import Channel, create_app
from simpli_sentiment.settings import settings

logger = structlog.get_logger()

app = create_app(
    title="Simpli Sentiment",
    version="0.1.0",
    description="Customer health and sentiment tracker with escalation risk detection",
    settings=settings,
    cors_origins="*",
)

# ---------------------------------------------------------------------------
# Keyword-based sentiment analyzer (no ML dependencies required)
# ---------------------------------------------------------------------------

NEGATIVE_KEYWORDS: dict[str, float] = {
    "terrible": -0.9,
    "awful": -0.85,
    "horrible": -0.85,
    "worst": -0.8,
    "hate": -0.8,
    "furious": -0.8,
    "unacceptable": -0.75,
    "frustrated": -0.7,
    "frustrating": -0.7,
    "angry": -0.7,
    "disgusted": -0.65,
    "disappointed": -0.6,
    "annoyed": -0.55,
    "upset": -0.55,
    "bad": -0.5,
    "poor": -0.5,
    "unhappy": -0.5,
    "broken": -0.45,
    "useless": -0.45,
    "slow": -0.3,
    "confusing": -0.3,
    "difficult": -0.25,
    "problem": -0.25,
    "issue": -0.2,
    "bug": -0.2,
}

POSITIVE_KEYWORDS: dict[str, float] = {
    "excellent": 0.9,
    "amazing": 0.85,
    "fantastic": 0.85,
    "wonderful": 0.8,
    "outstanding": 0.8,
    "love": 0.75,
    "great": 0.7,
    "perfect": 0.7,
    "awesome": 0.7,
    "happy": 0.6,
    "pleased": 0.6,
    "satisfied": 0.55,
    "good": 0.5,
    "nice": 0.45,
    "helpful": 0.45,
    "easy": 0.4,
    "fast": 0.35,
    "smooth": 0.35,
    "thanks": 0.3,
    "thank": 0.3,
    "appreciate": 0.3,
    "fine": 0.2,
    "okay": 0.1,
    "ok": 0.1,
}

ESCALATION_TRIGGERS = [
    "cancel",
    "lawsuit",
    "lawyer",
    "legal",
    "refund",
    "manager",
    "supervisor",
    "complaint",
    "report",
    "bbb",
    "attorney",
    "escalate",
    "unacceptable",
    "sue",
]

CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$")


def _analyze_text(text: str) -> tuple[float, list[str]]:
    """Return (sentiment_score, triggered_keywords) from text."""
    words = text.lower().split()
    scores: list[float] = []
    triggers: list[str] = []

    for word in words:
        cleaned = word.strip(".,!?;:'\"()[]{}").lower()
        if cleaned in NEGATIVE_KEYWORDS:
            scores.append(NEGATIVE_KEYWORDS[cleaned])
        if cleaned in POSITIVE_KEYWORDS:
            scores.append(POSITIVE_KEYWORDS[cleaned])
        if cleaned in ESCALATION_TRIGGERS:
            triggers.append(cleaned)

    score = sum(scores) / len(scores) if scores else 0.0
    score = max(-1.0, min(1.0, score))
    return score, triggers


def _score_to_label(score: float) -> str:
    if score >= 0.3:
        return "positive"
    if score <= -0.3:
        return "negative"
    return "neutral"


def _escalation_risk(score: float, triggers: list[str]) -> float:
    risk = 0.0
    if score < -0.3:
        risk += min(abs(score), 0.5)
    risk += min(len(triggers) * 0.15, 0.5)
    return round(min(risk, 1.0), 2)


# ---------------------------------------------------------------------------
# In-memory store (placeholder for database integration)
# ---------------------------------------------------------------------------

_sentiment_store: dict[str, list[dict[str, str | float]]] = {}
_alerts_store: list[dict[str, str]] = []


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    customer_id: str = Field(
        ..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$"
    )
    text: str = Field(..., min_length=1, max_length=10000)
    channel: Channel | None = Field(default=None)


class SentimentResult(BaseModel):
    score: float
    label: str
    escalation_risk: float
    triggers: list[str]


class SentimentTimepoint(BaseModel):
    timestamp: str
    score: float
    label: str
    source: str


class CustomerSentiment(BaseModel):
    customer_id: str
    current_score: float
    trend: str
    timeline: list[SentimentTimepoint]


class Alert(BaseModel):
    id: str
    customer_id: str
    severity: str
    reason: str
    created_at: str


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(
    "/customers/{customer_id}/sentiment",
    response_model=CustomerSentiment,
    responses={404: {"model": ErrorResponse}},
    tags=["customers"],
)
async def get_customer_sentiment(
    customer_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CustomerSentiment | JSONResponse:
    """Get sentiment timeline for a customer."""
    if not CUSTOMER_ID_PATTERN.match(customer_id):
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid customer_id format"},
        )

    history = _sentiment_store.get(customer_id, [])
    paginated = history[offset : offset + limit]

    timeline = [
        SentimentTimepoint(
            timestamp=str(entry["timestamp"]),
            score=float(entry["score"]),
            label=str(entry["label"]),
            source=str(entry.get("source", "api")),
        )
        for entry in paginated
    ]

    current_score = float(history[-1]["score"]) if history else 0.0

    if len(history) >= 2:
        recent = [float(e["score"]) for e in history[-3:]]
        avg_recent = sum(recent) / len(recent)
        trend = (
            "improving"
            if avg_recent > current_score + 0.1
            else "declining"
            if avg_recent < current_score - 0.1
            else "stable"
        )
    else:
        trend = "stable"

    return CustomerSentiment(
        customer_id=customer_id,
        current_score=round(current_score, 2),
        trend=trend,
        timeline=timeline,
    )


@app.post(
    "/analyze",
    response_model=SentimentResult,
    tags=["analysis"],
)
async def analyze(request: AnalyzeRequest) -> SentimentResult:
    """Analyze sentiment of a message or conversation."""
    score, triggers = _analyze_text(request.text)
    label = _score_to_label(score)
    risk = _escalation_risk(score, triggers)

    now = datetime.now(UTC).isoformat()
    entry: dict[str, str | float] = {
        "timestamp": now,
        "score": round(score, 2),
        "label": label,
        "source": request.channel or "api",
    }
    _sentiment_store.setdefault(request.customer_id, []).append(entry)

    if risk >= 0.5:
        alert = {
            "id": str(uuid.uuid4()),
            "customer_id": request.customer_id,
            "severity": "high" if risk >= 0.75 else "medium",
            "reason": (
                f"Escalation risk {risk} — triggers: "
                f"{', '.join(triggers) or 'negative sentiment'}"
            ),
            "created_at": now,
        }
        _alerts_store.append(alert)
        logger.warning("escalation_alert_created", **alert)

    return SentimentResult(
        score=round(score, 2),
        label=label,
        escalation_risk=risk,
        triggers=triggers,
    )


@app.get(
    "/alerts",
    response_model=list[Alert],
    tags=["alerts"],
)
async def get_alerts(
    severity: str | None = Query(default=None, pattern=r"^(low|medium|high)$"),
    customer_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Alert]:
    """Get active escalation risk alerts."""
    filtered = _alerts_store
    if severity:
        filtered = [a for a in filtered if a["severity"] == severity]
    if customer_id:
        filtered = [a for a in filtered if a["customer_id"] == customer_id]

    paginated = filtered[offset : offset + limit]
    return [Alert(**a) for a in paginated]
