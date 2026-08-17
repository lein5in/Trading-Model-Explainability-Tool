import pandas as pd
from app.backtest.portfolio import Portfolio

DEFAULT_FEE_RATE = 0.001
DEFAULT_SLIPPAGE_RATE = 0.0005
DEFAULT_INITIAL_CASH = 10000.0


def signal_to_direction(signal, signal_type: str) -> int:
    if signal_type == "discrete":
        return int(signal)
    if signal > 0.1:
        return 1
    if signal < -0.1:
        return -1
    return 0


def run_backtest(
    ohlcv: pd.DataFrame,
    features: pd.DataFrame,
    signals: list,
    signal_type: str,
    fee_rate: float = DEFAULT_FEE_RATE,
    slippage_rate: float = DEFAULT_SLIPPAGE_RATE,
    initial_cash: float = DEFAULT_INITIAL_CASH,
) -> dict:
    portfolio = Portfolio(initial_cash=initial_cash)

    for i in range(len(ohlcv)):
        row = ohlcv.iloc[i]
        signal = signals[i]
        direction = signal_to_direction(signal, signal_type)
        feature_row = features.iloc[i].to_dict()

        if portfolio.has_open_position():
            if direction != portfolio.position_direction:
                portfolio.close_position(
                    price=row["close"],
                    timestamp=row["timestamp"],
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                if direction != 0:
                    portfolio.open_position(
                        direction=direction,
                        price=row["close"],
                        timestamp=row["timestamp"],
                        features=feature_row,
                    )
        else:
            if direction != 0:
                portfolio.open_position(
                    direction=direction,
                    price=row["close"],
                    timestamp=row["timestamp"],
                    features=feature_row,
                )

    if portfolio.has_open_position():
        last_row = ohlcv.iloc[-1]
        portfolio.close_position(
            price=last_row["close"],
            timestamp=last_row["timestamp"],
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )

    total_pnl = sum(t.pnl for t in portfolio.trades)

    return {
        "trades": portfolio.trades,
        "final_cash": portfolio.cash,
        "total_pnl": total_pnl,
        "trade_count": len(portfolio.trades),
    }