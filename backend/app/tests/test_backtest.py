import json
import math
import pandas as pd
import pytest
from app.backtest.engine import run_backtest
from app.backtest.metrics import cagr, daily_returns, max_drawdown, sharpe_ratio

NAN = float("nan")
INITIAL_CAPITAL = 100000.0
FEE_BPS = 10.0
SLIPPAGE_BPS = 5.0
FEE = 0.001
SLIP = 0.0005

OPENS = [100.0, 102.0, 104.0, 103.0, 106.0, 108.0]
CLOSES = [101.0, 103.0, 102.0, 105.0, 107.0, 107.0]
HIGHS = [102.0, 104.0, 105.0, 106.0, 108.0, 109.0]
LOWS = [99.0, 101.0, 101.0, 102.0, 105.0, 106.0]
SIGNALS = [1, 1, 0, -1, -1, 0]


def frame(opens, closes, highs=None, lows=None, start="2024-01-01") -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range(start, periods=len(opens), freq="D").strftime("%Y-%m-%d"),
        "open": opens,
        "high": highs if highs is not None else [max(o, c) for o, c in zip(opens, closes)],
        "low": lows if lows is not None else [min(o, c) for o, c in zip(opens, closes)],
        "close": closes,
        "volume": [1000.0] * len(opens),
    })


def six_bar_result():
    return run_backtest(frame(OPENS, CLOSES, HIGHS, LOWS), SIGNALS, FEE_BPS, SLIPPAGE_BPS, INITIAL_CAPITAL)


def test_six_bar_fills_returns_costs_and_equity():
    result = six_bar_result()
    long_fill = OPENS[1] * (1 + SLIP)
    long_units = INITIAL_CAPITAL / long_fill
    cash_after_long_entry = -INITIAL_CAPITAL * FEE
    long_exit_fill = OPENS[3] * (1 - SLIP)
    long_exit_fee = long_units * long_exit_fill * FEE
    cash_after_long_exit = cash_after_long_entry + long_units * long_exit_fill - long_exit_fee
    short_fill = OPENS[4] * (1 - SLIP)
    short_units = -cash_after_long_exit / short_fill
    cash_after_short_entry = cash_after_long_exit - short_units * short_fill - cash_after_long_exit * FEE
    short_exit_fill = CLOSES[5] * (1 + SLIP)
    short_exit_fee = abs(short_units) * short_exit_fill * FEE
    final_cash = cash_after_short_entry + short_units * short_exit_fill - short_exit_fee

    expected_equity = [
        INITIAL_CAPITAL,
        cash_after_long_entry + long_units * CLOSES[1],
        cash_after_long_entry + long_units * CLOSES[2],
        cash_after_long_exit,
        cash_after_short_entry + short_units * CLOSES[4],
        final_cash,
    ]
    assert [point["equity"] for point in result["equity_curve"]] == pytest.approx(expected_equity, rel=1e-12)

    first, second = result["trades"]
    assert first["side"] == "long"
    assert first["entry_price"] == pytest.approx(long_fill)
    assert first["exit_price"] == pytest.approx(long_exit_fill)
    assert first["entry_date"] == "2024-01-02" and first["exit_date"] == "2024-01-04"
    assert first["entry_bar_index"] == 1 and first["signal_bar_index"] == 0
    assert first["bars_held"] == 2
    assert first["return"] == pytest.approx(cash_after_long_exit / INITIAL_CAPITAL - 1)
    assert first["pnl"] == pytest.approx(cash_after_long_exit - INITIAL_CAPITAL)
    long_slippage = long_units * (long_fill - OPENS[1]) + long_units * (OPENS[3] - long_exit_fill)
    assert first["costs"] == pytest.approx(INITIAL_CAPITAL * FEE + long_exit_fee + long_slippage)
    assert first["mfe"] == pytest.approx(max(HIGHS[1:3]) / long_fill - 1)
    assert first["mae"] == pytest.approx(min(LOWS[1:3]) / long_fill - 1)
    assert first["closed_at_end"] is False

    assert second["side"] == "short"
    assert second["entry_price"] == pytest.approx(short_fill)
    assert second["exit_price"] == pytest.approx(short_exit_fill)
    assert second["closed_at_end"] is True
    assert second["bars_held"] == 2
    assert second["return"] == pytest.approx(final_cash / cash_after_long_exit - 1)
    assert second["mfe"] == pytest.approx(1 - min(LOWS[4:6]) / short_fill)
    assert second["mae"] == pytest.approx(1 - max(HIGHS[4:6]) / short_fill)
    assert result["position_per_bar"] == [0, 1, 1, 0, -1, -1]


def test_round_trip_cost_with_fee_10_bps_and_slippage_5_bps():
    flat_price = 100.0
    result = run_backtest(frame([flat_price] * 4, [flat_price] * 4), [1, 0, 0, 0], FEE_BPS, SLIPPAGE_BPS, INITIAL_CAPITAL)
    entry_fill = flat_price * (1 + SLIP)
    exit_fill = flat_price * (1 - SLIP)
    units = INITIAL_CAPITAL / entry_fill
    hand_costs = INITIAL_CAPITAL * FEE + units * exit_fill * FEE + units * (entry_fill - flat_price) + units * (flat_price - exit_fill)
    hand_final = INITIAL_CAPITAL - INITIAL_CAPITAL * FEE - units * entry_fill + units * exit_fill * (1 - FEE)

    trade = result["trades"][0]
    assert trade["costs"] == pytest.approx(hand_costs)
    assert trade["pnl"] == pytest.approx(-hand_costs)
    assert result["equity_curve"][-1]["equity"] == pytest.approx(hand_final)
    assert result["metrics"]["strategy"]["total_costs_pct_of_initial"] == pytest.approx(hand_costs / INITIAL_CAPITAL)


def test_short_trade_profits_when_price_falls():
    prices = [100.0, 100.0, 95.0, 90.0, 85.0]
    result = run_backtest(frame(prices, prices), [-1, -1, -1, 0, 0], 0.0, 0.0, INITIAL_CAPITAL)
    trade = result["trades"][0]
    assert trade["side"] == "short"
    assert trade["return"] == pytest.approx(1 - 85.0 / 100.0)
    assert trade["pnl"] > 0


def test_nan_signal_keeps_the_position_and_is_counted():
    prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    result = run_backtest(frame(prices, prices), [1, NAN, None, 1, 0, 0], 0.0, 0.0, INITIAL_CAPITAL)
    assert result["ignored_bar_count"] == 2
    assert result["metrics"]["strategy"]["ignored_bar_count"] == 2
    assert len(result["trades"]) == 1
    assert result["trades"][0]["entry_bar_index"] == 1
    assert result["trades"][0]["exit_bar_index"] == 5
    assert result["position_per_bar"] == [0, 1, 1, 1, 1, 0]


def test_position_open_on_last_bar_is_closed_with_flag():
    prices = [100.0, 100.0, 110.0]
    result = run_backtest(frame(prices, prices), [1, 1, 1], FEE_BPS, SLIPPAGE_BPS, INITIAL_CAPITAL)
    trade = result["trades"][0]
    assert trade["closed_at_end"] is True
    assert trade["exit_date"] == "2024-01-03"
    assert trade["exit_price"] == pytest.approx(110.0 * (1 - SLIP))


def test_last_bar_signal_never_executes():
    prices = [100.0, 100.0, 100.0]
    result = run_backtest(frame(prices, prices), [0, 0, 1], 0.0, 0.0, INITIAL_CAPITAL)
    assert result["trades"] == []


def test_sharpe_is_null_for_two_point_and_constant_growth():
    assert sharpe_ratio(daily_returns([100.0, 110.0])) is None
    assert sharpe_ratio(daily_returns([100.0, 110.0, 121.0, 133.1])) is None


def test_sharpe_matches_hand_value():
    returns = [0.01, -0.02, 0.03]
    mean = (0.01 - 0.02 + 0.03) / 3
    variance = ((0.01 - mean) ** 2 + (-0.02 - mean) ** 2 + (0.03 - mean) ** 2) / 2
    assert sharpe_ratio(returns) == pytest.approx(mean / math.sqrt(variance) * math.sqrt(252))


def test_marked_to_market_drawdown_sees_the_dip_inside_a_trade():
    opens = [100.0, 100.0, 90.0, 100.0, 120.0, 120.0]
    closes = [100.0, 100.0, 80.0, 100.0, 120.0, 120.0]
    result = run_backtest(frame(opens, closes), [1, 1, 1, 1, 0, 0], 0.0, 0.0, INITIAL_CAPITAL)
    exit_only_equity = [INITIAL_CAPITAL, result["equity_curve"][-1]["equity"]]
    assert max_drawdown(exit_only_equity) == 0.0
    assert result["metrics"]["strategy"]["max_drawdown"] == pytest.approx(80.0 / 100.0 - 1)
    assert result["metrics"]["strategy"]["longest_drawdown_days"] == 2


def test_cagr_is_null_under_one_year_and_computed_for_two_years():
    assert cagr([100.0, 121.0], ["2020-01-01", "2020-12-30"]) is None
    assert cagr([100.0, 121.0], ["2020-01-01", "2021-12-31"]) == pytest.approx(1.21 ** (365.25 / 730) - 1)


def test_benchmark_total_return_is_last_close_over_first_open_minus_costs():
    result = six_bar_result()
    expected = CLOSES[-1] / (OPENS[1] * (1 + SLIP)) - 1 - FEE
    benchmark = result["metrics"]["benchmark"]
    assert benchmark["total_return"] == pytest.approx(expected)
    assert result["benchmark_equity_curve"][-1]["equity"] == pytest.approx(INITIAL_CAPITAL * (1 + expected))
    assert benchmark["n_trades"] == 1
    assert benchmark["correlation_to_benchmark"] == pytest.approx(1.0)
    assert benchmark["beta_to_benchmark"] == pytest.approx(1.0)


def test_metrics_contain_every_field():
    metrics = six_bar_result()["metrics"]["strategy"]
    assert set(metrics) == {
        "total_return", "cagr", "sharpe", "sortino", "annualized_volatility", "max_drawdown",
        "longest_drawdown_days", "calmar", "var_95_daily", "best_day", "worst_day", "win_rate",
        "profit_factor", "avg_win", "avg_loss", "best_trade", "worst_trade", "avg_bars_held",
        "n_trades", "n_long", "n_short", "time_in_market_long", "time_in_market_short",
        "round_trips_per_year", "total_costs_pct_of_initial", "correlation_to_benchmark",
        "beta_to_benchmark", "ignored_bar_count",
    }
    assert metrics["n_long"] == 1 and metrics["n_short"] == 1
    assert metrics["time_in_market_long"] == pytest.approx(2 / 6)
    assert metrics["time_in_market_short"] == pytest.approx(2 / 6)


def test_result_never_contains_nan_or_infinity():
    flat = [100.0] * 5
    for signals in ([NAN] * 5, [1, NAN, 0, NAN, 1], [0] * 5):
        result = run_backtest(frame(flat, flat), signals, FEE_BPS, SLIPPAGE_BPS, INITIAL_CAPITAL)
        json.dumps(result, allow_nan=False)
    json.dumps(six_bar_result(), allow_nan=False)
    json.dumps(run_backtest(frame([100.0], [100.0]), [1]), allow_nan=False)
