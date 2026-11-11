"""Distributional model: LightGBM mean + LightGBM scale (E|residual|) + empirical standardized-residual CDF.

    Y = mu(x) + s(x) * Z,      Z ~ empirical distribution of out-of-fold standardized residuals

* mu(x): LightGBM (L2) on pre-game features.
* s(x):  LightGBM fit to |out-of-fold residual| (OOF via season-grouped K-fold inside the TRAINING window only).
* Z:     the OOF residuals divided by a CROSS-FITTED s(x) (scale model not trained on that fold) — keeps skew/fat tails (yardage is right-skewed). `dist: normal` uses a
         Gaussian instead (sigma = s * sqrt(pi/2)).
P(over L) = 1 - F_Z((L - mu)/s).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy.stats import norm
from sklearn.model_selection import GroupKFold

QLEVELS = np.linspace(0.01, 0.99, 99)


def _lgbm(params: dict, n_estimators=None, **over) -> lgb.LGBMRegressor:
    p = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=50, subsample=0.8,
             subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=8, random_state=0)
    p.update(params or {})
    if n_estimators:
        p["n_estimators"] = n_estimators
    p.update(over)
    return lgb.LGBMRegressor(**p)


class DistModel:
    def __init__(self, lgbm_params: dict | None = None, dist: str = "empirical", n_folds: int = 3):
        self.params = lgbm_params or {}
        self.dist = dist
        self.n_folds = n_folds

    # -- scale / residual distribution (expensive: OOF) -----------------------------------------------------------
    def fit_dist(self, X: pd.DataFrame, y: np.ndarray, groups: np.ndarray):
        oof = np.full(len(y), np.nan)
        k = min(self.n_folds, len(np.unique(groups)))
        for tr, va in GroupKFold(n_splits=k).split(X, y, groups):
            m = _lgbm(self.params).fit(X.iloc[tr], y[tr])
            oof[va] = m.predict(X.iloc[va])
        res = y - oof
        # scale model cross-fitted too (Tester1 B9): z for each fold uses a scale model that never saw that fold,
        # so the standardized residual distribution is fully out-of-sample. Final scale model uses all rows.
        s_oof = np.full(len(y), np.nan)
        for tr, va in GroupKFold(n_splits=k).split(X, y, groups):
            sm = self._scale_fit(X.iloc[tr], np.abs(res[tr]))
            s_oof[va] = np.clip(sm.predict(X.iloc[va]), 3.0, None)
        self.scale_model = self._scale_fit(X, np.abs(res))
        z = res / s_oof
        self.z_sorted = np.sort(np.clip(z, -8, 8))
        return self

    def _scale_fit(self, X, absres):
        return _lgbm(self.params, n_estimators=200, num_leaves=7, min_child_samples=200).fit(X, absres)

    def _scale(self, X):
        return np.clip(self.scale_model.predict(X), 3.0, None)

    # -- mean (cheap; can be refit more often) ---------------------------------------------------------------------
    def fit_mean(self, X: pd.DataFrame, y: np.ndarray):
        self.mean_model = _lgbm(self.params).fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return self.mean_model.predict(X), self._scale(X)

    def prob_over(self, mu, s, line):
        z = (np.asarray(line) - mu) / s
        if self.dist == "normal":
            return 1 - norm.cdf(z, scale=np.sqrt(np.pi / 2))
        # empirical CDF with linear interpolation
        n = len(self.z_sorted)
        F = np.interp(z, self.z_sorted, (np.arange(1, n + 1) - 0.5) / n, left=0.0, right=1.0)
        return 1 - F

    def quantiles(self, mu, s, q=QLEVELS):
        if self.dist == "normal":
            zq = norm.ppf(q, scale=np.sqrt(np.pi / 2))
        else:
            zq = np.quantile(self.z_sorted, q)
        return mu[:, None] + s[:, None] * zq[None, :]


def crps_from_quantiles(qpred: np.ndarray, y: np.ndarray, q=QLEVELS) -> np.ndarray:
    """CRPS ~= 2 * mean pinball loss over quantile levels (per row)."""
    d = y[:, None] - qpred
    pin = np.maximum(q[None, :] * d, (q[None, :] - 1) * d)
    return 2 * pin.mean(axis=1)
