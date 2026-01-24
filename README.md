# Meta DM Auto Reply

FastAPI service that automatically handles Meta DMs for business accounts using ports/adapters pattern. Classifies messages by intent, generates replies from a structured knowledge base, maintains conversation context, and hands off to humans when needed. Supports English and Spanish.

**Features:** intent-based replies (pricing, booking, availability), webhook signature verification, duplicate protection, conversation state, booking integration.

**Stack:** FastAPI, OpenAI API, Pydantic, httpx, Uvicorn

## Setup

Requires Python 3.11+, OpenAI API key, and Meta app credentials.

```bash
git clone <repository-url> && cd FW.AI
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Endpoints

`GET /webhooks/instagram` verification | 
`POST /webhooks/instagram` messages | 
`GET /health` health check

## Project Structure

```
app/
 /api/
 /application/
 /domain/
 /infrastructure/
 /core/
 /wiring/
```
