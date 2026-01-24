import logging

from fastapi import FastAPI

from app.api.webhooks import router as webhooks_router
from app.core.config import settings

class ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extras = []
        for key in ("message_id", "intent", "language", "service", "reply_text", "reason"):
            value = getattr(record, key, None)
            if value not in (None, ""):
                extras.append(f"{key}={value}")
        base = super().format(record)
        if extras:
            return f"{base} | " + " ".join(extras)
        return base


handler = logging.StreamHandler()
handler.setFormatter(ContextFormatter("%(levelname)s:%(name)s:%(message)s"))

root = logging.getLogger()
root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
root.handlers.clear()
root.addHandler(handler)

app = FastAPI(title="Instagram DM Auto Reply", version="1.0.0")

app.include_router(webhooks_router, tags=["webhooks"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
