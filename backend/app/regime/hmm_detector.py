from dataclasses import dataclass
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

VOLATILITY_WINDOW = 20
N_REGIMES = 3
N_ITER = 500
RANDOM_STATE = 42
MIN_BARS = 250
REGIME_NAMES = ["Low vol", "Mid vol", "High vol"]
PROBABILITY_DECIMALS = 4
RETURN_FEATURE_INDEX = 0


class RegimeDetectionError(Exception):
    pass


@dataclass
class FittedRegimeModel:
    hmm: GaussianHMM
    feature_means: np.ndarray
    feature_stds: np.ndarray
    volatility_order: np.ndarray


def compute_features(close: pd.Series, volatility_window: int = VOLATILITY_WINDOW) -> pd.DataFrame:
    returns = close.astype(float).pct_change()
    return pd.DataFrame({
        "returns": returns,
        "volatility": returns.rolling(window=volatility_window).std(),
    })


def standardize(values: np.ndarray, means: np.ndarray, stds: np.ndarray) -> np.ndarray:
    return (values - means) / stds


def fit_regime_model(values: np.ndarray, n_regimes: int = N_REGIMES, random_state: int = RANDOM_STATE) -> FittedRegimeModel:
    means = values.mean(axis=0)
    stds = values.std(axis=0)
    stds[stds == 0] = 1.0
    hmm = GaussianHMM(n_components=n_regimes, covariance_type="diag", n_iter=N_ITER, random_state=random_state)
    hmm.fit(standardize(values, means, stds))
    return_variances = np.array([hmm.covars_[state][RETURN_FEATURE_INDEX, RETURN_FEATURE_INDEX] for state in range(n_regimes)])
    return FittedRegimeModel(hmm=hmm, feature_means=means, feature_stds=stds, volatility_order=np.argsort(return_variances))


def emission_log_likelihood(hmm: GaussianHMM, X: np.ndarray) -> np.ndarray:
    columns = [
        np.atleast_1d(multivariate_normal.logpdf(X, mean=hmm.means_[state], cov=hmm.covars_[state], allow_singular=True))
        for state in range(hmm.n_components)
    ]
    return np.column_stack(columns)


def forward_filter(hmm: GaussianHMM, X: np.ndarray) -> np.ndarray:
    log_emissions = emission_log_likelihood(hmm, X)
    with np.errstate(divide="ignore"):
        log_start = np.log(hmm.startprob_)
        log_transition = np.log(hmm.transmat_)
    log_filtered = np.empty_like(log_emissions)
    log_alpha = log_start + log_emissions[0]
    log_filtered[0] = log_alpha - logsumexp(log_alpha)
    for t in range(1, len(X)):
        log_alpha = logsumexp(log_filtered[t - 1][:, None] + log_transition, axis=0) + log_emissions[t]
        log_filtered[t] = log_alpha - logsumexp(log_alpha)
    return np.exp(log_filtered)


def filtered_probabilities(fitted: FittedRegimeModel, values: np.ndarray) -> np.ndarray:
    standardized = standardize(values, fitted.feature_means, fitted.feature_stds)
    return forward_filter(fitted.hmm, standardized)[:, fitted.volatility_order]


def unavailable(n_bars: int, reason: str) -> dict:
    return {
        "regimes_available": False,
        "reason": reason,
        "n_states": N_REGIMES,
        "state_names": REGIME_NAMES,
        "min_bars": MIN_BARS,
        "in_sample": True,
        "regime_per_bar": [None] * n_bars,
        "regime_index_per_bar": [None] * n_bars,
        "confidence_per_bar": [None] * n_bars,
        "probabilities_per_bar": [None] * n_bars,
        "n_bars": {name: 0 for name in REGIME_NAMES},
        "time_in_regime_pct": {name: None for name in REGIME_NAMES},
        "n_valid_bars": 0,
    }


def detect_regimes(ohlcv: pd.DataFrame) -> dict:
    close = ohlcv["close"].reset_index(drop=True)
    n_bars = len(close)
    features = compute_features(close)
    valid_mask = features.notna().all(axis=1).to_numpy() & np.isfinite(features.to_numpy()).all(axis=1)
    n_valid = int(valid_mask.sum())
    if n_valid < MIN_BARS:
        return unavailable(n_bars, f"At least {MIN_BARS} bars with defined regime features are needed; {n_valid} available.")

    values = features.to_numpy()[valid_mask]
    try:
        fitted = fit_regime_model(values)
        probabilities = filtered_probabilities(fitted, values)
    except Exception as exc:
        raise RegimeDetectionError(f"HMM fitting failed: {exc}")
    if not np.isfinite(probabilities).all():
        raise RegimeDetectionError("HMM filtering produced non-finite probabilities.")

    labels = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    regime_per_bar = [None] * n_bars
    regime_index_per_bar = [None] * n_bars
    confidence_per_bar = [None] * n_bars
    probabilities_per_bar = [None] * n_bars
    for offset, position in enumerate(np.flatnonzero(valid_mask)):
        regime_index_per_bar[position] = int(labels[offset])
        regime_per_bar[position] = REGIME_NAMES[int(labels[offset])]
        confidence_per_bar[position] = round(float(confidence[offset]), PROBABILITY_DECIMALS)
        probabilities_per_bar[position] = [round(float(p), PROBABILITY_DECIMALS) for p in probabilities[offset]]

    counts = {name: int((labels == index).sum()) for index, name in enumerate(REGIME_NAMES)}
    return {
        "regimes_available": True,
        "reason": None,
        "n_states": N_REGIMES,
        "state_names": REGIME_NAMES,
        "min_bars": MIN_BARS,
        "in_sample": True,
        "regime_per_bar": regime_per_bar,
        "regime_index_per_bar": regime_index_per_bar,
        "confidence_per_bar": confidence_per_bar,
        "probabilities_per_bar": probabilities_per_bar,
        "n_bars": counts,
        "time_in_regime_pct": {name: counts[name] / n_valid for name in REGIME_NAMES},
        "n_valid_bars": n_valid,
    }
