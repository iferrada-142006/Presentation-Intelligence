from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import presentations

app = FastAPI(
    title="Presentation Intelligence API",
    version="0.1.0",
    description="Multimodal presentation analysis platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pi.ferzamedia.com", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(presentations.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "presentation-intelligence"}
