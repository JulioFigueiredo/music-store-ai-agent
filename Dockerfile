# Optional way to run the chat without installing uv or Python locally.
# Usage: docker compose up --build   (reads GEMINI_API_KEY etc. from .env)

FROM python:3.12-slim

# uv, pinned to the version the lockfile was made with.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Dependencies first, in their own layer, so code changes rebuild fast.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project

# Then the project itself (secrets stay out: see .dockerignore).
COPY . .
RUN uv sync --locked --no-dev

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["uv", "run", "--no-sync", "streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
