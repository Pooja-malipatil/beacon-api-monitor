import json
import asyncio
from typing import Dict, List, Optional
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None  # set once at startup

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        connections = self.active_connections.get(user_id, [])
        dead_connections = []
        for connection in connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(user_id, dead)


manager = ConnectionManager()


def broadcast_update(user_id: str, message: dict):
    if manager.loop is None:
        print("WebSocket broadcast skipped: no event loop registered yet")
        return
    asyncio.run_coroutine_threadsafe(manager.send_to_user(user_id, message), manager.loop)