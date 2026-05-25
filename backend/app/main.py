from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.demo import router as demo_router
from app.api.onboarding import router as onboarding_router
from app.api.quotes import router as quotes_router
from app.api.twilio_webhook import router as twilio_whatsapp_router
from app.api.whatsapp_webhook import router as whatsapp_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="QuoteWise", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(whatsapp_router)
    app.include_router(twilio_whatsapp_router)
    app.include_router(quotes_router)
    app.include_router(onboarding_router)
    app.include_router(demo_router)

    # Serve generated PDFs; create the directory if it doesn't exist yet.
    pdf_dir = Path(settings.pdf_storage_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/pdfs", StaticFiles(directory=str(pdf_dir)), name="pdfs")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
