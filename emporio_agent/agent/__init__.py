"""The LLM side of the project: the only package that knows about Gemini.

    prompts.py  system prompt in pt-BR (persona and rules of conduct)
    agent.py    Agent: conversation history + explicit function-calling loop

Swapping the LLM provider would only touch this package.
"""

from emporio_agent.agent.agent import Agent, AgentReply, ToolCallRecord, create_agent

__all__ = ["Agent", "AgentReply", "ToolCallRecord", "create_agent"]
