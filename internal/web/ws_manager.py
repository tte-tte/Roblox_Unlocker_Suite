import datetime
import json
import logging
from typing import Optional
from fastapi import WebSocket

logger: logging.Logger = logging.getLogger("roblox_suite.websocket")


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, payload: dict[str, object]) -> None:
        disconnected: list[WebSocket] = []
        message_str: str = json.dumps(payload)
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception:
                disconnected.append(connection)
        for dead in disconnected:
            self.disconnect(dead)

    async def broadcast_log(self, username: str, message: str, level: str = "INFO") -> None:
        now_str: str = datetime.datetime.now().strftime("%H:%M:%S")
        await self.broadcast_json({
            "type": "log",
            "timestamp": now_str,
            "username": username,
            "level": level,
            "message": message
        })

    async def broadcast_account_update(self, account_data: dict[str, Optional[str | int]]) -> None:
        await self.broadcast_json({
            "type": "account_update",
            "account": account_data
        })


ws_manager: WebSocketManager = WebSocketManager()