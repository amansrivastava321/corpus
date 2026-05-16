"""Admin API — configuration, export/import, and storage health."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/config")
async def get_config(request: Request) -> dict:
    from corpus import config as cfg
    return {
        "version": cfg.VERSION,
        "host": cfg.HOST,
        "port": cfg.PORT,
        "db_path": cfg.DB_PATH,
        "log_level": cfg.LOG_LEVEL,
    }


@router.get("/storage/health")
async def storage_health(request: Request) -> dict:
    conn = request.app.state.container._conn
    try:
        async with conn.execute("SELECT COUNT(*) FROM products") as cur:
            product_count = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM signals") as cur:
            signal_count = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM episodes") as cur:
            episode_count = (await cur.fetchone())[0]
        return {
            "status": "healthy",
            "product_count": product_count,
            "signal_count": signal_count,
            "episode_count": episode_count,
        }
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


@router.post("/export")
async def export_data(request: Request) -> dict:
    conn = request.app.state.container._conn
    export: dict = {"exported_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    for table in ("products", "signals", "checkpoints", "episodes", "patterns"):
        try:
            async with conn.execute(f"SELECT * FROM {table}") as cur:  # noqa: S608
                rows = await cur.fetchall()
                export["tables"][table] = [dict(r) for r in rows]
        except Exception:
            export["tables"][table] = []
    return export


@router.post("/import")
async def import_data(request: Request) -> dict:
    # Import is deliberately read-only in this endpoint; real import goes through CLI.
    return {"status": "ok", "message": "Use 'corpus import' CLI command for bulk imports"}
