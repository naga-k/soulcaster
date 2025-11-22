"""FastAPI application for FeedbackAgent data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import FeedbackItem
from .store import add_feedback_item

app = FastAPI(
    title="FeedbackAgent Ingestion API",
    description="API for ingesting user feedback from multiple sources",
    version="0.1.0"
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "service": "feedbackagent-ingestion"}


@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem):
    """
    Ingest a feedback item from Reddit.

    This endpoint receives already-normalized Reddit posts from the reddit_poller.

    Args:
        item: FeedbackItem with Reddit post data

    Returns:
        Status response indicating success
    """
    add_feedback_item(item)
    return {"status": "ok", "id": str(item.id)}


@app.post("/ingest/sentry")
def ingest_sentry(payload: dict):
    """
    Ingest an error report from Sentry webhook.

    Parses Sentry's webhook payload and normalizes it into a FeedbackItem.
    Extracts exception type, message, and stack trace frames.

    Args:
        payload: Raw Sentry webhook payload

    Returns:
        Status response with created feedback item ID
    """
    try:
        event_id = payload.get("event_id")
        title = payload.get("message") or "Sentry Issue"

        # Construct body from exception data
        body = ""
        exception = payload.get("exception", {}).get("values", [])
        if exception:
            exc = exception[0]
            exc_type = exc.get("type", "Error")
            exc_value = exc.get("value", "")
            body += f"{exc_type}: {exc_value}\n\nStacktrace:\n"
            # Include first 3 stack frames for context
            for frame in exc.get("stacktrace", {}).get("frames", [])[:3]:
                body += f"  {frame.get('filename')}:{frame.get('lineno')}\n"

        item = FeedbackItem(
            id=uuid4(),
            source="sentry",
            external_id=event_id,
            title=title,
            body=body,
            metadata=payload,
            created_at=datetime.now(timezone.utc)
        )
        add_feedback_item(item)
        return {"status": "ok", "id": str(item.id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process Sentry payload: {str(e)}")


class ManualIngestRequest(BaseModel):
    """Request model for manual feedback submission."""
    text: str


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest):
    """
    Ingest manually submitted feedback text.

    Creates a FeedbackItem from raw text input. Title is truncated to 80 characters.

    Args:
        request: ManualIngestRequest containing the feedback text

    Returns:
        Status response with created feedback item ID
    """
    item = FeedbackItem(
        id=uuid4(),
        source="manual",
        title=request.text[:80],  # Truncate title to 80 chars
        body=request.text,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item)
    return {"status": "ok", "id": str(item.id)}
