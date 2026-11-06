from fastapi import APIRouter

from app.services.market_manager import market_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    market_state = market_manager.health()
    return {
        "application": "CUAN SCANNER V2",
        "status": "ok",
        "provider": "bybit-indonesia",
        "market_data": market_state,
    }
