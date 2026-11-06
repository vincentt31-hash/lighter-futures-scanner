from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from ...services.market_manager import market_manager

router = APIRouter(tags=["market"])


@router.get("/market/symbols")
async def get_symbols():
    """Return configured instruments and their live Bybit availability."""
    try:
        return await market_manager.get_symbol_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Market provider unavailable: {exc}")


@router.get("/market/overview")
async def get_overview():
    return await market_manager.get_overview()


@router.get("/market/klines/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = Query("15", description="Supported intervals: 1, 5, 15, 60, 240, D"),
    limit: int = Query(200, ge=1, le=1000),
):
    symbol = symbol.upper()
    try:
        return await market_manager.get_klines(symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to retrieve klines: {exc}")


@router.websocket("/ws/market")
async def market_stream(websocket: WebSocket):
    """Push normalized public market events to Android clients."""
    await websocket.accept()
    queue = market_manager.subscribe()
    try:
        # Send a current snapshot first, then stream updates.
        await websocket.send_json({
            "type": "snapshot",
            "data": await market_manager.get_overview(),
        })
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        market_manager.unsubscribe(queue)
