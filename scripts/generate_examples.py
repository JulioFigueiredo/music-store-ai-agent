"""Run scripted conversations through the real Agent and save the transcripts.

Usage:
    uv run python scripts/generate_examples.py          # all scenarios
    uv run python scripts/generate_examples.py 3 4      # only scenarios 3 and 4

Every reply in examples/ is a real model output; nothing is written by hand.
The store's "now" is fixed so the transcripts are reproducible against the
frozen dataset. Free-tier rate limits are respected with a pause between
messages, and a failed turn is retried instead of being saved.
"""

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from emporio_agent import config
from emporio_agent.agent import Agent, AgentReply, ToolCallRecord, create_agent
from emporio_agent.agent.agent import FALLBACK_REPLY
from emporio_agent.data import load_policy_sections, load_store_data

logger = logging.getLogger("generate_examples")

EXAMPLES_DIR = config.PROJECT_ROOT / "examples"
# A Wednesday during business hours, three days after the last order.
EXAMPLES_NOW = datetime(2026, 3, 25, 10, 30, tzinfo=config.STORE_TIMEZONE)
# Each turn takes 2-3 model calls; free-tier per-minute limits are low (5-10).
PAUSE_BETWEEN_MESSAGES_SECONDS = 25
RETRY_WAIT_SECONDS = 60
MAX_ATTEMPTS_PER_MESSAGE = 3


@dataclass(frozen=True)
class Scenario:
    """A scripted conversation: what the customer says, in order."""

    filename: str
    title: str
    description: str
    demonstrates: str
    messages: list[str]


SCENARIOS = [
    Scenario(
        filename="01_product_search.md",
        title="Catalog search with filters, then payment options",
        description="A customer looks for acoustic guitars up to R$ 1,000, then "
        "asks about installments and PIX for one of them.",
        demonstrates="Filtered catalog search (sorted, truncated to 10 of 12, "
        "unavailable products hidden) and deterministic payment math: 10x is "
        "not allowed because the installment would fall below the R$ 100 "
        "minimum, so the tool returns the real maximum.",
        messages=[
            "Oi! Quais violões disponíveis custando até R$1000?",
            "Dá pra parcelar o Tagima Woodstock em 10x?",
            "E se eu pagar no PIX, quanto fica?",
        ],
    ),
    Scenario(
        filename="02_price_lookup.md",
        title="Price lookup, expired and active promotions, out of stock",
        description="A customer checks prices, asks about a promotion that has "
        "expired, then about one that is active, and finally about a product "
        "that is out of stock.",
        demonstrates="Exact prices from the data; an expired promotion reported "
        "transparently with the current price; an active promotion shown with "
        "original price, discount % and promotional price, with no PIX "
        "discount on top (promotions are not cumulative); alternatives for an "
        "out-of-stock product.",
        messages=[
            "Quanto custa o Takamine GD20?",
            "Ele tá na Oferta Especial?",
            "E o Crafter HT-100, tem desconto?",
            "Se eu pagar no PIX, ganho mais 5% em cima?",
            "E o Giannini GF-3D, tem?",
        ],
    ),
    Scenario(
        filename="03_order_status.md",
        title="Order status with identity verification",
        description="A customer asks about an order. The first email does not "
        "match the order's customer; the second one does.",
        demonstrates="Identity check (order number + email or phone, same "
        "generic message for a wrong contact or an unknown order); greeting by "
        "first name; a shipped order whose estimated delivery is already in "
        "the past is flagged as delayed, so the agent apologizes, shares the "
        "tracking code and offers the staff contacts.",
        messages=[
            "Oi, queria saber do meu pedido 8",
            "Meu email é ana.ferreira@gmail.com",
            "Ah, desculpa, usei outro: anacarol.ferreira@coldmail.com",
        ],
    ),
    Scenario(
        filename="04_return_policy.md",
        title="Return request: order data combined with policy rules",
        description="A customer regrets buying a ukulele and wants to return "
        "it, then asks what happens if it has a defect.",
        demonstrates="The non-trivial case: the agent combines order facts "
        "(pre-computed days since purchase and since the estimated receipt) "
        "with the policy sections. The 7-day regret window and the 30-day "
        "defect exchange have passed, but the 90-day legal warranty from "
        "receipt still applies.",
        messages=[
            "Oi! Me arrependi da compra do meu ukulele, posso devolver?",
            "É o pedido 7, meu email é leticia.rocha@jmail.com",
            "E se ele apresentar algum defeito, o que eu faço?",
        ],
    ),
    Scenario(
        filename="05_out_of_scope.md",
        title="Out of scope requests and store information",
        description="A customer asks for accessories, for an instrument "
        "category the store does not carry, for help with homework, and for "
        "the store's address and hours.",
        demonstrates="Accessories redirected per the manual without inventing "
        "partner stores; an empty category reported as not carried (not as "
        "out of stock); an unrelated request politely declined; store "
        "information answered from the policies.",
        messages=[
            "Vocês vendem cordas de guitarra?",
            "E saxofone, vocês têm?",
            "Você me ajuda com meu dever de matemática? Quanto é 15% de 240?",
            "Beleza! Qual o endereço e o horário da loja?",
        ],
    ),
]


def main() -> None:
    """Generate the selected scenarios (all by default), one file each."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    selected = select_scenarios(parse_args().numbers)
    data, policy_sections = load_store_data(), load_policy_sections()
    EXAMPLES_DIR.mkdir(exist_ok=True)
    for number, scenario in selected:
        logger.info("Scenario %d: %s", number, scenario.title)
        agent = create_agent(data, policy_sections, clock=lambda: EXAMPLES_NOW)
        turns = run_scenario(agent, scenario)
        path = EXAMPLES_DIR / scenario.filename
        path.write_text(render_transcript(number, scenario, turns), encoding="utf-8")
        logger.info("Saved %s", path.relative_to(config.PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "numbers", nargs="*", type=int, help="scenario numbers (default: all)"
    )
    return parser.parse_args()


def select_scenarios(numbers: list[int]) -> list[tuple[int, Scenario]]:
    """(number, scenario) pairs to run, numbered from 1."""
    numbered = list(enumerate(SCENARIOS, start=1))
    if not numbers:
        return numbered
    return [(number, scenario) for number, scenario in numbered if number in numbers]


def run_scenario(agent: Agent, scenario: Scenario) -> list[tuple[str, AgentReply]]:
    """Send each message in order, pausing between them for the rate limit."""
    turns = []
    for index, message in enumerate(scenario.messages):
        if index > 0:
            time.sleep(PAUSE_BETWEEN_MESSAGES_SECONDS)
        turns.append((message, send_with_retry(agent, message)))
    return turns


def send_with_retry(agent: Agent, message: str) -> AgentReply:
    """Send a message; on the fallback reply, undo the turn, wait and retry.

    The fallback means the API failed (rate limit or overload), not that the
    agent answered, so it must never end up in an example.
    """
    for attempt in range(1, MAX_ATTEMPTS_PER_MESSAGE + 1):
        history_before = list(agent.history)
        reply = agent.send(message)
        if reply.text != FALLBACK_REPLY:
            return reply
        agent.history = history_before
        logger.warning(
            "Attempt %d failed; retrying in %ds", attempt, RETRY_WAIT_SECONDS
        )
        time.sleep(RETRY_WAIT_SECONDS)
    raise RuntimeError(
        f"No answer after {MAX_ATTEMPTS_PER_MESSAGE} attempts: {message!r}"
    )


def render_transcript(
    number: int, scenario: Scenario, turns: list[tuple[str, AgentReply]]
) -> str:
    """Markdown transcript: English header, pt-BR conversation, tool notes."""
    tool_names = sorted({call.name for _, reply in turns for call in reply.tool_calls})
    lines = [
        f"# Example {number}: {scenario.title}",
        "",
        f"- **Scenario:** {scenario.description}",
        f"- **Demonstrates:** {scenario.demonstrates}",
        f"- **Tools called:** {', '.join(f'`{name}`' for name in tool_names)}",
        f"- **Model:** `{config.GEMINI_MODEL}`",
        f"- **Simulated store date (`STORE_NOW`):** "
        f"`{EXAMPLES_NOW:%Y-%m-%dT%H:%M}` ({EXAMPLES_NOW:%A}, Campo Grande time)",
        "- **Generated by:** `uv run python scripts/generate_examples.py` "
        "(real model output, not edited). Tool calls are shown as small notes.",
        "",
        "---",
        "",
    ]
    for message, reply in turns:
        lines += [f"**Cliente:** {message}", ""]
        lines += [f"<sub>🔧 {format_call(call)}</sub><br>" for call in reply.tool_calls]
        if reply.tool_calls:
            lines.append("")
        lines += [f"**Assistente:** {hard_line_breaks(reply.text)}", "", "---", ""]
    return "\n".join(lines)


def format_call(call: ToolCallRecord) -> str:
    """A tool call as code: `name(arg="value", ...)`."""
    arguments = ", ".join(
        f"{key}={format_value(value)}" for key, value in call.arguments.items()
    )
    return f"`{call.name}({arguments})`"


def format_value(value: Any) -> str:
    """Numbers as-is, everything else as a JSON literal."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return json.dumps(value, ensure_ascii=False)


def hard_line_breaks(text: str) -> str:
    """Keep the chat's line breaks in Markdown (a single newline would merge)."""
    return text.strip().replace("\n", "  \n")


if __name__ == "__main__":
    main()
