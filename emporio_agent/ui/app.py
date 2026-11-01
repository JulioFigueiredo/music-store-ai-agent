"""Streamlit chat page: renders the conversation and forwards messages.

Streamlit reruns this script on every interaction; the conversation survives
in st.session_state (see session.py).
"""

import logging

import streamlit as st

from emporio_agent import config
from emporio_agent.agent import Agent
from emporio_agent.ui import components, session
from emporio_agent.ui.session import ChatMessage

MISSING_KEY_MESSAGE = (
    "A chave da API do Gemini não está configurada. Copie o arquivo "
    "`.env.example` para `.env`, preencha `GEMINI_API_KEY` (chave gratuita em "
    "https://aistudio.google.com/apikey) e recarregue a página."
)
DATA_ERROR_MESSAGE = "Não foi possível carregar os dados da loja."


def main() -> None:
    """Draw the page and answer the message typed in this rerun, if any."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    st.set_page_config(page_title="Empório da Música", page_icon="🎸")
    components.render_sidebar(
        now=config.get_store_now(),
        is_simulated=bool(config.STORE_NOW),
        model=config.GEMINI_MODEL,
        on_reset=session.reset_conversation,
    )
    st.title("🎸 Empório da Música")
    agent = start_agent()

    components.render_welcome()
    for message in session.get_messages():
        components.render_message(message)

    user_text = st.chat_input("Digite sua mensagem...")
    if isinstance(user_text, str) and user_text.strip():
        answer(agent, user_text.strip())


def start_agent() -> Agent:
    """Get this session's agent, or stop the page with a clear error."""
    try:
        return session.get_agent()
    except RuntimeError:
        st.error(MISSING_KEY_MESSAGE)
        st.stop()
    except (FileNotFoundError, ValueError) as error:
        st.error(DATA_ERROR_MESSAGE)
        st.caption(str(error))
        st.stop()


def answer(agent: Agent, user_text: str) -> None:
    """Show the customer's message, ask the agent and show its reply."""
    messages = session.get_messages()
    user_message = ChatMessage(role="user", text=user_text)
    messages.append(user_message)
    components.render_message(user_message)

    with st.spinner("Consultando..."):
        reply = agent.send(user_text)
    assistant_message = ChatMessage(
        role="assistant", text=reply.text, tool_calls=reply.tool_calls
    )
    messages.append(assistant_message)
    components.render_message(assistant_message)
