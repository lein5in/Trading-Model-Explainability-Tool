import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

DEFAULT_VOLATILITY_WINDOW = 20
N_REGIMES = 3
N_ITER = 500


class RegimeDetectionError(Exception):
    pass


def compute_features(ohlcv: pd.DataFrame, volatility_window: int = DEFAULT_VOLATILITY_WINDOW) -> pd.DataFrame:
    returns = ohlcv["close"].pct_change()
    rolling_volatility = returns.rolling(window=volatility_window).std()

    features = pd.DataFrame({
        "returns": returns,
        "volatility": rolling_volatility,
    })

    return features


def standardize(features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = features.values
    means = values.mean(axis=0)
    stds = values.std(axis=0)
    stds[stds == 0] = 1.0
    standardized_values = (values - means) / stds
    return standardized_values, means, stds


def fit_hmm(standardized_values: np.ndarray, n_regimes: int = N_REGIMES, random_state: int = 42) -> GaussianHMM:
    if len(standardized_values) < n_regimes * 10:
        raise RegimeDetectionError(
            f"Not enough valid data points ({len(standardized_values)}) to fit a {n_regimes}-state HMM."
        )

    model = GaussianHMM(
        n_components=n_regimes,
        covariance_type="diag",
        n_iter=N_ITER,
        random_state=random_state,
    )
    model.fit(standardized_values)

    return model


def label_regimes_by_mean_return(model: GaussianHMM) -> dict:
    mean_returns = model.means_[:, 0]
    ordered_states = np.argsort(mean_returns)

    labels = {}
    labels[int(ordered_states[0])] = "bearish"
    labels[int(ordered_states[-1])] = "bullish"
    for state in ordered_states[1:-1]:
        labels[int(state)] = "choppy"

    return labels


def detect_regimes(
    ohlcv: pd.DataFrame,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    n_regimes: int = N_REGIMES,
) -> dict:
    features = compute_features(ohlcv, volatility_window)
    valid_mask = features.notna().all(axis=1)
    clean_features = features[valid_mask]

    standardized_values, _, _ = standardize(clean_features)
    model = fit_hmm(standardized_values, n_regimes)

    filtered_proba = model.predict_proba(standardized_values)
    argmax_states = filtered_proba.argmax(axis=1)

    state_labels = label_regimes_by_mean_return(model)

    regime_sequence = [state_labels[int(state)] for state in argmax_states]
    confidence_sequence = [
        float(filtered_proba[i, argmax_states[i]])
        for i in range(len(argmax_states))
    ]

    full_length = len(ohlcv)
    padded_regime = [None] * full_length
    padded_confidence = [None] * full_length

    valid_indices = features.index[valid_mask]
    for offset, idx in enumerate(valid_indices):
        position = ohlcv.index.get_loc(idx)
        padded_regime[position] = regime_sequence[offset]
        padded_confidence[position] = confidence_sequence[offset]

    time_in_regime = pd.Series(regime_sequence).value_counts(normalize=True).to_dict()

    return {
        "regime_per_bar": padded_regime,
        "confidence_per_bar": padded_confidence,
        "time_in_regime_pct": {k: float(v) for k, v in time_in_regime.items()},
        "n_valid_bars": len(clean_features),
    }