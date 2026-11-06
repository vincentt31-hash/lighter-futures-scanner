"""Exchange-aware position sizing for Bybit linear USDT contracts.

Calculations are estimates for analysis/paper trading. They exclude fees,
funding, slippage, maintenance margin tiers, and liquidation-price mechanics.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any


def _d(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field}")
    if not result.is_finite():
        raise ValueError(f"Invalid {field}")
    return result


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("qtyStep must be greater than zero")
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _ceil_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("tickSize must be greater than zero")
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def _round_nearest(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("tickSize must be greater than zero")
    return (value / step).to_integral_value(rounding=ROUND_HALF_UP) * step


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


def size_linear_position(
    *,
    side: str,
    entry: Any,
    stop_loss: Any,
    capital_usdt: Any,
    risk_percent: Any,
    max_leverage: Any,
    instrument: dict[str, Any],
    take_profits: list[Any] | None = None,
) -> dict[str, Any]:
    """Calculate a rounded, exchange-filter-aware linear contract position."""
    side = str(side).upper()
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")

    entry_d = _d(entry, "entry")
    stop_d = _d(stop_loss, "stop_loss")
    capital = _d(capital_usdt, "capital_usdt")
    risk_pct = _d(risk_percent, "risk_percent")
    leverage_cap = _d(max_leverage, "max_leverage")

    if min(entry_d, stop_d, capital, risk_pct, leverage_cap) <= 0:
        raise ValueError("Entry, stop, capital, risk and leverage must be positive")
    if risk_pct > 10:
        raise ValueError("risk_percent cannot exceed 10")
    if side == "LONG" and stop_d >= entry_d:
        raise ValueError("LONG stop loss must be below entry")
    if side == "SHORT" and stop_d <= entry_d:
        raise ValueError("SHORT stop loss must be above entry")

    lot = instrument.get("lotSizeFilter") or {}
    price_filter = instrument.get("priceFilter") or {}
    tick = _d(price_filter.get("tickSize"), "tickSize")
    step = _d(lot.get("qtyStep"), "qtyStep")
    min_qty = _d(lot.get("minOrderQty"), "minOrderQty")
    min_notional_raw = lot.get("minNotionalValue")
    min_notional = _d(min_notional_raw, "minNotionalValue") if min_notional_raw not in (None, "") else Decimal("0")

    # Round entry to nearest tick. Round stop toward entry to avoid
    # accidentally increasing the intended stop distance due to tick rounding.
    rounded_entry = _round_nearest(entry_d, tick)
    rounded_stop = (
        _ceil_step(stop_d, tick) if side == "LONG" else
        (stop_d / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    )
    if side == "LONG" and rounded_stop >= rounded_entry:
        raise ValueError("Rounded LONG stop is not below rounded entry")
    if side == "SHORT" and rounded_stop <= rounded_entry:
        raise ValueError("Rounded SHORT stop is not above rounded entry")

    distance = abs(rounded_entry - rounded_stop)
    stop_fraction = distance / rounded_entry
    risk_budget = capital * risk_pct / Decimal("100")
    target_notional = risk_budget / stop_fraction
    leverage = min(leverage_cap, Decimal("125"))
    leverage_notional_cap = capital * leverage
    notional = min(target_notional, leverage_notional_cap)
    raw_qty = notional / rounded_entry
    quantity = _floor_step(raw_qty, step)

    # Round profit targets away from entry, so the target is not accidentally
    # closer than requested after tick-size normalization.
    rounded_tps: list[str] = []
    for target in take_profits or []:
        target_d = _d(target, "take_profit")
        if side == "LONG":
            rounded_target = _ceil_step(target_d, tick)
            if rounded_target <= rounded_entry:
                raise ValueError("LONG take profit must be above entry")
        else:
            rounded_target = (target_d / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
            if rounded_target >= rounded_entry:
                raise ValueError("SHORT take profit must be below entry")
        rounded_tps.append(_fmt(rounded_target))

    rounded_notional = quantity * rounded_entry
    estimated_loss = quantity * distance
    estimated_margin = rounded_notional / leverage
    actual_leverage = rounded_notional / capital if capital else Decimal("0")
    reasons: list[str] = []

    if quantity < min_qty:
        reasons.append("Rounded quantity is below Bybit minOrderQty")
    if min_notional > 0 and rounded_notional < min_notional:
        reasons.append("Rounded position value is below Bybit minNotionalValue")
    if quantity <= 0:
        reasons.append("Rounded quantity is zero")

    tradeable = not reasons
    return {
        "tradeable_size": tradeable,
        "validation_errors": reasons,
        "entry_rounded": _fmt(rounded_entry),
        "stop_loss_rounded": _fmt(rounded_stop),
        "take_profits_rounded": rounded_tps,
        "tick_size": _fmt(tick),
        "qty_step": _fmt(step),
        "min_order_qty": _fmt(min_qty),
        "min_notional_value": _fmt(min_notional),
        "quantity": _fmt(quantity),
        "position_value_usdt": _fmt(rounded_notional),
        "risk_budget_usdt": _fmt(risk_budget),
        "estimated_loss_at_stop_usdt": _fmt(estimated_loss),
        "estimated_margin_usdt": _fmt(estimated_margin),
        "estimated_leverage": round(float(actual_leverage), 4),
        "leverage_cap": float(leverage),
        "stop_distance_pct": round(float(stop_fraction * 100), 6),
        "risk_budget_utilization_pct": round(
            float(estimated_loss / risk_budget * 100), 4
        ) if risk_budget > 0 else 0,
        "notional_capped_by_leverage": target_notional > leverage_notional_cap,
        "calculation_note": (
            "Linear USDT estimate. Excludes fees, funding, slippage, "
            "maintenance margin tiers and liquidation mechanics."
        ),
    }
