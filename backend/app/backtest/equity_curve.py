from datetime import datetime


def compute_equity_curve(trades: list, initial_cash: float) -> list[dict]:
    equity_curve = [{"timestamp": None, "equity": initial_cash}]
    running_cash = initial_cash

    for trade in trades:
        running_cash += trade.pnl
        equity_curve.append({
            "timestamp": str(trade.exit_timestamp),
            "equity": round(running_cash, 4),
        })

    return equity_curve


def compute_max_drawdown(equity_curve: list[dict]) -> float | None:
    if len(equity_curve) < 2:
        return None

    peak = equity_curve[0]["equity"]
    max_drawdown = 0.0

    for point in equity_curve:
        equity = point["equity"]
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return round(max_drawdown, 6)


def compute_total_return_pct(initial_cash: float, final_cash: float) -> float:
    if initial_cash == 0:
        return 0.0
    return round((final_cash - initial_cash) / initial_cash, 6)


def compute_cagr(initial_cash: float, final_cash: float, start_timestamp, end_timestamp) -> float | None:
    if initial_cash <= 0 or final_cash <= 0:
        return None

    start_date = start_timestamp if isinstance(start_timestamp, datetime) else datetime.fromisoformat(str(start_timestamp))
    end_date = end_timestamp if isinstance(end_timestamp, datetime) else datetime.fromisoformat(str(end_timestamp))

    days_elapsed = (end_date - start_date).days
    if days_elapsed <= 0:
        return None

    years_elapsed = days_elapsed / 365.25
    if years_elapsed <= 0:
        return None

    cagr = (final_cash / initial_cash) ** (1 / years_elapsed) - 1
    return round(cagr, 6)