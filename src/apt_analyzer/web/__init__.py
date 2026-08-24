"""Minimal local web application boundary for apt-analyzer."""

from pathlib import Path
from typing import Final

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

_TEMPLATE_DIRECTORY: Final[Path] = Path(__file__).parent / "templates"


def create_app() -> FastAPI:
    """Create the local, single-process web application."""
    app = FastAPI(title="apt-analyzer local web")
    templates = Jinja2Templates(directory=_TEMPLATE_DIRECTORY)

    def root(request: Request) -> HTMLResponse:
        return _root(request, templates)

    app.add_api_route("/", root, response_class=HTMLResponse)
    app.add_api_route("/health", _health)

    return app


def _root(request: Request, templates: Jinja2Templates) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "apt-analyzer local web"},
    )


def _health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()
