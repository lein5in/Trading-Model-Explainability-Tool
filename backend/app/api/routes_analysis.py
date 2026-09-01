from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import pandas as pd

from app.db.client import get_supabase_client
from app.db.models import AnalysisResultInsert
from app.auth.dependencies import get_current_user_id
from app.sandbox.runner import run_predict_in_sandbox
from app.backtest.engine import run_backtest, DEFAULT_INITIAL_CASH
from app.backtest.equity_curve import (
    compute_equity_curve,
    compute_max_drawdown,
    compute_total_return_pct,
    compute_cagr,
)
from app.regime.hmm_detector import detect_regimes
from app.explainability.shap_engine import (
    compute_shap_explanation,
    compute_global_feature_importance,
    compute_regime_segmented_feature_importance,
)
from app.reports.generator import (
    assemble_report_data,
    generate_full_report,
    generate_section_explanation,
    compute_trade_statistics,
)
from app.data.ingestion import fetch_ohlcv

router = APIRouter(prefix="/analysis", tags=["analysis"])


class RunAnalysisRequest(BaseModel):
    model_id: str
    ticker: str
    start: str
    end: str
    signal_type: str
    feature_columns: list[str]


class SectionExplanationRequest(BaseModel):
    analysis_id: str
    section_name: str
    trade_index: int | None = None


def _get_registered_model(model_id: str, user_id: str) -> dict:
    client = get_supabase_client()
    response = (
        client.table("registered_models")
        .select("*")
        .eq("id", model_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")
    return response.data[0]


def _get_analysis_result(analysis_id: str, user_id: str) -> dict:
    client = get_supabase_client()
    response = (
        client.table("analysis_results")
        .select("*")
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found.")
    return response.data[0]


@router.post("/run")
def run_analysis(request: RunAnalysisRequest, user_id: str = Depends(get_current_user_id)):
    registered_model = _get_registered_model(request.model_id, user_id)

    ingestion_result = fetch_ohlcv(request.ticker, request.start, request.end)
    ohlcv = ingestion_result["data"]

    if ohlcv.empty:
        raise HTTPException(status_code=400, detail="No valid OHLCV data returned for this ticker/date range.")

    missing_columns = [c for c in request.feature_columns if c not in ohlcv.columns]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Feature columns not found in OHLCV data: {missing_columns}",
        )

    features = ohlcv[request.feature_columns]
    records = features.to_dict(orient="records")

    try:
        sandbox_result = run_predict_in_sandbox(
            registered_model["file_path"], records, request.signal_type
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model execution failed: {exc}")

    backtest_result = run_backtest(
        ohlcv=ohlcv,
        features=features,
        signals=sandbox_result["predictions"],
        signal_type=request.signal_type,
    )

    equity_curve = compute_equity_curve(backtest_result["trades"], DEFAULT_INITIAL_CASH)
    max_drawdown = compute_max_drawdown(equity_curve)
    total_return_pct = compute_total_return_pct(DEFAULT_INITIAL_CASH, backtest_result["final_cash"])
    cagr = compute_cagr(
        DEFAULT_INITIAL_CASH,
        backtest_result["final_cash"],
        ohlcv["timestamp"].iloc[0],
        ohlcv["timestamp"].iloc[-1],
    )

    regime_result = detect_regimes(ohlcv)

    sample_size = min(30, len(features))
    background_size = min(50, len(features))
    random_sample_df = features.sample(n=sample_size, random_state=0)
    background_records = features.sample(n=background_size, random_state=1).to_dict(orient="records")

    trade_entry_positions = []
    for trade in backtest_result["trades"]:
        matches = ohlcv.index[ohlcv["timestamp"] == trade.entry_timestamp]
        if len(matches) > 0:
            trade_entry_positions.append(int(matches[0]))

    random_sample_positions = [ohlcv.index.get_loc(idx) for idx in random_sample_df.index]
    combined_positions = sorted(set(random_sample_positions) | set(trade_entry_positions))

    sample_df = features.iloc[combined_positions]
    sample_positions = combined_positions
    sample_regimes = [regime_result["regime_per_bar"][pos] for pos in sample_positions]

    try:
        explanation = compute_shap_explanation(
            model_storage_path=registered_model["file_path"],
            records=sample_df.to_dict(orient="records"),
            background_records=background_records,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SHAP computation failed: {exc}")

    feature_importance = compute_global_feature_importance(
        explanation["shap_values"], explanation["feature_names"]
    )

    regime_segmented_importance = compute_regime_segmented_feature_importance(
        explanation["shap_values"], explanation["feature_names"], sample_regimes
    )

    trade_statistics = compute_trade_statistics(backtest_result["trades"])

    position_to_shap_index = {pos: i for i, pos in enumerate(sample_positions)}

    def _trade_shap_row_index(trade) -> int:
        matches = ohlcv.index[ohlcv["timestamp"] == trade.entry_timestamp]
        if len(matches) == 0:
            return -1
        position = int(matches[0])
        return position_to_shap_index.get(position, -1)

    report_data = assemble_report_data(
        model_name=registered_model["name"],
        ohlcv=ohlcv,
        trades=backtest_result["trades"],
        feature_importance=feature_importance,
        regime_result=regime_result,
    )

    report_text = generate_full_report(report_data)

    backtest_metrics = {
        "trade_count": backtest_result["trade_count"],
        "total_pnl": backtest_result["total_pnl"],
        "final_cash": backtest_result["final_cash"],
        "ignored_bar_count": backtest_result["ignored_bar_count"],
        "equity_curve": equity_curve,
        "max_drawdown": max_drawdown,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "win_rate": trade_statistics["win_rate"],
        "sharpe_ratio": trade_statistics["sharpe_ratio"],
        "trades": [
            {
                "entry_timestamp": str(t.entry_timestamp),
                "exit_timestamp": str(t.exit_timestamp) if t.exit_timestamp else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "direction": t.direction,
                "pnl": t.pnl,
                "feature_vector": t.feature_vector,
                "shap_row_index": _trade_shap_row_index(t),
            }
            for t in backtest_result["trades"]
        ],
    }

    shap_summary = {
        "explainer_type": explanation["explainer_type"],
        "feature_names": explanation["feature_names"],
        "shap_values": explanation["shap_values"],
        "base_value": explanation["base_value"],
        "additivity_error": explanation["additivity_error"],
        "feature_importance": feature_importance,
        "regime_segmented_importance": regime_segmented_importance,
    }

    ohlcv_records = ohlcv.assign(timestamp=ohlcv["timestamp"].astype(str)).to_dict(orient="records")

    insert_payload = AnalysisResultInsert(
        model_id=request.model_id,
        user_id=user_id,
        ticker=request.ticker,
        date_range={"start": request.start, "end": request.end},
        backtest_metrics=backtest_metrics,
        shap_summary=shap_summary,
        regime_labels=regime_result,
        report_text=report_text,
        status="completed",
    )

    insert_dict = insert_payload.model_dump(mode="json")
    insert_dict["ohlcv_data"] = ohlcv_records
    insert_dict["predictions"] = sandbox_result["predictions"]

    client = get_supabase_client()
    response = client.table("analysis_results").insert(insert_dict).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to persist analysis result.")

    row = response.data[0]

    return {
        "analysis_id": row["id"],
        "model_name": registered_model["name"],
        "ohlcv": ohlcv_records,
        "predictions": sandbox_result["predictions"],
        "backtest": backtest_metrics,
        "regime": regime_result,
        "shap": shap_summary,
        "report_data": report_data,
        "report_text": report_text,
    }


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, user_id: str = Depends(get_current_user_id)):
    row = _get_analysis_result(analysis_id, user_id)

    try:
        registered_model = _get_registered_model(row["model_id"], user_id)
        model_name = registered_model["name"]
    except HTTPException:
        model_name = None

    return {
        "analysis_id": row["id"],
        "model_id": row["model_id"],
        "model_name": model_name,
        "ticker": row["ticker"],
        "date_range": row["date_range"],
        "ohlcv": row.get("ohlcv_data"),
        "predictions": row.get("predictions"),
        "backtest": row["backtest_metrics"],
        "shap": row["shap_summary"],
        "regime": row["regime_labels"],
        "report_text": row["report_text"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@router.post("/explain-section")
def explain_section(request: SectionExplanationRequest, user_id: str = Depends(get_current_user_id)):
    row = _get_analysis_result(request.analysis_id, user_id)

    if request.trade_index is not None:
        trades = row["backtest_metrics"]["trades"] if row["backtest_metrics"] else []
        if request.trade_index < 0 or request.trade_index >= len(trades):
            raise HTTPException(status_code=404, detail=f"Trade index {request.trade_index} not found.")

        trade = trades[request.trade_index]
        shap_row_index = trade.get("shap_row_index", -1)

        if shap_row_index is None or shap_row_index < 0 or not row["shap_summary"]:
            raise HTTPException(
                status_code=404,
                detail="No SHAP data available for this trade.",
            )

        shap_summary = row["shap_summary"]
        shap_values_for_trade = shap_summary["shap_values"][shap_row_index]

        section_data = {
            "trade": {
                "entry_timestamp": trade["entry_timestamp"],
                "exit_timestamp": trade["exit_timestamp"],
                "entry_price": trade["entry_price"],
                "exit_price": trade["exit_price"],
                "direction": trade["direction"],
                "pnl": trade["pnl"],
            },
            "feature_names": shap_summary["feature_names"],
            "shap_values_for_trade": shap_values_for_trade,
            "base_value": shap_summary["base_value"],
        }

        section_name = f"Trade at {trade['entry_timestamp']}"

        try:
            explanation_text = generate_section_explanation(section_name, section_data)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Trade explanation failed: {exc}")

        return {"section_name": section_name, "explanation": explanation_text}

    section_data = {
        "backtest_statistics": row["backtest_metrics"],
        "feature_importance": row["shap_summary"]["feature_importance"] if row["shap_summary"] else None,
        "regime_behavior": row["regime_labels"],
    }

    try:
        explanation_text = generate_section_explanation(request.section_name, section_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Section explanation failed: {exc}")

    return {"section_name": request.section_name, "explanation": explanation_text}