from fastapi import FastAPI
from app.api.v1.interviews import router as interviews_router

app = FastAPI(title="ICAI Interview Engine", version="1.0.0")

app.include_router(interviews_router, prefix="/api/v1/interviews", tags=["interviews"])

