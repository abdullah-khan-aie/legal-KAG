import json
import logging
import os

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.common import Input, Output, generate_hash_id
from kag.interface import ReaderABC

logger = logging.getLogger(__name__)


def _html_to_text(html: str) -> str:
    """Best-effort plain text from an HTML email body.

    Uses BeautifulSoup (already a dependency) when available; falls back to a
    naive tag strip so a parser hiccup never fails the whole document.
    """
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text(separator=" ").strip()
    except Exception:  # noqa: BLE001
        import re

        return re.sub(r"<[^>]+>", " ", html).strip()


@ReaderABC.register("email")
@ReaderABC.register("email_reader")
@ReaderABC.register("json")
class EmailReader(ReaderABC):
    """Read a Gmail-style email-thread ``.json`` file into one Chunk per message.

    The expected shape is ``{"id": ..., "messages": [ {subject, sender,
    toRecipients, date, plaintextBody, htmlBody, snippet}, ... ]}`` (a single
    bare message dict is also accepted). Each message becomes its own Chunk --
    the natural retrieval unit -- with a small header (Subject / From / To /
    Date) prepended so sender/recipient/date are searchable alongside the body.

    Body text prefers ``plaintextBody``; if absent it falls back to stripping
    ``htmlBody``, then to ``snippet``. Volatile ``labelIds`` (INBOX/UNREAD/...) are
    intentionally excluded -- they are mailbox state, not content.
    """

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Read the email-thread ``.json`` at ``data`` and return one Chunk per message.

        Args:
            data: Path to a ``.json`` email-thread file.

        Raises:
            ValueError: If the input is empty.
            FileNotFoundError: If the path is not an existing file.
            RuntimeError: If the file cannot be parsed as JSON.
        """
        if not data:
            raise ValueError("Input cannot be empty")
        if not isinstance(data, str) or not os.path.isfile(data):
            raise FileNotFoundError(f"email json file not found: {data}")

        basename, _ = os.path.splitext(os.path.basename(data))
        try:
            with open(data, encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as e:
            raise RuntimeError(f"Failed to read email json '{data}': {e}") from e

        # Accept either a thread ({"messages": [...]}) or a single message dict.
        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            messages = payload["messages"]
        elif isinstance(payload, dict):
            messages = [payload]
        elif isinstance(payload, list):
            messages = payload
        else:
            logger.info(f"unrecognised email json shape, skipping: {data}")
            return []

        chunks: list[Chunk] = []
        for idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            subject = str(msg.get("subject", "") or "").strip()
            sender = str(msg.get("sender", "") or "").strip()
            recipients = msg.get("toRecipients") or []
            if isinstance(recipients, str):
                recipients = [recipients]
            to = ", ".join(str(r) for r in recipients)
            date = str(msg.get("date", "") or "").strip()

            body = msg.get("plaintextBody") or _html_to_text(msg.get("htmlBody", "")) or ""
            body = str(body).strip()
            if not body:
                body = str(msg.get("snippet", "") or "").strip()

            # Nothing worth indexing (no subject and no body) -> skip.
            if not subject and not body:
                continue

            header = "\n".join(
                line
                for line in (
                    f"Subject: {subject}" if subject else "",
                    f"From: {sender}" if sender else "",
                    f"To: {to}" if to else "",
                    f"Date: {date}" if date else "",
                )
                if line
            )
            content = f"{header}\n\n{body}" if header else body

            msg_id = str(msg.get("id", "") or idx)
            chunks.append(
                Chunk(
                    id=generate_hash_id(f"{data}::{msg_id}"),
                    name=f"{basename} / {subject}" if subject else f"{basename} / message {idx}",
                    content=content,
                    type=ChunkTypeEnum.Text,
                )
            )

        if not chunks:
            logger.info(f"email json has no indexable messages, skipping: {data}")
        return chunks
