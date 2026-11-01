"""Policy tool: search_policies, a thin wrapper over policies.py."""

from emporio_agent.policies import PolicySection, search_policy_sections
from emporio_agent.tools.common import ToolResult


class PolicyTools:
    """Search over the policy manual sections loaded at startup."""

    def __init__(self, sections: list[PolicySection]) -> None:
        self.sections = sections

    def search_policies(self, query: str) -> ToolResult:
        """Search the store's policy manual and return the relevant sections.

        Use it for any question about rules or store information: opening
        hours, address and contacts, payment methods and installment rules,
        returns and exchanges, shipping and delivery, promotion rules,
        warranty, privacy and complaints. Answer policy questions only from
        what this returns.

        Args:
            query: The customer's question or its key words, e.g.
                "devolução arrependimento".
        """
        found = search_policy_sections(self.sections, query)
        if not found:
            return {
                "found": False,
                "message": "No policy section matches. Try other key words.",
                "available_topics": [s.heading for s in self.sections],
            }
        return {
            "found": True,
            "sections": [{"section": s.heading, "text": s.text} for s in found],
        }
