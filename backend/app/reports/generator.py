import math
import anthropic
from app.config import ANTHROPIC_API_KEY
from app.reports.prompts import (
    REPORT_SYSTEM_PROMPT,
    EXPLAIN_SECTION_SYSTEM_PROMPT,
    build_full_report_prompt,
    build_section_explanation_prompt,
)

REPORT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2000
TRADING_PERIODS_PER_YEAR = 252


class ReportGenerationError(Exception):
    pass


def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ReportGenerationError("ANTHROPIC_API_KEY is not configured.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def compute_trade_statistics(trades: list) -> dict:
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": None,
            "sharpe_ratio": None,
            "avg_pnl": None,
            "total_pnl": 0.0,
        }

    pnls = [t.pnl for t in trades]
    win_count = sum(1 for pnl in pnls if pnl > 0)
    win_rate = win_count / len(pnls)
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / len(pnls)

    if len(pnls) > 1:
        mean_pnl = avg_pnl
        variance = sum((pnl - mean_pnl) ** 2 for pnl in pnls) / (len(pnls) - 1)
        std_pnl = math.sqrt(variance)
        sharpe_ratio = (mean_pnl / std_pnl) * math.sqrt(TRADING_PERIODS_PER_YEAR) if std_pnl > 0 else None
    else:
        sharpe_ratio = None

    return {
        "trade_count": len(pnls),
        "win_rate": round(win_rate, 4),
        "sharpe_ratio": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
        "avg_pnl": round(avg_pnl, 4),
        "total_pnl": round(total_pnl, 4),
    }


def compute_regime_behavior(trades: list, regime_per_bar: list, ohlcv_index_by_timestamp: dict) -> dict:
    regime_pnls = {}

    for trade in trades:
        position = ohlcv_index_by_timestamp.get(trade.entry_timestamp)
        if position is None:
            continue
        regime = regime_per_bar[position]
        if regime is None:
            continue
        regime_pnls.setdefault(regime, []).append(trade.pnl)

    regime_behavior = {}
    for regime, pnls in regime_pnls.items():
        regime_behavior[regime] = {
            "trade_count": len(pnls),
            "total_pnl": round(sum(pnls), 4),
            "avg_pnl": round(sum(pnls) / len(pnls), 4),
        }

    return regime_behavior


def build_notable_trades(trades: list, feature_importance: dict, top_n: int = 3) -> list:
    sorted_trades = sorted(trades, key=lambda t: abs(t.pnl), reverse=True)
    top_trades = sorted_trades[:top_n]

    notable = []
    for t in top_trades:
        notable.append({
            "entry_timestamp": str(t.entry_timestamp),
            "direction": t.direction,
            "pnl": round(t.pnl, 4),
            "feature_vector_at_entry": t.feature_vector,
        })
    return notable


def assemble_report_data(
    model_name: str,
    ohlcv,
    trades: list,
    feature_importance: dict,
    regime_result: dict,
) -> dict:
    trade_stats = compute_trade_statistics(trades)

    timestamp_to_position = {
        row["timestamp"]: idx for idx, row in ohlcv.iterrows()
    }

    regime_behavior = compute_regime_behavior(
        trades, regime_result["regime_per_bar"], timestamp_to_position
    )

    notable_trades = build_notable_trades(trades, feature_importance)

    return {
        "model_name": model_name,
        "period": {
            "start": str(ohlcv["timestamp"].iloc[0]),
            "end": str(ohlcv["timestamp"].iloc[-1]),
        },
        "backtest_statistics": trade_stats,
        "feature_importance": {k: round(v, 4) for k, v in feature_importance.items()},
        "regime_behavior": regime_behavior,
        "time_in_regime_pct": regime_result["time_in_regime_pct"],
        "notable_trades": notable_trades,
    }


def generate_full_report(report_data: dict) -> str:
    client = _get_client()
    prompt = build_full_report_prompt(report_data)

    try:
        response = client.messages.create(
            model=REPORT_MODEL,
            max_tokens=MAX_TOKENS,
            system=REPORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise ReportGenerationError(f"Anthropic API call failed: {exc}")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_blocks)


def generate_section_explanation(section_name: str, section_data: dict) -> str:
    client = _get_client()
    prompt = build_section_explanation_prompt(section_name, section_data)

    try:
        response = client.messages.create(
            model=REPORT_MODEL,
            max_tokens=500,
            system=EXPLAIN_SECTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise ReportGenerationError(f"Anthropic API call failed: {exc}")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_blocks)