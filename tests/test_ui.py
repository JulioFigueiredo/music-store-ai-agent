"""UI tests with Streamlit's AppTest: no browser, no LLM calls.

The agent is replaced by a fake that returns a scripted reply, so these tests
check only what the interface draws.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from emporio_agent import config
from emporio_agent.agent import AgentReply, ToolCallRecord
from emporio_agent.ui import session

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


class FakeAgent:
    """Stands in for Agent: answers with a fixed reply and one tool call."""

    def send(self, user_message: str) -> AgentReply:
        call = ToolCallRecord(
            name="search_policies",
            arguments={"query": "horário"},
            result_summary='{"found": true}',
        )
        return AgentReply(text="Abrimos às 9h. Frete: R$ 35,00.", tool_calls=[call])


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "create_agent", lambda *_args: FakeAgent())


def run_app() -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    return app.run()


@pytest.mark.usefixtures("fake_agent")
def test_page_shows_welcome_sidebar_and_simulated_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "STORE_NOW", "2026-03-25T10:30")
    app = run_app()
    assert not app.exception
    assert "assistente virtual" in app.chat_message[0].markdown[0].value
    assert app.sidebar.button[0].label == "Nova conversa"
    assert "Data simulada: 25/03/2026 10:30" in app.sidebar.info[0].value


@pytest.mark.usefixtures("fake_agent")
def test_reply_shows_tool_calls_and_escapes_prices() -> None:
    app = run_app()
    app.chat_input[0].set_value("Que horas abre?").run()
    assert not app.exception
    user, assistant = app.chat_message[1], app.chat_message[2]
    assert user.markdown[0].value == "Que horas abre?"
    # "$" is escaped so "R$ 35,00" is not rendered as LaTeX.
    assert assistant.markdown[0].value == "Abrimos às 9h. Frete: R\\$ 35,00."
    assert assistant.expander[0].label == "🔧 Consultas realizadas (1)"


@pytest.mark.usefixtures("fake_agent")
def test_new_conversation_clears_the_screen() -> None:
    app = run_app()
    app.chat_input[0].set_value("Oi").run()
    app.sidebar.button[0].click().run()
    assert len(app.chat_message) == 1  # only the welcome message


def test_missing_api_key_shows_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    app = run_app()
    assert "GEMINI_API_KEY" in app.error[0].value
    assert len(app.chat_input) == 0  # the page stops before the chat
