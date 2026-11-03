"""The agent: conversation history plus an explicit function-calling loop.

Each turn sends the system prompt, the history and the new message, with the
tool declarations. While the model asks for tools, they run in Python and
their results go back to the model. The turn ends with a text answer, or with
a polite fallback after MAX_TOOL_ROUNDS model calls.

The loop is written by hand (no agent framework) so every tool call is visible:
it is logged and returned with the reply for the UI and the examples.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google import genai
from google.genai import errors, types

from emporio_agent import config
from emporio_agent.agent.prompts import build_system_prompt
from emporio_agent.data.policies import PolicySection
from emporio_agent.data.store_data import StoreData
from emporio_agent.tools import build_tool_registry
from emporio_agent.tools.common import ToolResult
from emporio_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Poxa, não consegui concluir sua consulta agora. Pode tentar de novo em "
    "instantes? Se preferir, nossa equipe também pode te ajudar pelos canais "
    "de atendimento da loja."
)
SUMMARY_MAX_CHARS = 300
# Retry only server-side errors. Not 429: on the free tier it usually means
# the daily quota is used up, and retrying would only burn more requests.
RETRY_STATUS_CODES = [500, 502, 503, 504]
RETRY_MAX_DELAY_SECONDS = 10.0


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call made during a turn, shown in the UI and the examples."""

    name: str
    arguments: dict[str, Any]
    result_summary: str


@dataclass(frozen=True)
class AgentReply:
    """The agent's answer to one message, plus the tools it used."""

    text: str
    tool_calls: list[ToolCallRecord]


class Agent:
    """One customer conversation: owns the history and runs the tool loop.

    Create one instance per conversation (the UI keeps one per browser
    session), so histories never leak between customers.
    """

    def __init__(
        self,
        client: genai.Client,
        tools: ToolRegistry,
        model: str = config.GEMINI_MODEL,
        clock: Callable[[], datetime] = config.get_store_now,
    ) -> None:
        self.client = client
        self.tools = tools
        self.model = model
        self.clock = clock
        self.history: list[types.Content] = []

    def send(self, user_message: str) -> AgentReply:
        """Answer one customer message, calling tools as the model asks."""
        contents = [*self.history, text_content("user", user_message)]
        tool_calls: list[ToolCallRecord] = []
        try:
            answer = self._run_loop(contents, tool_calls)
        except errors.APIError as error:
            logger.error("Gemini API error: %s", error)
            answer = None
        if answer is None:
            # Keep a clean history: the customer's message and the fallback.
            contents = [
                *self.history,
                text_content("user", user_message),
                text_content("model", FALLBACK_REPLY),
            ]
            answer = FALLBACK_REPLY
        self.history = contents
        return AgentReply(text=answer, tool_calls=tool_calls)

    def _run_loop(
        self, contents: list[types.Content], tool_calls: list[ToolCallRecord]
    ) -> str | None:
        """Call the model until it answers with text; None if it never does.

        `contents` grows in place with the model's messages and tool results.
        The model's own message is sent back unchanged, which keeps the
        "thought signatures" that Gemini needs between calls.
        """
        generation_config = self._generation_config()
        for _ in range(config.MAX_TOOL_ROUNDS):
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=generation_config
            )
            if not response.candidates or response.candidates[0].content is None:
                logger.warning("Model returned no content")
                return None
            contents.append(response.candidates[0].content)
            if not response.function_calls:
                return response.text or None
            contents.append(self._run_tool_calls(response.function_calls, tool_calls))
        logger.warning("No answer after %d model calls", config.MAX_TOOL_ROUNDS)
        return None

    def _generation_config(self) -> types.GenerateContentConfig:
        """Prompt with the current date, tools and sampling settings."""
        return types.GenerateContentConfig(
            system_instruction=build_system_prompt(self.clock()),
            # The SDK builds each tool declaration from the function's
            # signature and docstring.
            tools=list(self.tools.values()),
            temperature=config.GEMINI_TEMPERATURE,
            # We run the tools ourselves, so each call can be logged and shown.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

    def _run_tool_calls(
        self,
        function_calls: list[types.FunctionCall],
        tool_calls: list[ToolCallRecord],
    ) -> types.Content:
        """Run each requested tool and package the results for the model."""
        parts = []
        for call in function_calls:
            name = call.name or ""
            arguments = dict(call.args or {})
            result = self._dispatch(name, arguments)
            summary = summarize(result)
            logger.info("Tool %s(%s) -> %s", name, arguments, summary)
            tool_calls.append(ToolCallRecord(name, arguments, summary))
            parts.append(types.Part.from_function_response(name=name, response=result))
        # The Gemini API expects tool results in a "user" turn ("tool" is
        # rejected with 400 INVALID_ARGUMENT).
        return types.Content(role="user", parts=parts)

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run one tool. Failures become {"error": ...} so the model can recover."""
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return tool(**arguments)
        except (TypeError, ValueError, KeyError) as error:
            logger.exception("Tool %s failed", name)
            return {"error": f"The tool could not run: {error}"}


def create_agent(
    data: StoreData,
    policy_sections: list[PolicySection],
    clock: Callable[[], datetime] = config.get_store_now,
) -> Agent:
    """Build an agent over already-loaded data. Fails fast without an API key.

    Transient server errors (such as 503 "high demand") are retried by the
    SDK with exponential backoff before the agent falls back. `clock` is
    "now" for both the prompt and the tools (the example script fixes it).
    """
    retry_options = types.HttpRetryOptions(
        attempts=config.GEMINI_RETRY_ATTEMPTS,
        max_delay=RETRY_MAX_DELAY_SECONDS,
        http_status_codes=RETRY_STATUS_CODES,
    )
    client = genai.Client(
        api_key=config.require_api_key(),
        http_options=types.HttpOptions(retry_options=retry_options),
    )
    tools = build_tool_registry(data, policy_sections, clock)
    return Agent(client, tools, clock=clock)


def text_content(role: str, text: str) -> types.Content:
    """A plain text message from the user or the model."""
    return types.Content(role=role, parts=[types.Part.from_text(text=text)])


def summarize(result: ToolResult) -> str:
    """Short, single-line view of a tool result for logs and the UI."""
    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= SUMMARY_MAX_CHARS:
        return text
    return text[: SUMMARY_MAX_CHARS - 3] + "..."
