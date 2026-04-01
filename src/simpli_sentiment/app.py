"""FastAPI application."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Simpli Sentiment",
    version="0.1.0",
    description="Customer health and sentiment tracker with escalation risk detection",
)


class AnalyzeRequest(BaseModel):
    customer_id: str
    text: str
    channel: str | None = None


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


@app.get("/customers/{customer_id}/sentiment", response_model=CustomerSentiment)
async def get_customer_sentiment(customer_id: str) -> CustomerSentiment:
    """Get sentiment timeline for a customer."""
    return CustomerSentiment(
        customer_id=customer_id,
        current_score=0.0,
        trend="stable",
        timeline=[],
    )


@app.post("/analyze", response_model=SentimentResult)
async def analyze(request: AnalyzeRequest) -> SentimentResult:
    """Analyze sentiment of a message or conversation."""
    return SentimentResult(
        score=0.0,
        label="neutral",
        escalation_risk=0.0,
        triggers=[],
    )


@app.get("/alerts", response_model=list[Alert])
async def get_alerts() -> list[Alert]:
    """Get active escalation risk alerts."""
    return []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
