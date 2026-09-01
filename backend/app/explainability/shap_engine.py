import numpy as np
from app.sandbox.runner import run_explain_in_sandbox

ADDITIVITY_EPSILON = 0.01


class AdditivityCheckFailed(Exception):
    pass


def compute_shap_explanation(
    model_storage_path: str,
    records: list[dict],
    background_records: list[dict] = None,
) -> dict:
    result = run_explain_in_sandbox(
        model_storage_path=model_storage_path,
        records=records,
        background_records=background_records,
    )

    if result["additivity_error"] > ADDITIVITY_EPSILON:
        raise AdditivityCheckFailed(
            f"SHAP additivity check failed: error={result['additivity_error']} "
            f"exceeds epsilon={ADDITIVITY_EPSILON}"
        )

    return result


def compute_global_feature_importance(shap_values: list, feature_names: list[str]) -> dict:
    values_array = np.abs(np.asarray(shap_values))
    mean_abs_shap = values_array.mean(axis=0)

    return {
        name: float(score)
        for name, score in zip(feature_names, mean_abs_shap)
    }


def compute_regime_segmented_feature_importance(
    shap_values: list,
    feature_names: list[str],
    sample_regimes: list,
) -> dict:
    values_array = np.abs(np.asarray(shap_values))
    regime_groups = {}

    for row_index, regime in enumerate(sample_regimes):
        if regime is None:
            continue
        regime_groups.setdefault(regime, []).append(values_array[row_index])

    result = {}
    for regime, rows in regime_groups.items():
        rows_array = np.asarray(rows)
        mean_abs_shap = rows_array.mean(axis=0)
        result[regime] = {
            name: float(score)
            for name, score in zip(feature_names, mean_abs_shap)
        }

    return result