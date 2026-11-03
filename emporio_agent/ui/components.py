"""How the chat is drawn: messages, tool calls and the sidebar."""

import json
from collections.abc import Callable
from datetime import datetime

import streamlit as st

from emporio_agent.agent import ToolCallRecord
from emporio_agent.ui.session import ChatMessage

WELCOME_MESSAGE = (
    "Oi! Eu sou o assistente virtual da Empório da Música. Sua música começa "
    "aqui! 🎸\n\nPosso te ajudar com instrumentos, preços, promoções, formas "
    "de pagamento, pedidos e políticas da loja. O que você procura?"
)
HELP_TOPICS = """\
**Posso ajudar com:**
- instrumentos, preços e disponibilidade
- promoções ativas
- PIX e parcelamento
- status de pedidos (número do pedido + e-mail ou telefone)
- trocas, devoluções, frete, garantia e horários
"""
# Friendly label per tool, so the expander shows at a glance whether the
# agent queried data (catalog, orders...) or the policies.
TOOL_LABELS = {
    "search_products": "📦 Catálogo",
    "get_product_details": "📦 Produto",
    "get_active_promotions": "🏷️ Promoções",
    "calculate_payment_options": "💳 Pagamento",
    "get_order_status": "🚚 Pedido",
    "search_policies": "📋 Políticas",
}


def render_sidebar(
    now: datetime, is_simulated: bool, model: str, on_reset: Callable[[], None]
) -> None:
    """Store info, the reference date, help topics and the reset button."""
    with st.sidebar:
        st.header("Empório da Música")
        st.caption("Sua música começa aqui.")
        st.button("Nova conversa", on_click=on_reset, width="stretch")
        date_label = "Data simulada" if is_simulated else "Data e hora"
        st.info(f"{date_label}: {now:%d/%m/%Y %H:%M}")
        if is_simulated:
            st.caption(
                "Os dados da loja vão até março de 2026, então o atendimento "
                "usa uma data fixa para prazos e pedidos fazerem sentido."
            )
        st.markdown(HELP_TOPICS)
        st.caption(f"Modelo: {model}")


def render_message(message: ChatMessage) -> None:
    """One chat bubble, with the tool calls under assistant replies."""
    with st.chat_message(message.role):
        st.markdown(escape_markdown(message.text))
        if message.tool_calls:
            render_tool_calls(message.tool_calls)


def render_welcome() -> None:
    """Fixed greeting shown at the top (UI only: costs no model call)."""
    with st.chat_message("assistant"):
        st.markdown(WELCOME_MESSAGE)


def render_tool_calls(tool_calls: list[ToolCallRecord]) -> None:
    """Collapsed list of the queries made during a turn.

    Makes the agent's decisions visible: which tool, with which arguments,
    and a short view of what came back.
    """
    with st.expander(f"🔧 Consultas realizadas ({len(tool_calls)})"):
        for call in tool_calls:
            label = TOOL_LABELS.get(call.name, "🔧 Ferramenta")
            st.markdown(f"**{label}** · `{call.name}`")
            st.code(json.dumps(call.arguments, ensure_ascii=False), language="json")
            st.code(call.result_summary, language="json", wrap_lines=True)


def escape_markdown(text: str) -> str:
    """Escape "$" so prices like "R$ 429,90" are not rendered as LaTeX math."""
    return text.replace("$", "\\$")
