from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _default_static_dir() -> Path:
    cwd_dist = Path.cwd() / "web" / "dist"
    if cwd_dist.exists():
        return cwd_dist

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "web" / "dist"
        if candidate.exists():
            return candidate
    return cwd_dist


def _is_static_asset_path(path: str) -> bool:
    return Path(path).suffix != ""


def mount_webui_static(app: FastAPI, *, static_dir: Path | str | None = None) -> None:
    dist_dir = Path(static_dir) if static_dir is not None else _default_static_dir()
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return

    dist_root = dist_dir.resolve()

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def webui_static_or_spa_fallback(request: Request, path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)

        requested_path = (dist_root / path).resolve()
        if requested_path.is_relative_to(dist_root) and requested_path.is_file():
            return FileResponse(requested_path)

        if _is_static_asset_path(path):
            raise StarletteHTTPException(status_code=404)

        return FileResponse(index_path)
