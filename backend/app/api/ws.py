from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.auth import verify_token
from app.env import ENV

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    if ENV.dashboard_auth_enabled:
        token = websocket.query_params.get("token")
        if not verify_token(token):
            await websocket.close(code=1008, reason="Unauthorized")
            return
    runtime = websocket.app.state.runtime
    bus = websocket.app.state.bus
    await bus.connect(websocket)
    try:
        await websocket.send_json({"type": "hello", "payload": runtime.snapshot()})
        while True:
            text = await websocket.receive_text()
            if text.strip() == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await bus.disconnect(websocket)
