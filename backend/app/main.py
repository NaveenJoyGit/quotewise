from fastapi import FastAPI

from app.api.whatsapp_webhook import router as whatsapp_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="QuoteWise", version="0.1.0")
    app.include_router(whatsapp_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
