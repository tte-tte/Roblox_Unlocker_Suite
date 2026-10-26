import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from core.inspector import inspector_service
from database.repository import AccountRepository
from web.ws_manager import ws_manager

logger: logging.Logger = logging.getLogger("roblox_suite.routes")
router: APIRouter = APIRouter()


class ConcurrencyRequest(BaseModel):
    workers: int


class GenerateAccountsRequest(BaseModel):
    count: int = 10
    prefix: str = "RblxPlayer"


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> HTMLResponse:
    try:
        html_path: Path = Path("web/dashboard.html")
        content: str = html_path.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    except Exception as exc:
        logger.error(f"Failed to read dashboard HTML: {exc}")
        return HTMLResponse(content="<h1>Dashboard file missing</h1>", status_code=500)


@router.get("/api/accounts")
async def list_accounts() -> JSONResponse:
    accounts: list[dict[str, Optional[str | int]]] = await AccountRepository.get_all_accounts()
    return JSONResponse(content={
        "accounts": accounts,
        "workers": inspector_service.max_workers
    })


@router.post("/api/accounts/sync")
async def sync_accounts() -> JSONResponse:
    added: int = await AccountRepository.sync_from_file()
    accounts: list[dict[str, Optional[str | int]]] = await AccountRepository.get_all_accounts()
    await ws_manager.broadcast_log("SYSTEM", f"Reloaded accounts.txt & proxies.txt (New: {added}, Total: {len(accounts)})")
    return JSONResponse(content={"added": added, "accounts": accounts})


@router.post("/api/accounts/generate")
async def generate_accounts(payload: GenerateAccountsRequest) -> JSONResponse:
    created: int = await AccountRepository.generate_accounts_batch(
        count=payload.count,
        prefix=payload.prefix
    )
    accounts: list[dict[str, Optional[str | int]]] = await AccountRepository.get_all_accounts()
    await ws_manager.broadcast_log(
        "GENERATOR",
        f"Generated {created} new accounts with prefix '{payload.prefix}' and saved to accounts.txt!"
    )
    return JSONResponse(content={"created": created, "accounts": accounts})


@router.post("/api/settings/concurrency")
async def update_concurrency(payload: ConcurrencyRequest) -> JSONResponse:
    active_workers: int = inspector_service.set_concurrency(payload.workers)
    await ws_manager.broadcast_log(
        "SYSTEM",
        f"Parallel Multi-Window Engine set to {active_workers} concurrent threads (with automated Win32 click queue)."
    )
    return JSONResponse(content={"workers": active_workers})


@router.post("/api/accounts/{account_id}/run")
async def run_single_account(account_id: int) -> JSONResponse:
    asyncio.create_task(inspector_service.process_account(account_id))
    return JSONResponse(content={"status": "started", "account_id": account_id})


@router.post("/api/accounts/run-all")
async def run_all_accounts() -> JSONResponse:
    accounts: list[dict[str, Optional[str | int]]] = await AccountRepository.get_all_accounts()
    for item in accounts:
        acc_id: Optional[str | int] = item.get("id")
        if isinstance(acc_id, int):
            asyncio.create_task(inspector_service.process_account(acc_id))
    return JSONResponse(content={"status": "started_all", "count": len(accounts)})


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket client closed with error: {exc}")
        ws_manager.disconnect(websocket)