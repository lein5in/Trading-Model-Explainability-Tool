import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from app.backtest.metrics import compute_metrics

DEFAULT_INITIAL_CAPITAL = 100000.0
DEFAULT_FEE_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 2.0
BPS = 10000.0
LONG = 1
SHORT = -1
FLAT = 0


@dataclass
class Fill:
    price: float
    fee: float
    slippage_cost: float


@dataclass
class OpenPosition:
    side: int
    units: float
    entry_fill: Fill
    entry_bar_index: int
    equity_before_entry: float


@dataclass
class Account:
    cash: float
    fee_rate: float
    slippage_rate: float
    position: OpenPosition | None = None
    trades: list = field(default_factory=list)

    def enter(self, side: int, raw_price: float, bar_index: int) -> None:
        equity = self.cash
        price = raw_price * (1 + self.slippage_rate) if side == LONG else raw_price * (1 - self.slippage_rate)
        units = side * equity / price
        fee = abs(units) * price * self.fee_rate
        self.cash -= units * price + fee
        self.position = OpenPosition(
            side=side,
            units=units,
            entry_fill=Fill(price, fee, abs(units) * abs(price - raw_price)),
            entry_bar_index=bar_index,
            equity_before_entry=equity,
        )

    def exit(self, raw_price: float, bar_index: int, closed_at_end: bool) -> dict:
        position = self.position
        side = position.side
        price = raw_price * (1 - self.slippage_rate) if side == LONG else raw_price * (1 + self.slippage_rate)
        fee = abs(position.units) * price * self.fee_rate
        self.cash += position.units * price - fee
        exit_fill = Fill(price, fee, abs(position.units) * abs(price - raw_price))
        self.position = None
        pnl = self.cash - position.equity_before_entry
        return {
            "side": "long" if side == LONG else "short",
            "side_sign": side,
            "entry_bar_index": position.entry_bar_index,
            "exit_bar_index": bar_index,
            "entry_price": position.entry_fill.price,
            "exit_price": exit_fill.price,
            "pnl": pnl,
            "return": pnl / position.equity_before_entry,
            "costs": position.entry_fill.fee + exit_fill.fee + position.entry_fill.slippage_cost + exit_fill.slippage_cost,
            "fees": position.entry_fill.fee + exit_fill.fee,
            "closed_at_end": closed_at_end,
        }

    def equity(self, mark_price: float) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.position.units * mark_price


def is_missing(signal) -> bool:
    if signal is None:
        return True
    try:
        return math.isnan(float(signal))
    except (TypeError, ValueError):
        return True


def signal_to_side(signal) -> int:
    value = float(signal)
    if value > 0:
        return LONG
    if value < 0:
        return SHORT
    return FLAT


def excursions(side: int, entry_price: float, highs: np.ndarray, lows: np.ndarray) -> tuple[float, float]:
    if side == LONG:
        return float(highs.max() / entry_price - 1), float(lows.min() / entry_price - 1)
    return float(1 - lows.min() / entry_price), float(1 - highs.max() / entry_price)


def finalize_trade(raw: dict, trade_id: int, dates: list[str], highs: np.ndarray, lows: np.ndarray) -> dict:
    entry_index = raw["entry_bar_index"]
    exit_index = raw["exit_bar_index"]
    last_held = exit_index if raw["closed_at_end"] else exit_index - 1
    bars_held = last_held - entry_index + 1
    mfe, mae = excursions(raw["side_sign"], raw["entry_price"], highs[entry_index:last_held + 1], lows[entry_index:last_held + 1])
    return {
        "id": trade_id,
        "side": raw["side"],
        "entry_date": dates[entry_index],
        "exit_date": dates[exit_index],
        "entry_price": raw["entry_price"],
        "exit_price": raw["exit_price"],
        "return": raw["return"],
        "pnl": raw["pnl"],
        "bars_held": bars_held,
        "costs": raw["costs"],
        "entry_bar_index": entry_index,
        "signal_bar_index": entry_index - 1,
        "exit_bar_index": exit_index,
        "mfe": mfe,
        "mae": mae,
        "closed_at_end": raw["closed_at_end"],
        "regime": None,
    }


def simulate_strategy(df: pd.DataFrame, signals: list, fee_rate: float, slippage_rate: float, initial_capital: float) -> dict:
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    n = len(df)
    account = Account(cash=initial_capital, fee_rate=fee_rate, slippage_rate=slippage_rate)
    raw_trades = []
    equity = []
    sides = []
    target = FLAT
    ignored_bar_count = 0

    for index in range(n):
        if index > 0:
            current = account.position.side if account.position is not None else FLAT
            if target != current:
                if account.position is not None:
                    raw_trades.append(account.exit(opens[index], index, closed_at_end=False))
                if target != FLAT:
                    account.enter(target, opens[index], index)
        if index == n - 1 and account.position is not None:
            sides.append(account.position.side)
            raw_trades.append(account.exit(closes[index], index, closed_at_end=True))
            equity.append(account.cash)
        else:
            sides.append(account.position.side if account.position is not None else FLAT)
            equity.append(account.equity(closes[index]))

        signal = signals[index] if index < len(signals) else None
        if is_missing(signal):
            ignored_bar_count += 1
        else:
            target = signal_to_side(signal)

    return {"equity": equity, "raw_trades": raw_trades, "sides": sides, "ignored_bar_count": ignored_bar_count}


def simulate_buy_and_hold(df: pd.DataFrame, fee_rate: float, slippage_rate: float, initial_capital: float) -> dict:
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    n = len(df)
    if n < 2:
        return {"equity": [initial_capital] * n, "raw_trades": [], "sides": [FLAT] * n}
    account = Account(cash=initial_capital, fee_rate=fee_rate, slippage_rate=slippage_rate)
    equity = [initial_capital]
    account.enter(LONG, opens[1], 1)
    for index in range(1, n):
        equity.append(account.equity(closes[index]))
    position = account.position
    final_value = equity[-1]
    raw_trade = {
        "side": "long",
        "side_sign": LONG,
        "entry_bar_index": 1,
        "exit_bar_index": n - 1,
        "entry_price": position.entry_fill.price,
        "exit_price": float(closes[-1]),
        "pnl": final_value - initial_capital,
        "return": final_value / initial_capital - 1,
        "costs": position.entry_fill.fee + position.entry_fill.slippage_cost,
        "fees": position.entry_fill.fee,
        "closed_at_end": True,
    }
    return {"equity": equity, "raw_trades": [raw_trade], "sides": [FLAT] + [LONG] * (n - 1)}


def run_backtest(
    ohlcv: pd.DataFrame,
    signals: list,
    fee_bps: float = DEFAULT_FEE_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> dict:
    df = ohlcv.reset_index(drop=True)
    dates = [str(value) for value in df["date"]]
    highs = df["high"].to_numpy(dtype=float) if "high" in df else df["close"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float) if "low" in df else df["close"].to_numpy(dtype=float)
    fee_rate = fee_bps / BPS
    slippage_rate = slippage_bps / BPS

    strategy = simulate_strategy(df, list(signals), fee_rate, slippage_rate, initial_capital)
    benchmark = simulate_buy_and_hold(df, fee_rate, slippage_rate, initial_capital)

    trades = [finalize_trade(raw, i + 1, dates, highs, lows) for i, raw in enumerate(strategy["raw_trades"])]
    benchmark_trades = [finalize_trade(raw, i + 1, dates, highs, lows) for i, raw in enumerate(benchmark["raw_trades"])]

    benchmark_metrics = compute_metrics(
        dates, benchmark["equity"], benchmark_trades, benchmark["sides"], initial_capital, benchmark["equity"], 0,
    )
    strategy_metrics = compute_metrics(
        dates, strategy["equity"], trades, strategy["sides"], initial_capital, benchmark["equity"], strategy["ignored_bar_count"],
    )

    return {
        "initial_capital": initial_capital,
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "equity_curve": [{"date": d, "equity": e} for d, e in zip(dates, strategy["equity"])],
        "benchmark_equity_curve": [{"date": d, "equity": e} for d, e in zip(dates, benchmark["equity"])],
        "position_per_bar": strategy["sides"],
        "trades": trades,
        "metrics": {"strategy": strategy_metrics, "benchmark": benchmark_metrics},
        "ignored_bar_count": strategy["ignored_bar_count"],
    }
