"""Agent loop tests with a scripted fake client: no LLM calls, no API key."""

from datetime import datetime
from typing import Any

from google.genai import errors, types

from emporio_agent import config
from emporio_agent.agent.agent import FALLBACK_REPLY, Agent
from emporio_agent.agent.prompts import build_system_prompt
from emporio_agent.tools.registry import ToolRegistry

STORE_NOW = datetime(2026, 3, 25, 10, 30, tzinfo=config.STORE_TIMEZONE)


class FakeModels:
    """Returns scripted responses and records what the agent sent."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.sent_contents: list[list[types.Content]] = []

    def generate_content(
        self, model: str, contents: list[types.Content], config: Any
    ) -> types.GenerateContentResponse:
        self.sent_contents.append(list(contents))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.models = FakeModels(responses)


def text_response(text: str) -> types.GenerateContentResponse:
    part = types.Part.from_text(text=text)
    return model_response(part)


def tool_call_response(name: str, **args: Any) -> types.GenerateContentResponse:
    part = types.Part.from_function_call(name=name, args=args)
    return model_response(part)


def model_response(part: types.Part) -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def make_agent(client: FakeClient, tool_registry: ToolRegistry) -> Agent:
    return Agent(client, tool_registry, clock=lambda: STORE_NOW)  # type: ignore[arg-type]


def test_plain_answer_without_tools(tool_registry: ToolRegistry) -> None:
    client = FakeClient([text_response("Oi! Como posso ajudar?")])
    agent = make_agent(client, tool_registry)
    reply = agent.send("Oi")
    assert reply.text == "Oi! Como posso ajudar?"
    assert reply.tool_calls == []
    assert [content.role for content in agent.history] == ["user", "model"]


def test_tool_call_runs_and_result_goes_back_to_the_model(
    tool_registry: ToolRegistry,
) -> None:
    client = FakeClient(
        [
            tool_call_response("search_policies", query="horário"),
            text_response("Abrimos às 9h."),
        ]
    )
    reply = make_agent(client, tool_registry).send("Que horas abre?")

    assert reply.text == "Abrimos às 9h."
    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call.name == "search_policies"
    assert call.arguments == {"query": "horário"}
    assert "Horário de Funcionamento" in call.result_summary

    # Second model call: user message, model's tool call, tool result.
    tool_message = client.models.sent_contents[1][-1]
    assert tool_message.role == "user"
    assert tool_message.parts is not None
    tool_result = tool_message.parts[0].function_response
    assert tool_result is not None and tool_result.response is not None
    assert tool_result.name == "search_policies"
    assert tool_result.response["found"] is True


def test_unknown_tool_returns_an_error_to_the_model(
    tool_registry: ToolRegistry,
) -> None:
    client = FakeClient(
        [tool_call_response("delete_everything"), text_response("Não consigo.")]
    )
    reply = make_agent(client, tool_registry).send("Apaga tudo")
    assert reply.text == "Não consigo."
    assert "Unknown tool" in reply.tool_calls[0].result_summary


def test_bad_tool_arguments_do_not_crash_the_agent(
    tool_registry: ToolRegistry,
) -> None:
    client = FakeClient(
        [
            tool_call_response("search_policies", wrong_argument="x"),
            text_response("Pode repetir?"),
        ]
    )
    reply = make_agent(client, tool_registry).send("?")
    assert reply.text == "Pode repetir?"
    assert "could not run" in reply.tool_calls[0].result_summary


def test_endless_tool_loop_stops_with_fallback(tool_registry: ToolRegistry) -> None:
    responses = [
        tool_call_response("search_policies", query="x")
        for _ in range(config.MAX_TOOL_ROUNDS)
    ]
    client = FakeClient(responses)
    agent = make_agent(client, tool_registry)
    reply = agent.send("?")
    assert reply.text == FALLBACK_REPLY
    assert len(client.models.sent_contents) == config.MAX_TOOL_ROUNDS
    # History keeps only the customer's message and the fallback.
    assert [content.role for content in agent.history] == ["user", "model"]


def test_api_error_returns_fallback(tool_registry: ToolRegistry) -> None:
    error = errors.APIError(503, {"error": {"message": "high demand"}})
    agent = make_agent(FakeClient([error]), tool_registry)
    assert agent.send("Oi").text == FALLBACK_REPLY


def test_history_is_sent_on_the_next_turn(tool_registry: ToolRegistry) -> None:
    client = FakeClient([text_response("Oi!"), text_response("Tudo bem.")])
    agent = make_agent(client, tool_registry)
    agent.send("Oi")
    agent.send("Tudo bem?")
    second_turn = client.models.sent_contents[1]
    assert [content.role for content in second_turn] == ["user", "model", "user"]


def test_system_prompt_has_the_current_date_and_weekday() -> None:
    prompt = build_system_prompt(datetime(2026, 3, 25, 10, 30))
    assert "quarta-feira, 25/03/2026, 10:30" in prompt
