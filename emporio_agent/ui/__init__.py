"""Streamlit chat interface (user-facing strings in pt-BR).

    app.py         page flow: sidebar, history, chat input
    session.py     per-browser-session state and data loaded once per process
    components.py  how messages, tool calls and the sidebar are drawn

The UI only renders and forwards messages to the Agent: no business logic.
Run it with `uv run streamlit run app.py` from the repository root.
"""
