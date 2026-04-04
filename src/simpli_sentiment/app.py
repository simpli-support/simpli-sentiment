"""FastAPI application."""

import json as json_module
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import litellm
import structlog
from fastapi import File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from simpli_core import Channel, CostTracker, create_app
from simpli_core.connectors import (
    FieldMapping,
    FileConnector,
    SalesforceConnector,
    apply_mappings,
)
from simpli_core.connectors.mapping import CASE_TO_TICKET

from simpli_sentiment.settings import settings

cost_tracker = CostTracker()
logger = structlog.get_logger()

app = create_app(
    title="Simpli Sentiment",
    version="0.1.0",
    description="Customer health and sentiment tracker with escalation risk detection",
    settings=settings,
    cors_origins="*",
    cost_tracker=cost_tracker,
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
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$",
        description="Unique customer identifier (alphanumeric, hyphens, underscores).",
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Message or conversation text to analyze.",
    )
    channel: Channel | None = Field(
        default=None, description="Communication channel the message originated from."
    )


class SentimentResult(BaseModel):
    score: float = Field(
        description="Sentiment score from -1.0 (very negative) to 1.0 (very positive)."
    )
    label: str = Field(description="Sentiment label: positive, negative, or neutral.")
    escalation_risk: float = Field(description="Escalation risk score from 0.0 to 1.0.")
    triggers: list[str] = Field(
        description="Keywords or phrases that indicate escalation risk."
    )


class SentimentTimepoint(BaseModel):
    timestamp: str = Field(description="ISO 8601 timestamp of this data point.")
    score: float = Field(description="Sentiment score at this point in time.")
    label: str = Field(description="Sentiment label at this point in time.")
    source: str = Field(description="Source channel or origin of the analyzed message.")


class CustomerSentiment(BaseModel):
    customer_id: str = Field(description="Unique customer identifier.")
    current_score: float = Field(
        description="Most recent sentiment score for this customer."
    )
    trend: str = Field(description="Sentiment trend: improving, declining, or stable.")
    timeline: list[SentimentTimepoint] = Field(
        description="Chronological sentiment data points."
    )


class Alert(BaseModel):
    id: str = Field(description="Unique alert identifier.")
    customer_id: str = Field(description="Customer who triggered the alert.")
    severity: str = Field(description="Alert severity level: low, medium, or high.")
    reason: str = Field(
        description="Human-readable explanation of why the alert was raised."
    )
    created_at: str = Field(
        description="ISO 8601 timestamp when the alert was created."
    )


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable error message.")


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
    summary="Get sentiment timeline for a customer",
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
    summary="Analyze sentiment of a message or conversation",
)
async def analyze(request: AnalyzeRequest) -> SentimentResult:
    """Analyze sentiment of a message or conversation."""
    try:
        system_prompt = (
            "You are a sentiment analyzer for customer support messages. "
            "Analyze the emotional tone, frustration level, and escalation risk. "
            "Return JSON with exactly these keys:\n"
            '- "score": float from -1.0 (very negative) to 1.0 (very positive)\n'
            '- "label": one of "positive", "negative", or "neutral"\n'
            '- "escalation_risk": float from 0.0 (no risk) '
            "to 1.0 (certain escalation)\n"
            '- "triggers": list of specific phrases from the text that indicate '
            "escalation risk\n\n"
            "Consider tone, urgency, frustration, threats (cancellation, legal, "
            "social media), and implicit sentiment — not just keywords. "
            "ALL CAPS text indicates shouting/anger. "
            "Multiple exclamation marks indicate strong emotion.\n\n"
            "Return ONLY the JSON object."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.text},
        ]

        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=messages,
            temperature=0.1,
        )
        cost_tracker.record_from_response(settings.litellm_model, response)

        raw = response.choices[0].message.content.strip()

        # Try to extract JSON — handle fenced blocks or embedded JSON objects
        cleaned = raw
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1)
        else:
            brace_match = list(
                re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
            )
            if brace_match:
                cleaned = brace_match[-1].group(0)

        parsed = json_module.loads(cleaned)

        score = max(-1.0, min(1.0, float(parsed.get("score", 0.0))))
        label = parsed.get("label", _score_to_label(score))
        risk = max(0.0, min(1.0, float(parsed.get("escalation_risk", 0.0))))
        triggers = parsed.get("triggers", [])

    except Exception:
        logger.warning("llm_sentiment_failed, falling back to keyword analysis")
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
    summary="Get active escalation risk alerts",
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


# ---------------------------------------------------------------------------
# Ingest models
# ---------------------------------------------------------------------------


class SalesforceIngestRequest(BaseModel):
    instance_url: str = Field(
        default="", description="Salesforce instance URL; uses server default if empty."
    )
    client_id: str = Field(
        default="", description="OAuth2 client ID; uses server default if empty."
    )
    client_secret: str = Field(
        default="", description="OAuth2 client secret; uses server default if empty."
    )
    soql_where: str = Field(
        default="", description="Optional SOQL WHERE clause to filter records."
    )
    limit: int = Field(
        default=100, ge=1, le=10000, description="Maximum number of records to fetch."
    )
    mappings: list[FieldMapping] | None = Field(
        default=None,
        description="Custom field mappings; uses defaults if not provided.",
    )


class IngestResult(BaseModel):
    total: int = Field(description="Total number of records received.")
    processed: int = Field(description="Number of records successfully processed.")
    results: list[dict[str, Any]] = Field(description="Per-record processing results.")
    errors: list[dict[str, Any]] = Field(
        default_factory=list, description="Records that failed processing."
    )


# ---------------------------------------------------------------------------
# Ingest routes
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/ingest",
    response_model=IngestResult,
    tags=["ingest"],
    summary="Ingest messages from a file and analyze sentiment",
)
async def ingest_file(
    file: UploadFile = File(...),  # noqa: B008
    mappings: str | None = Form(default=None),
) -> IngestResult:
    """Ingest messages from a file and analyze sentiment for each one."""
    records = FileConnector.parse(file.file, format=_detect_format(file.filename))

    field_mappings: list[FieldMapping] | None = None
    if mappings:
        field_mappings = [FieldMapping(**m) for m in json_module.loads(mappings)]

    return await _process_records(records, field_mappings, apply_defaults=False)


@app.post(
    "/api/v1/ingest/salesforce",
    response_model=IngestResult,
    tags=["ingest"],
    summary="Ingest cases from Salesforce and analyze sentiment",
)
async def ingest_salesforce(request: SalesforceIngestRequest) -> IngestResult:
    """Pull case comments from Salesforce and analyze sentiment."""
    instance_url = request.instance_url or settings.salesforce_instance_url
    client_id = request.client_id or settings.salesforce_client_id
    client_secret = request.client_secret or settings.salesforce_client_secret

    if not all([instance_url, client_id, client_secret]):
        return JSONResponse(  # type: ignore[return-value]
            status_code=400,
            content={
                "detail": "Salesforce credentials required"
                " (instance_url, client_id, client_secret)"
            },
        )

    connector = SalesforceConnector(
        instance_url=instance_url,
        client_id=client_id,
        client_secret=client_secret,
    )
    records = connector.get_cases(where=request.soql_where, limit=request.limit)

    return await _process_records(records, request.mappings)


def _detect_format(filename: str | None) -> str:
    if not filename:
        return "csv"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
    return suffix if suffix in FileConnector.SUPPORTED_FORMATS else "csv"


async def _process_records(
    records: list[dict[str, Any]],
    custom_mappings: list[FieldMapping] | None,
    *,
    apply_defaults: bool = True,
) -> IngestResult:
    keep = settings.preserve_unmapped_fields
    if custom_mappings:
        mapped = apply_mappings(records, custom_mappings, preserve_unmapped=keep)
    elif apply_defaults:
        mapped = apply_mappings(records, CASE_TO_TICKET, preserve_unmapped=keep)
    else:
        mapped = records

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for i, record in enumerate(mapped):
        try:
            subject = record.get("subject", "")
            description = (
                record.get("description")
                or record.get("body")
                or record.get("content")
                or record.get("text")
                or ""
            )
            text = (
                f"Subject: {subject}\n\n{description}".strip()
                if subject and description
                else (description or subject or "")
            )
            customer_id = record.get(
                "author_id", record.get("customer_id", f"ingest-{i}")
            )
            req = AnalyzeRequest(customer_id=customer_id, text=text)
            result = await analyze(req)
            results.append(result.model_dump())
        except Exception as exc:
            errors.append({"index": i, "error": str(exc), "record": record})

    return IngestResult(
        total=len(records),
        processed=len(results),
        results=results,
        errors=errors,
    )
