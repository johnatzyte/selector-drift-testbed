# Pinned by digest, not tag: demos have to still work in six months.
# ghcr.io/astral-sh/uv:python3.13-bookworm-slim resolved 2026-09-18.
FROM ghcr.io/astral-sh/uv@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8811

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY gunicorn.conf.py ./
COPY shop/ ./shop/

EXPOSE 8811
# Single worker on purpose — see the comment in gunicorn.conf.py.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "shop.wsgi:app"]
