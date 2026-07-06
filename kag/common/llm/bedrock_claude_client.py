import asyncio
import logging

import boto3

from kag.interface.common.llm_client import LLMClient
from kag.interface.solver.reporter_abc import do_report

logging.getLogger("botocore").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


@LLMClient.register("bedrock_claude")
class BedrockClaudeClient(LLMClient):
    """Anthropic Claude on Amazon Bedrock via the native Converse API (boto3).

    Anthropic models are not served over Bedrock's OpenAI-compatible endpoint, so
    this client uses ``bedrock-runtime`` ``converse`` / ``converse_stream``. The
    ``model`` is a Bedrock model id or inference-profile id (e.g. the EU profile
    ``eu.anthropic.claude-sonnet-4-6``, which keeps inference within EU regions).

    Text only: this covers the ingestion extractors and the retriever /
    deep_thought / kag_thinker generators. OpenAI-style function-calling (the
    ``tools`` path used only by the MCP executor) is not implemented here.
    """

    def __init__(
        self,
        region: str,
        model: str,
        temperature: float = 0.7,
        max_rate: float = 1000,
        time_period: float = 1,
        **kwargs,
    ):
        """Initialize the Bedrock Claude client.

        Args:
            region: AWS region to call Bedrock in (e.g. "eu-west-2").
            model: Bedrock model id or inference-profile id for Claude.
            temperature: Sampling temperature.
            max_rate: Maximum number of requests allowed per time period.
            time_period: Length of the rate-limiting window in seconds.

        Auth uses boto3's standard AWS credential chain (SSO profile via
        ``aws sso login``, environment credentials, or an instance role).
        """
        name = kwargs.pop("name", None)
        if not name:
            name = f"bedrock_claude:{region}:{model}"
        super().__init__(name, max_rate, time_period, **kwargs)

        self.region = region
        self.model = model
        self.temperature = temperature
        self.client = boto3.client("bedrock-runtime", region_name=region)

        self.check()
        logger.debug(
            f"Initialize BedrockClaudeClient with rate limit {max_rate} every {time_period}s"
        )

    def _inference_config(self) -> dict:
        return {"maxTokens": self.max_tokens, "temperature": self.temperature}

    def _build_converse(self, prompt: str, image_url: str, messages):
        """Map a prompt or OpenAI-style messages to Converse (system, messages).

        Converse separates the system prompt from the turn list; user/assistant
        turns carry a list of content blocks. We support text content only.
        """
        if image_url:
            raise NotImplementedError(
                "bedrock_claude is text-only; image_url is not supported."
            )
        if messages:
            system: list = []
            turns: list = []
            for message in messages:
                role = message.get("role")
                content = message.get("content")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict)
                    )
                if role == "system":
                    system.append({"text": content})
                else:
                    turns.append({"role": role, "content": [{"text": content}]})
            if not system:
                system = [{"text": "you are a helpful assistant"}]
            return system, turns
        return (
            [{"text": "you are a helpful assistant"}],
            [{"role": "user", "content": [{"text": prompt}]}],
        )

    @staticmethod
    def _extract_text(response: dict) -> str:
        blocks = response["output"]["message"]["content"]
        return "".join(block.get("text", "") for block in blocks if "text" in block)

    def _meter(self, token_meter, usage: dict) -> None:
        token_meter.update(
            usage.get("outputTokens", 0),
            usage.get("inputTokens", 0),
            usage.get("totalTokens", 0),
        )

    def __call__(self, prompt: str = "", image_url: str = None, **kwargs):
        """Run a synchronous Converse request and return the text response."""
        if kwargs.get("tools"):
            raise NotImplementedError(
                "bedrock_claude does not implement OpenAI-style function-calling; "
                "the MCP tool path is unsupported. Use the text pipelines."
            )
        system, messages = self._build_converse(
            prompt, image_url, kwargs.get("messages")
        )
        token_meter = LLMClient.get_token_meter()
        response = self.client.converse(
            modelId=self.model,
            messages=messages,
            system=system,
            inferenceConfig=self._inference_config(),
        )
        self._meter(token_meter, response.get("usage", {}))
        text = self._extract_text(response)
        do_report(text, "FINISH", **kwargs)
        return text

    async def acall(self, prompt: str = "", image_url: str = None, **kwargs):
        """Async wrapper: boto3 is synchronous, so run the call off the loop.

        ``asyncio.to_thread`` propagates the current context, so the per-document
        token-meter task id set by callers is preserved inside the worker thread.
        """
        return await asyncio.to_thread(self.__call__, prompt, image_url, **kwargs)

    async def astream(self, prompt: str = "", image_url: str = None, **kwargs):
        """Stream text deltas via Converse streaming, bridging boto3's sync stream.

        boto3's ``converse_stream`` yields a synchronous event iterator; we drain
        it on a worker thread and hand deltas back to the event loop through an
        ``asyncio.Queue``. Token usage arrives on the final ``metadata`` event.

        Yields:
            str: The next text delta from the model.
        """
        if kwargs.get("tools"):
            raise NotImplementedError(
                "bedrock_claude does not implement OpenAI-style function-calling."
            )
        system, messages = self._build_converse(
            prompt, image_url, kwargs.get("messages")
        )
        token_meter = LLMClient.get_token_meter()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _drain() -> None:
            try:
                response = self.client.converse_stream(
                    modelId=self.model,
                    messages=messages,
                    system=system,
                    inferenceConfig=self._inference_config(),
                )
                for event in response["stream"]:
                    if "contentBlockDelta" in event:
                        text = event["contentBlockDelta"]["delta"].get("text")
                        if text:
                            loop.call_soon_threadsafe(queue.put_nowait, ("delta", text))
                    elif "metadata" in event:
                        usage = event["metadata"].get("usage")
                        if usage:
                            loop.call_soon_threadsafe(queue.put_nowait, ("usage", usage))
            except Exception as err:  # surface to the consumer
                loop.call_soon_threadsafe(queue.put_nowait, ("error", err))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        future = loop.run_in_executor(None, _drain)
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "delta":
                    yield payload
                elif kind == "usage":
                    self._meter(token_meter, payload)
                elif kind == "error":
                    raise payload
                else:  # done
                    break
        finally:
            await future
