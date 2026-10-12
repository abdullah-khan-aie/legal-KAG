import asyncio
import contextlib
import copy
import logging
import weakref

from anthropic import Anthropic, AsyncAnthropic
from pydantic import ValidationError

from kag.interface.common.llm_client import LLMClient
from kag.interface.solver.reporter_abc import do_report

logger = logging.getLogger(__name__)


def _obs():
    """Import the app's tracing helpers, or None if the app layer is absent.

    Kept lazy so the vendored kag tree stays importable on its own.
    """
    try:
        from src.observability import tracing as o

        return o
    except Exception:
        return None


# Lets short-lived scripts close their httpx sessions on the running loop,
# instead of warning about unclosed sessions at interpreter shutdown.
_ASYNC_CLIENTS: weakref.WeakSet = weakref.WeakSet()


async def aclose_all_anthropic_clients() -> None:
    """Close every live AnthropicLLMClient's async (httpx) session."""
    for client in list(_ASYNC_CLIENTS):
        await client.aclose()


def _unwrap_secret(value):
    """Return the plaintext of a SecretStr, or the value unchanged."""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


@LLMClient.register("anthropic")
class AnthropicLLMClient(LLMClient):
    """Claude via Anthropic's Messages API.

    Async methods carry the pipelines; the sync ones serve the few blocking call
    sites left in the solver. Text only, so use structured_output for schemas.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_rate: float = 1000,
        time_period: float = 1,
        **kwargs,
    ):
        """Initialize the client for one Anthropic model id.

        api_key arrives through kwargs so a SecretStr survives the component
        registry unstringified. Unset falls back to ANTHROPIC_API_KEY.
        """
        name = kwargs.pop("name", None)
        api_key = _unwrap_secret(kwargs.pop("api_key", None))
        if not name:
            name = f"anthropic:{model}"
        super().__init__(name, max_rate, time_period, **kwargs)

        self.model = model
        self.temperature = temperature
        self._api_key = api_key
        # Both are lazy: a pure-async process never opens a sync pool, and httpx's
        # async transport binds to the loop, so it must be built inside one.
        self._client: Anthropic | None = None
        self._aclient: AsyncAnthropic | None = None
        self._aclient_lock = asyncio.Lock()
        _ASYNC_CLIENTS.add(self)

        self.check()
        logger.debug(
            f"Initialize AnthropicLLMClient model={model} rate limit {max_rate} every {time_period}s"
        )

    def _build_messages(self, prompt: str, image_url: str, messages):
        """Map a prompt or OpenAI-style messages to Anthropic (system, messages).

        The Messages API separates the system prompt from the turn list; each turn
        carries text content. We support text content only.
        """
        if image_url:
            raise NotImplementedError("anthropic client is text-only; image_url is not supported.")
        if messages:
            system_parts: list[str] = []
            turns: list[dict] = []
            for message in messages:
                role = message.get("role")
                content = message.get("content")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "") for part in content if isinstance(part, dict)
                    )
                if role == "system":
                    if content:
                        system_parts.append(content)
                else:
                    turns.append({"role": role, "content": content or ""})
            system = "\n\n".join(system_parts)
            return system, turns
        return "", [{"role": "user", "content": prompt}]

    def _create_kwargs(self, system: str, messages: list, **extra) -> dict:
        """Common Messages.create arguments (system omitted when empty)."""
        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        payload.update(extra)
        return payload

    @staticmethod
    def _extract_text(message) -> str:
        return "".join(block.text for block in message.content if block.type == "text")

    @staticmethod
    def _meter(token_meter, usage) -> None:
        if usage is None:
            return
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        token_meter.update(output_tokens, input_tokens, input_tokens + output_tokens)

    def _get_client(self) -> Anthropic:
        """Return the shared sync client, created on first blocking use."""
        if self._client is None:
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    async def _aget_client(self) -> AsyncAnthropic:
        """Return the shared async client, created lazily on the running loop."""
        if self._aclient is None:
            async with self._aclient_lock:
                if self._aclient is None:
                    self._aclient = AsyncAnthropic(api_key=self._api_key)
        return self._aclient

    async def aclose(self) -> None:
        """Close the lazily-created async (httpx) client, if one was opened."""
        if self._aclient is not None:
            try:
                await self._aclient.close()
            except Exception:  # best-effort cleanup
                pass
            finally:
                self._aclient = None

    def __call__(self, prompt: str = "", image_url: str = None, **kwargs):
        """Run a synchronous Messages request and return the text response."""
        if kwargs.get("tools"):
            raise NotImplementedError(
                "anthropic client does not implement OpenAI-style function-calling; "
                "the MCP tool path is unsupported. Use the text pipelines."
            )
        system, messages = self._build_messages(prompt, image_url, kwargs.get("messages"))
        token_meter = LLMClient.get_token_meter()
        message = self._get_client().messages.create(**self._create_kwargs(system, messages))
        self._meter(token_meter, message.usage)
        text = self._extract_text(message)
        do_report(text, "FINISH", **kwargs)
        return text

    async def acall(self, prompt: str = "", image_url: str = None, **kwargs):
        """Async Messages request over AsyncAnthropic (native async, no worker thread)."""
        if kwargs.get("tools"):
            raise NotImplementedError(
                "anthropic client does not implement OpenAI-style function-calling."
            )
        system, messages = self._build_messages(prompt, image_url, kwargs.get("messages"))
        token_meter = LLMClient.get_token_meter()
        client = await self._aget_client()
        # Records tokens and cost against whichever span is currently active.
        o = _obs()
        gen_cm = o.span("anthropic.messages", as_type="generation", model=self.model) if o else None
        with gen_cm if gen_cm is not None else contextlib.nullcontext() as gen:
            message = await client.messages.create(**self._create_kwargs(system, messages))
            usage = message.usage
            self._meter(token_meter, usage)
            text = self._extract_text(message)
            if o is not None and gen is not None:
                o.record_generation_usage(
                    gen,
                    model=self.model,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    output=text,
                )
        do_report(text, "FINISH", **kwargs)
        return text

    async def astream(self, prompt: str = "", image_url: str = None, **kwargs):
        """Yield text deltas as the model produces them.

        Token usage only arrives on the accumulated final message, so it is read
        after the stream is drained.
        """
        if kwargs.get("tools"):
            raise NotImplementedError(
                "anthropic client does not implement OpenAI-style function-calling."
            )
        system, messages = self._build_messages(prompt, image_url, kwargs.get("messages"))
        token_meter = LLMClient.get_token_meter()
        client = await self._aget_client()
        o = _obs()
        gen_cm = o.span("anthropic.stream", as_type="generation", model=self.model) if o else None
        with gen_cm if gen_cm is not None else contextlib.nullcontext() as gen:
            text_parts: list[str] = []
            async with client.messages.stream(**self._create_kwargs(system, messages)) as stream:
                async for text in stream.text_stream:
                    if text:
                        text_parts.append(text)
                        yield text
                final = await stream.get_final_message()
            usage = final.usage
            self._meter(token_meter, usage)
            if o is not None and gen is not None:
                o.record_generation_usage(
                    gen,
                    model=self.model,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    output="".join(text_parts),
                )

    # Claude has no response_format, so schema-validated output is done by
    # forcing a tool call: expose the pydantic schema as a tool, make the model
    # call it, validate the JSON, and feed any error back for one retry.
    @staticmethod
    def _inline_defs(schema: dict) -> dict:
        """Inline $ref and $defs into a self-contained JSON schema.

        Pydantic nests models by reference, which the tool input_schema may reject.
        """
        defs = schema.get("$defs") or schema.get("definitions") or {}

        def resolve(node):
            if isinstance(node, dict):
                if "$ref" in node:
                    ref = node["$ref"].split("/")[-1]
                    target = copy.deepcopy(defs.get(ref, {}))
                    for k, v in node.items():
                        if k != "$ref":
                            target[k] = v
                    return resolve(target)
                return {k: resolve(v) for k, v in node.items() if k not in ("$defs", "definitions")}
            if isinstance(node, list):
                return [resolve(item) for item in node]
            return node

        return resolve(schema)

    @classmethod
    def _build_tool(cls, schema):
        schema_name = getattr(schema, "__name__", "Result")
        tool_name = f"record_{schema_name.lower()}"
        tool = {
            "name": tool_name,
            "description": (
                f"Record the answer as a {schema_name} object. Call this tool "
                "exactly once with every field filled in."
            ),
            "input_schema": cls._inline_defs(schema.model_json_schema()),
        }
        return tool_name, [tool], {"type": "tool", "name": tool_name}

    @staticmethod
    def _extract_tool_input(message, tool_name: str) -> dict:
        for block in message.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        for block in message.content:  # fall back to any tool call
            if block.type == "tool_use":
                return block.input
        raise ValueError("model returned no tool call for structured output")

    @staticmethod
    def _append_correction(turns: list, error: Exception) -> list:
        # Appended to the last user turn rather than added as a new one, because
        # the Messages API requires alternating roles.
        turns = copy.deepcopy(turns)
        turns[-1]["content"] += (
            f"\n\nYour previous result failed schema validation with:\n{error}\n"
            "Return a corrected result that fully satisfies the schema."
        )
        return turns

    def structured_output(self, schema, prompt: str = "", *, max_retries: int = 2, **kwargs):
        """Force a schema-validated response via Anthropic tool-use (sync)."""
        system, turns = self._build_messages(prompt, None, kwargs.get("messages"))
        tool_name, tools, tool_choice = self._build_tool(schema)
        token_meter = LLMClient.get_token_meter()
        client = self._get_client()
        attempt_turns, last_error = turns, None
        for _ in range(max(1, max_retries)):
            message = client.messages.create(
                **self._create_kwargs(system, attempt_turns, tools=tools, tool_choice=tool_choice)
            )
            self._meter(token_meter, message.usage)
            tool_input = self._extract_tool_input(message, tool_name)
            try:
                return schema.model_validate(tool_input)
            except ValidationError as error:
                last_error = error
                attempt_turns = self._append_correction(turns, error)
        raise RuntimeError(
            f"structured_output could not satisfy {schema.__name__} after "
            f"{max_retries} attempts: {last_error}"
        )

    async def astructured_output(self, schema, prompt: str = "", *, max_retries: int = 2, **kwargs):
        """Force a schema-validated response via Anthropic tool-use (async)."""
        system, turns = self._build_messages(prompt, None, kwargs.get("messages"))
        tool_name, tools, tool_choice = self._build_tool(schema)
        token_meter = LLMClient.get_token_meter()
        client = await self._aget_client()
        o = _obs()
        gen_cm = o.span("anthropic.tool", as_type="generation", model=self.model) if o else None
        attempt_turns, last_error = turns, None
        for _ in range(max(1, max_retries)):
            with gen_cm if gen_cm is not None else contextlib.nullcontext() as gen:
                message = await client.messages.create(
                    **self._create_kwargs(
                        system, attempt_turns, tools=tools, tool_choice=tool_choice
                    )
                )
                usage = message.usage
                self._meter(token_meter, usage)
                if o is not None and gen is not None:
                    o.record_generation_usage(
                        gen,
                        model=self.model,
                        input_tokens=getattr(usage, "input_tokens", None),
                        output_tokens=getattr(usage, "output_tokens", None),
                    )
            tool_input = self._extract_tool_input(message, tool_name)
            try:
                return schema.model_validate(tool_input)
            except ValidationError as error:
                last_error = error
                attempt_turns = self._append_correction(turns, error)
        raise RuntimeError(
            f"structured_output could not satisfy {schema.__name__} after "
            f"{max_retries} attempts: {last_error}"
        )
