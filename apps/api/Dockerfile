FROM python:3.12-slim@sha256:5072b08ad74609c5329ab4085a96dfa873de565fb4751a4cfcd7dcc427661df0

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml /app/
COPY constraints.txt /app/constraints.txt
COPY app /app/app
COPY tests /app/tests

RUN python -m pip install -c constraints.txt .[dev]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
