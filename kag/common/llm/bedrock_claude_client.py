import asyncio
import logging

import aioboto3
import boto3
from botocore.config import Config

from kag.interface.common.llm_client import LLMClient
from kag.interface.solver.reporter_abc import do_report

logging.getLogger("botocore").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def _unwrap_secret(value):
    """Return the plaintext of a SecretStr, or the value unchanged."""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


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

        Optional ``aws_access_key_id`` / ``aws_secret_access_key`` (plain str or
        SecretStr, passed via kwargs) make Bedrock use those credentials
        explicitly instead of boto3's default chain. They are accepted as kwargs
        (not typed params) so a SecretStr passes through the component registry
        unstringified and stays masked in logs. With none, auth falls back to the
        standard chain (environment, profile, or instance role).
        """
        name = kwargs.pop("name", None)
        aws_access_key_id = _unwrap_secret(kwargs.pop("aws_access_key_id", None))
        aws_secret_access_key = _unwrap_secret(kwargs.pop("aws_secret_access_key", None))
        if not name:
            name = f"bedrock_claude:{region}:{model}"
        super().__init__(name, max_rate, time_period, **kwargs)

        self.region = region
        self.model = model
        self.temperature = temperature
        # Explicit Bedrock credentials (when supplied) take precedence over the
        # environment/instance-role chain, so Bedrock uses a scoped IAM user while
        # the infra credentials in the environment stay for Secrets Manager etc.
        self._credentials = {}
        if aws_access_key_id and aws_secret_access_key:
            self._credentials = {
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            }
        # Adaptive retry backs off and retries on ThrottlingException instead of
        # failing. boto3 defaults to max_pool_connections=10; raise it well above
        # the target in-flight concurrency so the connection pool is never the
        # bottleneck (each schema extraction task peaks at ~2 concurrent calls, so
        # model_execute_num=100 => ~200 in flight).
        self._config = Config(
            retries={"mode": "adaptive", "total_max_attempts": 10},
            max_pool_connections=256,
        )
        # Sync client for the blocking ``invoke`` path.
        self.client = boto3.client(
            "bedrock-runtime", region_name=region, config=self._config, **self._credentials
        )
        # Async client (aioboto3) for acall / astream: native async I/O, no thread
        # bridge. Created lazily on first use inside the running loop, then reused
        # for the life of the process.
        self._session = aioboto3.Session(**self._credentials)
        self._aclient = None
        self._aclient_cm = None
        self._aclient_lock = asyncio.Lock()

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
            raise NotImplementedError("bedrock_claude is text-only; image_url is not supported.")
        if messages:
            system: list = []
            turns: list = []
            for message in messages:
                role = message.get("role")
                content = message.get("content")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "") for part in content if isinstance(part, dict)
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

    @staticmethod
    def _meter(token_meter, usage: dict) -> None:
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
        system, messages = self._build_converse(prompt, image_url, kwargs.get("messages"))
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

    async def _aget_client(self):
        """Return the shared aioboto3 client, creating it on first use.

        aioboto3 clients are async context managers bound to the running loop, so
        we enter the context once (lazily) and reuse the client for the process.
        """
        if self._aclient is None:
            async with self._aclient_lock:
                if self._aclient is None:
                    self._aclient_cm = self._session.client(
                        "bedrock-runtime", region_name=self.region, config=self._config
                    )
                    self._aclient = await self._aclient_cm.__aenter__()
        return self._aclient

    async def acall(self, prompt: str = "", image_url: str = None, **kwargs):
        """Async Converse request over aioboto3 (native async, no worker thread)."""
        if kwargs.get("tools"):
            raise NotImplementedError(
                "bedrock_claude does not implement OpenAI-style function-calling."
            )
        system, messages = self._build_converse(prompt, image_url, kwargs.get("messages"))
        token_meter = LLMClient.get_token_meter()
        client = await self._aget_client()
        response = await client.converse(
            modelId=self.model,
            messages=messages,
            system=system,
            inferenceConfig=self._inference_config(),
        )
        self._meter(token_meter, response.get("usage", {}))
        text = self._extract_text(response)
        do_report(text, "FINISH", **kwargs)
        return text

    async def astream(self, prompt: str = "", image_url: str = None, **kwargs):
        """Stream text deltas via Converse streaming over aioboto3.

        ``converse_stream`` returns an async event iterator, so deltas are yielded
        directly -- no worker thread or bridging queue. Token usage arrives on the
        final ``metadata`` event.

        Yields:
            str: The next text delta from the model.
        """
        if kwargs.get("tools"):
            raise NotImplementedError(
                "bedrock_claude does not implement OpenAI-style function-calling."
            )
        system, messages = self._build_converse(prompt, image_url, kwargs.get("messages"))
        token_meter = LLMClient.get_token_meter()
        client = await self._aget_client()
        response = await client.converse_stream(
            modelId=self.model,
            messages=messages,
            system=system,
            inferenceConfig=self._inference_config(),
        )
        async for event in response["stream"]:
            if "contentBlockDelta" in event:
                text = event["contentBlockDelta"]["delta"].get("text")
                if text:
                    yield text
            elif "metadata" in event:
                usage = event["metadata"].get("usage")
                if usage:
                    self._meter(token_meter, usage)
