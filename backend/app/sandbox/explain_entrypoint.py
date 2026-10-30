import pandas as pd
from app.sandbox.explain_core import (
    DEFAULT_ADDITIVITY_EPSILON,
    DEFAULT_KERNEL_BACKGROUND_SIZE,
    DEFAULT_KERNEL_NSAMPLES,
    AdditivityError,
    explain,
)
from app.sandbox.sandbox_common import SandboxTaskError, run_entrypoint


def frame(records: list[list[float]], feature_names: list[str]) -> pd.DataFrame:
    return pd.DataFrame(records, columns=feature_names, dtype=float)


def handle_explain(model, payload: dict) -> dict:
    feature_names = payload["feature_names"]
    global_rows = frame(payload["global_rows"], feature_names)
    trade_rows = frame(payload.get("trade_rows", []), feature_names)
    background = frame(payload["background_rows"], feature_names)
    combined = pd.concat([global_rows, trade_rows], ignore_index=True)
    try:
        result = explain(
            model,
            combined,
            background,
            epsilon=float(payload.get("epsilon", DEFAULT_ADDITIVITY_EPSILON)),
            nsamples=int(payload.get("nsamples", DEFAULT_KERNEL_NSAMPLES)),
            kernel_background_size=int(payload.get("kernel_background_size", DEFAULT_KERNEL_BACKGROUND_SIZE)),
        )
    except AdditivityError as exc:
        raise SandboxTaskError(str(exc), code="shap_additivity_failed", details={"max_gap": exc.max_gap})

    split = len(global_rows)
    return {
        "explainer": result["explainer"],
        "explained_output": result["explained_output"],
        "explained_class": result["explained_class"],
        "base_value": result["base_value"],
        "max_additivity_gap": result["max_additivity_gap"],
        "global_values": result["values"][:split].tolist(),
        "global_outputs": result["outputs"][:split].tolist(),
        "trade_values": result["values"][split:].tolist(),
        "trade_outputs": result["outputs"][split:].tolist(),
    }


if __name__ == "__main__":
    run_entrypoint(handle_explain)
