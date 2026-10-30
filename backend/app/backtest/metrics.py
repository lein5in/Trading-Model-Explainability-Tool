import math
from datetime import date
import numpy as np

TRADING_DAYS_PER_YEAR = 252
DAYS_PER_YEAR = 365.25
MIN_CAGR_DAYS = 365
STD_EPSILON = 1e-12
VAR_CONFIDENCE = 0.95
VAR_PERCENTILE = round((1 - VAR_CONFIDENCE) * 100)


def finite_or_none(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def daily_returns(equity) -> np.ndarray:
    values = np.asarray(equity, dtype=float)
    if len(values) < 2:
        return np.array([])
    return values[1:] / values[:-1] - 1.0


def sample_std(values: np.ndarray) -> float | None:
    if len(values) < 2:
        return None
    return float(np.std(values, ddof=1))


def sharpe_ratio(returns) -> float | None:
    values = np.asarray(returns, dtype=float)
    std = sample_std(values)
    if std is None or std <= STD_EPSILON:
        return None
    return finite_or_none(values.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(returns) -> float | None:
    values = np.asarray(returns, dtype=float)
    if len(values) < 2:
        return None
    downside = math.sqrt(float(np.mean(np.minimum(values, 0.0) ** 2)))
    if downside <= STD_EPSILON:
        return None
    return finite_or_none(values.mean() / downside * math.sqrt(TRADING_DAYS_PER_YEAR))


def annualized_volatility(returns) -> float | None:
    std = sample_std(np.asarray(returns, dtype=float))
    return None if std is None else finite_or_none(std * math.sqrt(TRADING_DAYS_PER_YEAR))


def period_days(dates: list[str]) -> int:
    if len(dates) < 2:
        return 0
    return (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days


def cagr(equity, dates: list[str]) -> float | None:
    days = period_days(dates)
    if days < MIN_CAGR_DAYS or equity[0] <= 0 or equity[-1] <= 0:
        return None
    return finite_or_none((equity[-1] / equity[0]) ** (DAYS_PER_YEAR / days) - 1.0)


def max_drawdown(equity) -> float:
    values = np.asarray(equity, dtype=float)
    if len(values) == 0:
        return 0.0
    peaks = np.maximum.accumulate(values)
    return float(min((values / peaks - 1.0).min(), 0.0))


def longest_drawdown_days(equity, dates: list[str]) -> int:
    longest = 0
    peak = None
    peak_date = None
    in_drawdown = False
    for value, day in zip(equity, dates):
        current = date.fromisoformat(day)
        if peak is None or value >= peak:
            if in_drawdown:
                longest = max(longest, (current - peak_date).days)
            peak, peak_date, in_drawdown = value, current, False
        else:
            in_drawdown = True
    if in_drawdown and dates:
        longest = max(longest, (date.fromisoformat(dates[-1]) - peak_date).days)
    return longest


def correlation_and_beta(returns: np.ndarray, benchmark_returns: np.ndarray) -> tuple[float | None, float | None]:
    if len(returns) < 2 or len(returns) != len(benchmark_returns):
        return None, None
    strategy_std = float(np.std(returns, ddof=1))
    benchmark_std = float(np.std(benchmark_returns, ddof=1))
    if benchmark_std <= STD_EPSILON:
        return None, None
    covariance = float(np.cov(returns, benchmark_returns, ddof=1)[0, 1])
    beta = finite_or_none(covariance / benchmark_std ** 2)
    if strategy_std <= STD_EPSILON:
        return None, beta
    return finite_or_none(covariance / (strategy_std * benchmark_std)), beta


def mean_or_none(values: list[float]) -> float | None:
    return finite_or_none(sum(values) / len(values)) if values else None


def trade_statistics(trades: list[dict]) -> dict:
    returns = [trade["return"] for trade in trades]
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] < 0]
    gross_profit = sum(trade["pnl"] for trade in wins)
    gross_loss = sum(trade["pnl"] for trade in losses)
    return {
        "win_rate": len(wins) / len(trades) if trades else None,
        "profit_factor": finite_or_none(gross_profit / abs(gross_loss)) if losses else None,
        "avg_win": mean_or_none([trade["return"] for trade in wins]),
        "avg_loss": mean_or_none([trade["return"] for trade in losses]),
        "best_trade": max(returns) if returns else None,
        "worst_trade": min(returns) if returns else None,
        "avg_bars_held": mean_or_none([trade["bars_held"] for trade in trades]),
        "n_trades": len(trades),
        "n_long": sum(1 for trade in trades if trade["side"] == "long"),
        "n_short": sum(1 for trade in trades if trade["side"] == "short"),
    }


def compute_metrics(
    dates: list[str],
    equity: list[float],
    trades: list[dict],
    sides: list[int],
    initial_capital: float,
    benchmark_equity: list[float],
    ignored_bar_count: int,
) -> dict:
    returns = daily_returns(equity)
    benchmark_returns = daily_returns(benchmark_equity)
    days = period_days(dates)
    years = days / DAYS_PER_YEAR
    growth = cagr(equity, dates) if equity else None
    drawdown = max_drawdown(equity)
    correlation, beta = correlation_and_beta(returns, benchmark_returns)
    n_bars = len(sides)

    metrics = {
        "total_return": finite_or_none(equity[-1] / equity[0] - 1.0) if equity else None,
        "cagr": growth,
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "annualized_volatility": annualized_volatility(returns),
        "max_drawdown": drawdown,
        "longest_drawdown_days": longest_drawdown_days(equity, dates),
        "calmar": finite_or_none(growth / abs(drawdown)) if growth is not None and drawdown != 0 else None,
        "var_95_daily": float(np.percentile(returns, VAR_PERCENTILE)) if len(returns) else None,
        "best_day": float(returns.max()) if len(returns) else None,
        "worst_day": float(returns.min()) if len(returns) else None,
    }
    metrics.update(trade_statistics(trades))
    metrics.update({
        "time_in_market_long": sum(1 for side in sides if side > 0) / n_bars if n_bars else None,
        "time_in_market_short": sum(1 for side in sides if side < 0) / n_bars if n_bars else None,
        "round_trips_per_year": len(trades) / years if years > 0 else None,
        "total_costs_pct_of_initial": sum(trade["costs"] for trade in trades) / initial_capital,
        "correlation_to_benchmark": correlation,
        "beta_to_benchmark": beta,
        "ignored_bar_count": int(ignored_bar_count),
    })
    return metrics
