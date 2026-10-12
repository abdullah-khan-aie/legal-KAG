from __future__ import annotations

from collections.abc import AsyncIterable

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from src.api.schemas import ChatTitleRequest, ChatTitleResponse, QueryRequest
from src.application.query.chat_title import generate_chat_title
from src.application.query.streaming import stream_query_events
from src.config import get_settings

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/chat-title", response_model=ChatTitleResponse)
async def chat_title(request: ChatTitleRequest) -> ChatTitleResponse:
    """Generate a short sidebar title for a chat from its messages."""
    settings = get_settings()
    title = await generate_chat_title(
        [msg.model_dump() for msg in request.messages],
        settings,
    )
    return ChatTitleResponse(title=title)


@router.post("/stream", response_class=EventSourceResponse)
async def query_stream(request: QueryRequest) -> AsyncIterable[ServerSentEvent]:
    """Answer a query over Server-Sent Events.

    Event types: step for progress, token for an answer delta, answer for the
    final text, done as the end sentinel, and error on failure.
    """
    async for event in stream_query_events(request.query, request.pipeline.value):
        segment = event["segment"]
        status = event.get("status")
        content = event.get("content")

        if segment == "answer" and status == "RUNNING":
            yield ServerSentEvent(data={"delta": content}, event="token")
        elif segment == "answer":
            # The full answer is delivered by the terminal "done" handling below.
            continue
        elif segment == "done":
            yield ServerSentEvent(data={"answer": content}, event="answer")
            yield ServerSentEvent(raw_data="[DONE]", event="done")
        elif segment == "error":
            yield ServerSentEvent(data={"error": content}, event="error")
        else:
            step: dict = {"stage": segment, "label": event.get("tag"), "status": status}
            if isinstance(content, str):
                step["content"] = content
            yield ServerSentEvent(data=step, event="step")
