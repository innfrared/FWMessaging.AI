# ICAI Interview Engine

FastAPI service that powers interview question generation and answer evaluation for ICAI.

This service is consumed by the Django backend over HTTP and does not store data.

## What it does

- Generates interview questions from a candidate profile
- Evaluates interview answers and returns structured feedback
- Supports multiple interview modes (conversation, drilldown, case, etc.)
- Enforces strict request/response contracts

## Tech

- Python
- FastAPI
- Pydantic
- OpenAI API

## Run locally

```bash
uvicorn app.main:app --reload --port 8001
```

API docs available at:

- `/docs`

## Configuration

Environment variables:

- `OPENAI_API_KEY=...`
- `OPENAI_MODEL_GENERATE=...`
- `OPENAI_MODEL_EVALUATE=...`

If no API key is provided, a mock LLM is used.

## API

Base path:

- `/api/v1/interviews`

Endpoints:

- `POST /generate` — generate interview questions
- `POST /evaluate` — evaluate answers and return feedback

## Notes

- Stateless service
- No database
- Session IDs are passed through for context only
- Designed to be replaceable or scaled independently

