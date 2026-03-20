from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, catalog, connections, health, mappings, oauth, public, transfers
from app.config import Settings
from app.services.container import ServiceContainer


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    container = ServiceContainer(resolved_settings)
    container.database.initialize()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description="Веб-сервис для переноса карточек товаров между Wildberries и Ozon.",
    )
    app.state.container = container

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(connections.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(transfers.router, prefix="/api/v1")
    app.include_router(mappings.router, prefix="/api/v1")
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(oauth.router, prefix="/api/v1")

    @app.middleware("http")
    async def disable_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
