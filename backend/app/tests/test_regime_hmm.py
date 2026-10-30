import json
import math
import numpy as np
import pandas as pd
import pytest
from hmmlearn.hmm import GaussianHMM
from app.regime.hmm_detector import (
    MIN_BARS,
    REGIME_NAMES,
    compute_features,
    detect_regimes,
    fit_regime_model,
    filtered_probabilities,
    forward_filter,
    standardize,
)

TRUNCATION_BAR = 300
SERIES_LENGTH = 520
HAND_START = [0.6, 0.4]
HAND_TRANSITION = [[0.7, 0.3], [0.4, 0.6]]
HAND_MEANS = [0.0, 3.0]
HAND_OBSERVATIONS = [0.0, 3.0, 1.0]


def close_from_segments(segments: list[tuple[int, float]], seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = np.concatenate([rng.normal(0.0, sigma, length) for length, sigma in segments])
    return pd.Series(100.0 * np.cumprod(1.0 + returns))


def regime_feature_values(close: pd.Series) -> np.ndarray:
    features = compute_features(close)
    return features.dropna().to_numpy()


def ohlcv_from_close(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"close": close})


def standard_normal_pdf(x: float, mean: float) -> float:
    return math.exp(-0.5 * (x - mean) ** 2) / math.sqrt(2 * math.pi)


def hand_filtered() -> list[list[float]]:
    rows = []
    previous = None
    for x in HAND_OBSERVATIONS:
        if previous is None:
            unnormalized = [HAND_START[s] * standard_normal_pdf(x, HAND_MEANS[s]) for s in range(2)]
        else:
            predicted = [sum(previous[i] * HAND_TRANSITION[i][s] for i in range(2)) for s in range(2)]
            unnormalized = [predicted[s] * standard_normal_pdf(x, HAND_MEANS[s]) for s in range(2)]
        total = sum(unnormalized)
        previous = [value / total for value in unnormalized]
        rows.append(previous)
    return rows


@pytest.fixture(scope="module")
def fitted_and_values():
    close = close_from_segments([(170, 0.004), (170, 0.02), (180, 0.009)], seed=11)
    values = regime_feature_values(close)
    return fit_regime_model(values), values


def test_forward_pass_matches_hand_computed_two_state_model():
    model = GaussianHMM(n_components=2, covariance_type="diag")
    model.n_features = 1
    model.startprob_ = np.array(HAND_START)
    model.transmat_ = np.array(HAND_TRANSITION)
    model.means_ = np.array([[m] for m in HAND_MEANS])
    model.covars_ = np.array([[1.0], [1.0]])

    result = forward_filter(model, np.array([[x] for x in HAND_OBSERVATIONS]))

    np.testing.assert_allclose(result, np.array(hand_filtered()), rtol=1e-12)


def test_hmmlearn_compiled_forward_pass_matches_an_independent_forward_pass():
    model = GaussianHMM(n_components=2, covariance_type="diag")
    model.n_features = 1
    model.startprob_ = np.array(HAND_START)
    model.transmat_ = np.array(HAND_TRANSITION)
    model.means_ = np.array([[m] for m in HAND_MEANS])
    model.covars_ = np.array([[1.0], [1.0]])
    hand_log_likelihood = 0.0
    previous = None
    for x in HAND_OBSERVATIONS:
        if previous is None:
            unnormalized = [HAND_START[s] * standard_normal_pdf(x, HAND_MEANS[s]) for s in range(2)]
        else:
            predicted = [sum(previous[i] * HAND_TRANSITION[i][s] for i in range(2)) for s in range(2)]
            unnormalized = [predicted[s] * standard_normal_pdf(x, HAND_MEANS[s]) for s in range(2)]
        hand_log_likelihood += math.log(sum(unnormalized))
        previous = [value / sum(unnormalized) for value in unnormalized]

    assert model.score(np.array([[x] for x in HAND_OBSERVATIONS])) == pytest.approx(hand_log_likelihood, rel=1e-10)


def test_filtered_labels_do_not_change_when_the_series_is_truncated(fitted_and_values):
    fitted, values = fitted_and_values
    full = filtered_probabilities(fitted, values)
    truncated = filtered_probabilities(fitted, values[:TRUNCATION_BAR])
    np.testing.assert_allclose(full[:TRUNCATION_BAR], truncated, atol=1e-9, rtol=0)
    assert (full[:TRUNCATION_BAR].argmax(axis=1) == truncated.argmax(axis=1)).all()


def test_filtered_labels_do_not_change_when_the_future_changes(fitted_and_values):
    fitted, values = fitted_and_values
    altered = values.copy()
    altered[TRUNCATION_BAR:, 0] = altered[TRUNCATION_BAR:, 0] * -3.0
    altered[TRUNCATION_BAR:, 1] = altered[TRUNCATION_BAR:, 1] * 4.0
    original = filtered_probabilities(fitted, values)
    changed = filtered_probabilities(fitted, altered)
    np.testing.assert_allclose(original[:TRUNCATION_BAR], changed[:TRUNCATION_BAR], atol=1e-9, rtol=0)
    assert not np.allclose(original[TRUNCATION_BAR:], changed[TRUNCATION_BAR:])


def test_the_same_check_detects_a_smoothed_implementation(fitted_and_values):
    fitted, values = fitted_and_values
    altered = values.copy()
    altered[TRUNCATION_BAR:, 0] = altered[TRUNCATION_BAR:, 0] * -3.0
    altered[TRUNCATION_BAR:, 1] = altered[TRUNCATION_BAR:, 1] * 4.0
    smoothed_original = fitted.hmm.predict_proba(standardize(values, fitted.feature_means, fitted.feature_stds))
    smoothed_changed = fitted.hmm.predict_proba(standardize(altered, fitted.feature_means, fitted.feature_stds))
    smoothed_truncated = fitted.hmm.predict_proba(
        standardize(values[:TRUNCATION_BAR], fitted.feature_means, fitted.feature_stds)
    )
    assert np.abs(smoothed_original[:TRUNCATION_BAR] - smoothed_changed[:TRUNCATION_BAR]).max() > 1e-6
    assert np.abs(smoothed_original[:TRUNCATION_BAR] - smoothed_truncated).max() > 1e-6


def test_states_are_ordered_by_volatility():
    segment = 250
    close = close_from_segments([(segment, 0.005), (segment, 0.02), (segment, 0.01)], seed=3)
    result = detect_regimes(ohlcv_from_close(close))
    labels = result["regime_per_bar"]

    def majority(start, end):
        window = [label for label in labels[start:end] if label is not None]
        return max(set(window), key=window.count)

    assert majority(40, segment) == "Low vol"
    assert majority(segment + 40, 2 * segment) == "High vol"
    assert majority(2 * segment + 40, 3 * segment) == "Mid vol"
    assert result["state_names"] == REGIME_NAMES

    fitted = fit_regime_model(regime_feature_values(close))
    ordered_variances = [fitted.hmm.covars_[state][0, 0] for state in fitted.volatility_order]
    assert ordered_variances == sorted(ordered_variances)


def test_output_shape_counts_and_finiteness():
    close = close_from_segments([(170, 0.004), (170, 0.02), (180, 0.009)], seed=11)
    result = detect_regimes(ohlcv_from_close(close))
    assert result["regimes_available"] is True
    assert len(result["regime_per_bar"]) == SERIES_LENGTH
    assert result["regime_per_bar"][:20] == [None] * 20
    assert sum(result["n_bars"].values()) == result["n_valid_bars"] == SERIES_LENGTH - 20
    assert sum(result["time_in_regime_pct"].values()) == pytest.approx(1.0)
    for probabilities, confidence in zip(result["probabilities_per_bar"][20:], result["confidence_per_bar"][20:]):
        assert len(probabilities) == 3
        assert sum(probabilities) == pytest.approx(1.0, abs=1e-3)
        assert confidence == max(probabilities)
    json.dumps(result, allow_nan=False)


def test_short_history_returns_unavailable_instead_of_failing():
    close = close_from_segments([(MIN_BARS, 0.01)], seed=5)
    result = detect_regimes(ohlcv_from_close(close))
    assert result["regimes_available"] is False
    assert "250" in result["reason"]
    assert result["regime_per_bar"] == [None] * MIN_BARS
    json.dumps(result, allow_nan=False)
