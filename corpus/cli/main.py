"""Corpus CLI — Click-based command-line interface."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
    _RICH = True
except ImportError:
    _RICH = False


_console = Console() if _RICH else None


def _out(data: Any, *, as_json: bool = False) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    elif _RICH and isinstance(data, dict):
        rprint(data)
    else:
        click.echo(json.dumps(data, indent=2, default=str))


def _client(base_url: str) -> "httpx.Client":
    if not _HTTPX:
        click.echo("httpx is required for CLI commands. Run: pip install httpx", err=True)
        sys.exit(1)
    return httpx.Client(base_url=base_url, timeout=10.0)


def _get(base_url: str, path: str) -> dict:
    with _client(base_url) as c:
        resp = c.get(path)
        resp.raise_for_status()
        return resp.json()


def _post(base_url: str, path: str, body: dict) -> dict:
    with _client(base_url) as c:
        resp = c.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group()
@click.option("--url", default="http://localhost:8000", envvar="CORPUS_URL", show_default=True,
              help="Corpus server URL")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output raw JSON")
@click.pass_context
def cli(ctx: click.Context, url: str, as_json: bool) -> None:
    """Corpus — AI-native coordination runtime CLI."""
    ctx.ensure_object(dict)
    ctx.obj["url"] = url
    ctx.obj["json"] = as_json


# ─── serve ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", default=None, envvar="CORPUS_HOST", help="Bind host")
@click.option("--port", default=None, type=int, envvar="CORPUS_PORT", help="Bind port")
@click.option("--db", default=None, envvar="CORPUS_DB_PATH", help="SQLite path")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload on code changes")
def serve(host: str | None, port: int | None, db: str | None, reload: bool) -> None:
    """Start the Corpus server."""
    import os
    import uvicorn
    from corpus import config as cfg

    _host = host or cfg.HOST
    _port = port or cfg.PORT
    if db:
        os.environ["CORPUS_DB_PATH"] = db

    click.echo(f"Starting Corpus {cfg.VERSION} on {_host}:{_port}")
    uvicorn.run("corpus.server:app", host=_host, port=_port, reload=reload)


# ─── doctor ───────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Check server health and connectivity."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    try:
        data = _get(url, "/health")
        if as_json:
            _out(data, as_json=True)
        elif _RICH and _console:
            status = data.get("status", "unknown")
            color = "green" if status == "ok" else "red"
            _console.print(f"[bold {color}]Corpus status: {status}[/]")
            _console.print(data)
        else:
            click.echo(f"status: {data.get('status', 'unknown')}")
            click.echo(json.dumps(data, indent=2))
    except Exception as exc:
        click.echo(f"[ERROR] Cannot reach Corpus at {url}: {exc}", err=True)
        sys.exit(1)


# ─── products ─────────────────────────────────────────────────────────────────

@cli.group()
def products() -> None:
    """Manage registered products."""


@products.command("list")
@click.pass_context
def products_list(ctx: click.Context) -> None:
    """List all registered products."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    data = _get(url, "/products")
    if as_json:
        _out(data, as_json=True)
        return
    items = data.get("products", data) if isinstance(data, dict) else data
    if _RICH and _console:
        t = Table("Name", "Product ID", "Capabilities", "Status")
        for p in items:
            caps = ", ".join(p.get("capabilities", []))
            t.add_row(p.get("name", ""), p.get("product_id", ""), caps, p.get("presence", ""))
        _console.print(t)
    else:
        click.echo(json.dumps(items, indent=2, default=str))


# ─── signals ──────────────────────────────────────────────────────────────────

@cli.group()
def signals() -> None:
    """Inspect and emit signals."""


@signals.command("emit")
@click.option("--source", required=True, help="Source product name")
@click.option("--target", required=True, help="Target product name")
@click.option("--type", "sig_type", required=True, help="Signal type (e.g. INFORM, BLOCK)")
@click.option("--message", required=True, help="Signal message")
@click.option("--severity", default="MEDIUM", show_default=True)
@click.option("--payload", default="{}", help="JSON payload string")
@click.pass_context
def signals_emit(ctx: click.Context, source: str, target: str, sig_type: str,
                 message: str, severity: str, payload: str) -> None:
    """Emit a signal to a target product."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    try:
        body_payload = json.loads(payload)
    except json.JSONDecodeError as exc:
        click.echo(f"Invalid --payload JSON: {exc}", err=True)
        sys.exit(1)
    body = {
        "source_product": source,
        "target_product": target,
        "type": sig_type,
        "severity": severity,
        "payload": body_payload,
    }
    data = _post(url, "/signals/emit", body)
    _out(data, as_json=as_json)


@signals.command("pending")
@click.option("--target", default=None, help="Filter by target product")
@click.pass_context
def signals_pending(ctx: click.Context, target: str | None) -> None:
    """Show pending (undelivered) signals."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    path = f"/signals/pending/{target}" if target else "/signals/pending/all"
    data = _get(url, path)
    _out(data, as_json=as_json)


# ─── checkpoints ──────────────────────────────────────────────────────────────

@cli.group()
def checkpoints() -> None:
    """Manage deployment checkpoints."""


@checkpoints.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.pass_context
def checkpoints_list(ctx: click.Context, status: str | None) -> None:
    """List checkpoints."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    path = "/checkpoints"
    if status:
        path += f"?status={status}"
    data = _get(url, path)
    if as_json:
        _out(data, as_json=True)
        return
    items = data.get("checkpoints", data) if isinstance(data, dict) else data
    if _RICH and _console:
        t = Table("ID", "Product", "Reason", "Status")
        for cp in items:
            t.add_row(
                str(cp.get("checkpoint_id", cp.get("id", "")))[:12],
                cp.get("product_name", ""),
                (cp.get("reason", "") or "")[:40],
                cp.get("status", ""),
            )
        _console.print(t)
    else:
        click.echo(json.dumps(items, indent=2, default=str))


# ─── policy ───────────────────────────────────────────────────────────────────

@cli.group()
def policy() -> None:
    """Inspect and manage policy."""


@policy.command("show")
@click.pass_context
def policy_show(ctx: click.Context) -> None:
    """Show the current governance policy."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    data = _get(url, "/policy")
    _out(data, as_json=as_json)


# ─── guardian ─────────────────────────────────────────────────────────────────

@cli.group()
def guardian() -> None:
    """Guardian mode status and interventions."""


@guardian.command("status")
@click.pass_context
def guardian_status(ctx: click.Context) -> None:
    """Show Guardian engine status."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    data = _get(url, "/guardian/status")
    _out(data, as_json=as_json)


@guardian.command("interventions")
@click.option("--limit", default=20, show_default=True)
@click.pass_context
def guardian_interventions(ctx: click.Context, limit: int) -> None:
    """List recent Guardian interventions."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    data = _get(url, f"/guardian/interventions?limit={limit}")
    _out(data, as_json=as_json)


# ─── dashboard ────────────────────────────────────────────────────────────────

@cli.group()
def dashboard() -> None:
    """Observability dashboard."""


@dashboard.command("summary")
@click.pass_context
def dashboard_summary(ctx: click.Context) -> None:
    """Print full system dashboard summary."""
    url = ctx.obj["url"]
    as_json = ctx.obj["json"]
    data = _get(url, "/dashboard/summary")
    if as_json:
        _out(data, as_json=True)
        return
    if _RICH and _console:
        sys_info = data.get("system", {})
        _console.rule("[bold]Corpus Dashboard[/]")
        _console.print(f"[green]Status:[/] {sys_info.get('status', '?')}")
        _console.print(f"[blue]Products:[/] {data.get('products', {}).get('total', 0)} total, "
                       f"{data.get('products', {}).get('online', 0)} online")
        _console.print(f"[yellow]Signals pending:[/] {data.get('signals', {}).get('pending', 0)}")
        cp = data.get("checkpoints", {})
        _console.print(f"[red]Checkpoints:[/] {cp.get('waiting_clearance', 0)} waiting, "
                       f"{cp.get('blocked', 0)} blocked")
        _console.print(f"[cyan]Policy mode:[/] {data.get('policy', {}).get('mode', '?')}")
    else:
        click.echo(json.dumps(data, indent=2, default=str))


# ─── export / import ──────────────────────────────────────────────────────────

@cli.command("export")
@click.option("--output", "-o", default="corpus_export.json", show_default=True,
              help="Output file path")
@click.pass_context
def export_cmd(ctx: click.Context, output: str) -> None:
    """Export Corpus state to a JSON file."""
    url = ctx.obj["url"]
    data = {
        "products": _get(url, "/products"),
        "checkpoints": _get(url, "/checkpoints"),
        "dashboard": _get(url, "/dashboard/summary"),
    }
    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)
    click.echo(f"Exported to {output}")


@cli.command("import")
@click.argument("input_file", type=click.Path(exists=True))
@click.pass_context
def import_cmd(ctx: click.Context, input_file: str) -> None:
    """Import products from a JSON export file."""
    url = ctx.obj["url"]
    with open(input_file) as f:
        data = json.load(f)
    products_data = data.get("products", {})
    items = products_data.get("products", []) if isinstance(products_data, dict) else products_data
    imported = 0
    for p in items:
        try:
            _post(url, "/products/register", p)
            imported += 1
        except Exception as exc:
            click.echo(f"Skipped {p.get('name', '?')}: {exc}", err=True)
    click.echo(f"Imported {imported} product(s).")
