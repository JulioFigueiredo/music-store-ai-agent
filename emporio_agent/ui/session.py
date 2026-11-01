"""Per-session state: one Agent per browser session, data shared per process.

Each browser session gets its own Agent (and so its own history), which keeps
conversations from leaking between customers. The CSVs and the PDF are loaded
once per process and shared, since they are read-only.
"""

from dataclasses import dataclass, field

import streamlit as st

from emporio_agent.agent import Agent, ToolCallRecord, create_agent
from emporio_agent.data import (
    PolicySection,
    StoreData,
    load_policy_sections,
    load_store_data,
)


@dataclass(frozen=True)
class ChatMessage:
    """One message as shown on screen (the Agent keeps its own history)."""

    role: str  # "user" or "assistant"
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


@st.cache_resource(show_spinner="Carregando catálogo e políticas...")
def load_resources() -> tuple[StoreData, list[PolicySection]]:
    """Load the CSVs and the policies PDF once per process."""
    return load_store_data(), load_policy_sections()


def get_agent() -> Agent:
    """This session's agent, created on first use.

    Raises RuntimeError if the API key is missing, and FileNotFoundError or
    ValueError if the data files are missing or malformed.
    """
    if "agent" not in st.session_state:
        data, policy_sections = load_resources()
        st.session_state.agent = create_agent(data, policy_sections)
    agent: Agent = st.session_state.agent
    return agent


def get_messages() -> list[ChatMessage]:
    """The messages shown in this session, oldest first."""
    messages: list[ChatMessage] = st.session_state.setdefault("messages", [])
    return messages


def reset_conversation() -> None:
    """Start over: a fresh agent (empty history) and an empty screen."""
    for key in ("agent", "messages"):
        st.session_state.pop(key, None)
