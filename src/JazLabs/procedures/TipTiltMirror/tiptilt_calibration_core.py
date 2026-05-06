#!/usr/bin/env python3
"""
2D piezo tip/tilt calibration module supporting affine and quadratic models.

Provides model classes, fitting, diagnostics, printing, plotting, and end-to-end
analysis. For a minimal usage script see analyse_calib_TT_data.py.

Models
------
Affine:
    [x, y] = A @ [V1, V2] + b

Quadratic:
    [x, y] = f(V1, V2)
    terms = [V1, V2, V1^2, V1*V2, V2^2, 1]

Notes on inverse mapping
------------------------
- Affine inverse is analytic.
- Quadratic inverse is numerical (local least-squares minimisation).
- Quadratic offset inversion depends on a reference operating point. This is explicit in
  the API via `reference_volts` / `reference_xy` arguments.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Tuple

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
# plt.ion()
import numpy as np

try:
    from scipy.optimize import least_squares
except Exception:  # pragma: no cover
    least_squares = None

ModelType = Literal["affine", "quadratic"]


# ============================================================
# Helpers
# ============================================================

def _as_points(arr: np.ndarray, name: str) -> Tuple[np.ndarray, bool]:
    """Return array as shape (N,2), plus flag whether original input was a single point."""
    a = np.asarray(arr, dtype=float)
    if a.ndim == 1:
        if a.shape[0] != 2:
            raise ValueError(f"{name} must have shape (2,) or (N,2), got {a.shape}")
        return a.reshape(1, 2), True
    if a.ndim == 2 and a.shape[1] == 2:
        return a, False
    raise ValueError(f"{name} must have shape (2,) or (N,2), got {a.shape}")


def _restore_shape(points: np.ndarray, was_single: bool) -> np.ndarray:
    return points[0] if was_single else points


# ============================================================
# Reusable calibration interface
# ============================================================

class BaseTipTiltCalibration(ABC):
    """Common interface for all calibration models."""

    model_type: ModelType

    @abstractmethod
    def volts_to_xy(self, volts: np.ndarray) -> np.ndarray:
        """Forward map voltages to pixel positions."""

    @abstractmethod
    def xy_to_volts(
        self,
        xy: np.ndarray,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """Inverse map pixel positions to voltages."""

    @abstractmethod
    def pixel_offsets_to_voltage_offsets(
        self,
        dxy: np.ndarray,
        reference_volts: np.ndarray | None = None,
        reference_xy: np.ndarray | None = None,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """Map image-plane offsets to voltage offsets."""

    @abstractmethod
    def voltage_offsets_to_pixel_offsets(
        self,
        dV: np.ndarray,
        reference_volts: np.ndarray | None = None,
    ) -> np.ndarray:
        """Map voltage offsets to image-plane offsets."""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-friendly dict."""

    def save_json(self, path: str | Path) -> None:
        """Save calibration to JSON file."""
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load_json(path: str | Path) -> BaseTipTiltCalibration:
        """Load calibration from JSON file."""
        return load_tiptilt_calibration(path)

    def offset_pixels_to_dac(
        self,
        dx: float,
        dy: float,
        reference_volts: np.ndarray | None = None,
        reference_xy: np.ndarray | None = None,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> Tuple[float, float]:
        """
        Convert pixel offset (dx, dy) to voltage offsets (dV1, dV2).

        For quadratic models, requires reference_volts or reference_xy.
        """
        dV = self.pixel_offsets_to_voltage_offsets(
            np.array([dx, dy], dtype=float),
            reference_volts=reference_volts,
            reference_xy=reference_xy,
            initial_guess=initial_guess,
            max_iter=max_iter,
            tol=tol,
        )
        return float(dV[0]), float(dV[1])

    def absolute_xy_to_dac(
        self,
        x: float,
        y: float,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> Tuple[float, float]:
        """Convert absolute pixel position (x, y) to voltages (V1, V2)."""
        V = self.xy_to_volts(
            np.array([x, y], dtype=float),
            initial_guess=initial_guess,
            max_iter=max_iter,
            tol=tol,
        )
        return float(V[0]), float(V[1])


# ============================================================
# Affine model
# ============================================================

@dataclass
class AffineTipTiltCalibration(BaseTipTiltCalibration):
    """
    Affine model:
        xy = volts @ A.T + b

    Inverse is analytic:
        volts = (xy - b) @ A^{-1}.T
    """

    A: np.ndarray
    b: np.ndarray
    model_type: ModelType = "affine"

    def __post_init__(self) -> None:
        self.A = np.asarray(self.A, dtype=float)
        self.b = np.asarray(self.b, dtype=float)
        if self.A.shape != (2, 2):
            raise ValueError(f"A must have shape (2,2), got {self.A.shape}")
        if self.b.shape != (2,):
            raise ValueError(f"b must have shape (2,), got {self.b.shape}")

    @property
    def Ainv(self) -> np.ndarray:
        """Inverse of transformation matrix A."""
        return np.linalg.inv(self.A)

    def volts_to_xy(self, volts: np.ndarray) -> np.ndarray:
        """Forward map voltages to pixel positions."""
        vv, was_single = _as_points(volts, "volts")
        out = vv @ self.A.T + self.b
        return _restore_shape(out, was_single)

    def xy_to_volts(
        self,
        xy: np.ndarray,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """Inverse map pixel positions to voltages (analytic)."""
        del initial_guess, max_iter, tol
        xx, was_single = _as_points(xy, "xy")
        out = (xx - self.b) @ self.Ainv.T
        return _restore_shape(out, was_single)

    def pixel_offsets_to_voltage_offsets(
        self,
        dxy: np.ndarray,
        reference_volts: np.ndarray | None = None,
        reference_xy: np.ndarray | None = None,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """Map pixel offsets to voltage offsets (reference-independent for affine)."""
        del reference_volts, reference_xy, initial_guess, max_iter, tol
        dd, was_single = _as_points(dxy, "dxy")
        out = dd @ self.Ainv.T
        return _restore_shape(out, was_single)

    def voltage_offsets_to_pixel_offsets(
        self,
        dV: np.ndarray,
        reference_volts: np.ndarray | None = None,
    ) -> np.ndarray:
        """Map voltage offsets to pixel offsets (reference-independent for affine)."""
        del reference_volts
        dd, was_single = _as_points(dV, "dV")
        out = dd @ self.A.T
        return _restore_shape(out, was_single)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-friendly dict."""
        return {
            "model_type": "affine",
            "A": self.A.tolist(),
            "b": self.b.tolist(),
            "Ainv": self.Ainv.tolist(),
            "equations": {
                "x": {
                    "V1_coeff": float(self.A[0, 0]),
                    "V2_coeff": float(self.A[0, 1]),
                    "offset": float(self.b[0]),
                },
                "y": {
                    "V1_coeff": float(self.A[1, 0]),
                    "V2_coeff": float(self.A[1, 1]),
                    "offset": float(self.b[1]),
                },
            },
            "offset_conversion": {
                "dV1_from_dx_dy": [float(self.Ainv[0, 0]), float(self.Ainv[0, 1])],
                "dV2_from_dx_dy": [float(self.Ainv[1, 0]), float(self.Ainv[1, 1])],
            },
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AffineTipTiltCalibration":
        """Deserialize from dict."""
        return cls(A=np.array(d["A"], dtype=float), b=np.array(d["b"], dtype=float))


# ============================================================
# Quadratic model
# ============================================================

@dataclass
class QuadraticTipTiltCalibration(BaseTipTiltCalibration):
    """
    Quadratic model:
        xy = design_matrix(volts) @ B

    terms in each design row:
        [V1, V2, V1^2, V1*V2, V2^2, 1]

    Inverse mapping is numerical and solved pointwise by minimising image-plane error.
    """

    B: np.ndarray  # shape (6,2)
    affine_seed: AffineTipTiltCalibration | None = None
    model_type: ModelType = "quadratic"

    def __post_init__(self) -> None:
        self.B = np.asarray(self.B, dtype=float)
        if self.B.shape != (6, 2):
            raise ValueError(f"B must have shape (6,2), got {self.B.shape}")

    @staticmethod
    def design_matrix(volts: np.ndarray) -> np.ndarray:
        """Compute design matrix for quadratic model."""
        vv, _ = _as_points(volts, "volts")
        v1 = vv[:, 0]
        v2 = vv[:, 1]
        return np.column_stack([
            v1,
            v2,
            v1 ** 2,
            v1 * v2,
            v2 ** 2,
            np.ones(len(vv)),
        ])

    def volts_to_xy(self, volts: np.ndarray) -> np.ndarray:
        """Forward map voltages to pixel positions."""
        vv, was_single = _as_points(volts, "volts")
        out = self.design_matrix(vv) @ self.B
        return _restore_shape(out, was_single)

    def _jacobian_xy_wrt_volts(self, v: np.ndarray) -> np.ndarray:
        """Compute Jacobian matrix d(xy)/d(volts) at point v."""
        v1, v2 = float(v[0]), float(v[1])
        j = np.zeros((2, 2), dtype=float)
        # x derivatives
        j[0, 0] = self.B[0, 0] + 2.0 * self.B[2, 0] * v1 + self.B[3, 0] * v2
        j[0, 1] = self.B[1, 0] + self.B[3, 0] * v1 + 2.0 * self.B[4, 0] * v2
        # y derivatives
        j[1, 0] = self.B[0, 1] + 2.0 * self.B[2, 1] * v1 + self.B[3, 1] * v2
        j[1, 1] = self.B[1, 1] + self.B[3, 1] * v1 + 2.0 * self.B[4, 1] * v2
        return j

    def _linearized_guess(self, xy_target: np.ndarray) -> np.ndarray:
        """Generate initial guess for inverse mapping using linearization."""
        if self.affine_seed is not None:
            return np.asarray(self.affine_seed.xy_to_volts(xy_target), dtype=float)

        A0 = self.B[:2, :].T
        b0 = self.B[5, :]
        try:
            A0_inv = np.linalg.inv(A0)
            return (xy_target - b0) @ A0_inv.T
        except np.linalg.LinAlgError:
            return np.zeros(2, dtype=float)

    def _solve_single_xy(
        self,
        xy_target: np.ndarray,
        initial_guess: np.ndarray | None,
        max_iter: int,
        tol: float,
    ) -> np.ndarray:
        """Solve inverse mapping for a single target point."""
        target = np.asarray(xy_target, dtype=float)
        x0 = np.asarray(initial_guess, dtype=float) if initial_guess is not None else self._linearized_guess(target)

        def residual(v: np.ndarray) -> np.ndarray:
            return self.volts_to_xy(v) - target

        if least_squares is not None:
            sol = least_squares(
                residual,
                x0,
                method="trf",
                max_nfev=max_iter,
                ftol=tol,
                xtol=tol,
                gtol=tol,
            )
            if sol.success:
                return sol.x

        # Fallback damped Gauss-Newton if SciPy is unavailable or fails.
        v = x0.copy()
        for _ in range(max_iter):
            r = residual(v)
            if np.linalg.norm(r) <= tol:
                return v

            J = self._jacobian_xy_wrt_volts(v)
            step, _, _, _ = np.linalg.lstsq(J, -r, rcond=None)

            alpha = 1.0
            norm_r = np.linalg.norm(r)
            accepted = False
            for _ in range(10):
                cand = v + alpha * step
                if np.linalg.norm(residual(cand)) < norm_r:
                    v = cand
                    accepted = True
                    break
                alpha *= 0.5

            if not accepted:
                v = v + step

            if np.linalg.norm(step) <= tol:
                return v

        return v

    def xy_to_volts(
        self,
        xy: np.ndarray,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """Inverse map pixel positions to voltages (numerical)."""
        xx, was_single = _as_points(xy, "xy")

        guesses = None
        if initial_guess is not None:
            gg, _ = _as_points(initial_guess, "initial_guess")
            if len(gg) == 1:
                guesses = np.repeat(gg, len(xx), axis=0)
            elif len(gg) == len(xx):
                guesses = gg
            else:
                raise ValueError("initial_guess must have shape (2,) or match xy shape (N,2)")

        out = np.zeros_like(xx)
        prev = None
        for i, target in enumerate(xx):
            guess = guesses[i] if guesses is not None else prev
            if guess is None:
                guess = self._linearized_guess(target)
            out[i] = self._solve_single_xy(target, guess, max_iter=max_iter, tol=tol)
            prev = out[i]

        return _restore_shape(out, was_single)

    def pixel_offsets_to_voltage_offsets(
        self,
        dxy: np.ndarray,
        reference_volts: np.ndarray | None = None,
        reference_xy: np.ndarray | None = None,
        initial_guess: np.ndarray | None = None,
        max_iter: int = 100,
        tol: float = 1e-10,
    ) -> np.ndarray:
        """
        Convert image-plane offsets to voltage offsets around a reference operating point.

        For quadratic models this operation is reference-dependent:
          1) establish reference absolute point (reference_volts or reference_xy)
          2) target_xy = reference_xy + dxy
          3) numerically invert target_xy -> target_volts
          4) return target_volts - reference_volts
        """
        dd, was_single = _as_points(dxy, "dxy")

        if reference_volts is None and reference_xy is None:
            raise ValueError(
                "Quadratic offset inversion requires a reference operating point. "
                "Provide reference_volts or reference_xy explicitly."
            )

        if reference_volts is not None:
            ref_v = np.asarray(reference_volts, dtype=float)
            if ref_v.shape != (2,):
                raise ValueError(f"reference_volts must have shape (2,), got {ref_v.shape}")
        else:
            ref_v = np.asarray(
                self.xy_to_volts(reference_xy, initial_guess=initial_guess, max_iter=max_iter, tol=tol),
                dtype=float,
            )

        if reference_xy is not None:
            ref_xy = np.asarray(reference_xy, dtype=float)
            if ref_xy.shape != (2,):
                raise ValueError(f"reference_xy must have shape (2,), got {ref_xy.shape}")
        else:
            ref_xy = np.asarray(self.volts_to_xy(ref_v), dtype=float)

        targets_xy = ref_xy.reshape(1, 2) + dd
        target_volts = self.xy_to_volts(
            targets_xy,
            initial_guess=ref_v if initial_guess is None else initial_guess,
            max_iter=max_iter,
            tol=tol,
        )

        target_volts_2d, _ = _as_points(target_volts, "target_volts")
        out = target_volts_2d - ref_v.reshape(1, 2)
        return _restore_shape(out, was_single)

    def voltage_offsets_to_pixel_offsets(
        self,
        dV: np.ndarray,
        reference_volts: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Convert voltage offsets to pixel offsets around a reference operating point.

        For quadratic models this depends on `reference_volts` because mapping is nonlinear.
        """
        dd, was_single = _as_points(dV, "dV")
        if reference_volts is None:
            raise ValueError(
                "Quadratic voltage->pixel offset conversion requires reference_volts explicitly."
            )
        ref_v = np.asarray(reference_volts, dtype=float)
        if ref_v.shape != (2,):
            raise ValueError(f"reference_volts must have shape (2,), got {ref_v.shape}")

        ref_xy = np.asarray(self.volts_to_xy(ref_v), dtype=float)
        tgt_xy = self.volts_to_xy(ref_v.reshape(1, 2) + dd)
        tgt_xy_2d, _ = _as_points(tgt_xy, "tgt_xy")
        out = tgt_xy_2d - ref_xy.reshape(1, 2)
        return _restore_shape(out, was_single)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-friendly dict."""
        d: Dict[str, Any] = {
            "model_type": "quadratic",
            "terms": ["V1", "V2", "V1^2", "V1*V2", "V2^2", "1"],
            "B": self.B.tolist(),
            "inverse_method": "numerical_least_squares",
        }
        if self.affine_seed is not None:
            d["affine_seed"] = {
                "A": self.affine_seed.A.tolist(),
                "b": self.affine_seed.b.tolist(),
            }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QuadraticTipTiltCalibration":
        """Deserialize from dict."""
        affine_seed = None
        if "affine_seed" in d:
            affine_seed = AffineTipTiltCalibration(
                A=np.array(d["affine_seed"]["A"], dtype=float),
                b=np.array(d["affine_seed"]["b"], dtype=float),
            )
        return cls(B=np.array(d["B"], dtype=float), affine_seed=affine_seed)


# ============================================================
# Persistence factory
# ============================================================

def load_tiptilt_calibration(path: str | Path) -> BaseTipTiltCalibration:
    """
    Load calibration from JSON file.

    Automatically detects model type and returns appropriate calibration object.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    model_type = d.get("model_type")

    # Backward compatibility: old affine JSON had no explicit model_type.
    if model_type is None:
        if "A" in d and "b" in d:
            return AffineTipTiltCalibration.from_dict(d)
        raise ValueError("Could not infer calibration model type from JSON")

    if model_type == "affine":
        return AffineTipTiltCalibration.from_dict(d)
    if model_type == "quadratic":
        return QuadraticTipTiltCalibration.from_dict(d)

    raise ValueError(f"Unsupported model_type in JSON: {model_type}")


# ============================================================
# Fitting and diagnostics
# ============================================================

def _validate_fit_inputs(volts: np.ndarray, xy: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Validate inputs for fitting functions."""
    vv = np.asarray(volts, dtype=float)
    xx = np.asarray(xy, dtype=float)
    if vv.ndim != 2 or vv.shape[1] != 2:
        raise ValueError(f"volts must have shape (N,2), got {vv.shape}")
    if xx.ndim != 2 or xx.shape[1] != 2:
        raise ValueError(f"xy must have shape (N,2), got {xx.shape}")
    if vv.shape[0] != xx.shape[0]:
        raise ValueError("volts and xy must have same number of rows")
    return vv, xx


def fit_affine_calibration(volts: np.ndarray, xy: np.ndarray) -> AffineTipTiltCalibration:
    """
    Fit affine calibration model to data.

    Parameters
    ----------
    volts : ndarray, shape (N, 2)
        Voltage values [V1, V2]
    xy : ndarray, shape (N, 2)
        Corresponding pixel positions [x, y]

    Returns
    -------
    AffineTipTiltCalibration
        Fitted calibration object
    """
    vv, xx = _validate_fit_inputs(volts, xy)
    X = np.column_stack([vv, np.ones(len(vv))])  # [V1, V2, 1]
    B, _, _, _ = np.linalg.lstsq(X, xx, rcond=None)  # shape (3,2)
    A = B[:2, :].T
    b = B[2, :]
    return AffineTipTiltCalibration(A=A, b=b)


def fit_quadratic_calibration(volts: np.ndarray, xy: np.ndarray) -> QuadraticTipTiltCalibration:
    """
    Fit quadratic calibration model to data.

    Parameters
    ----------
    volts : ndarray, shape (N, 2)
        Voltage values [V1, V2]
    xy : ndarray, shape (N, 2)
        Corresponding pixel positions [x, y]

    Returns
    -------
    QuadraticTipTiltCalibration
        Fitted calibration object with affine seed for inverse mapping
    """
    vv, xx = _validate_fit_inputs(volts, xy)
    X = QuadraticTipTiltCalibration.design_matrix(vv)
    B, _, _, _ = np.linalg.lstsq(X, xx, rcond=None)
    affine_seed = fit_affine_calibration(vv, xx)
    return QuadraticTipTiltCalibration(B=B, affine_seed=affine_seed)


def fit_calibration(
    volts: np.ndarray,
    xy: np.ndarray,
    model_type: ModelType = "affine",
) -> BaseTipTiltCalibration:
    """
    Fit calibration model to data.

    Parameters
    ----------
    volts : ndarray, shape (N, 2)
        Voltage values [V1, V2]
    xy : ndarray, shape (N, 2)
        Corresponding pixel positions [x, y]
    model_type : str
        Either "affine" or "quadratic"

    Returns
    -------
    BaseTipTiltCalibration
        Fitted calibration object
    """
    if model_type == "affine":
        return fit_affine_calibration(volts, xy)
    if model_type == "quadratic":
        return fit_quadratic_calibration(volts, xy)
    raise ValueError(f"Unknown model_type: {model_type}")


def residual_statistics(xy_true: np.ndarray, xy_pred: np.ndarray) -> Dict[str, Any]:
    """
    Compute residual statistics for model evaluation.

    Parameters
    ----------
    xy_true : ndarray, shape (N, 2)
        True pixel positions
    xy_pred : ndarray, shape (N, 2)
        Predicted pixel positions from model

    Returns
    -------
    dict
        Dictionary containing:
        - resid: residuals (N, 2)
        - rmag: residual magnitudes (N,)
        - rmse_xy: RMSE per axis [x, y]
        - rmse_total: total RMSE
        - mae_xy: mean absolute error per axis
        - mean_xy: mean residual per axis
        - std_xy: std of residuals per axis
        - r2_x, r2_y: R² values
        - median_mag, p68_mag, p95_mag, p99_mag, max_mag: percentiles
    """
    resid = xy_true - xy_pred
    rmag = np.linalg.norm(resid, axis=1)

    rmse_xy = np.sqrt(np.mean(resid ** 2, axis=0))
    rmse_total = np.sqrt(np.mean(np.sum(resid ** 2, axis=1)))
    mae_xy = np.mean(np.abs(resid), axis=0)
    mean_xy = np.mean(resid, axis=0)
    std_xy = np.std(resid, axis=0, ddof=1)

    ss_res_x = np.sum((xy_true[:, 0] - xy_pred[:, 0]) ** 2)
    ss_res_y = np.sum((xy_true[:, 1] - xy_pred[:, 1]) ** 2)
    ss_tot_x = np.sum((xy_true[:, 0] - np.mean(xy_true[:, 0])) ** 2)
    ss_tot_y = np.sum((xy_true[:, 1] - np.mean(xy_true[:, 1])) ** 2)

    r2_x = 1.0 - ss_res_x / ss_tot_x
    r2_y = 1.0 - ss_res_y / ss_tot_y

    p = np.percentile(rmag, [50, 68, 95, 99, 100])

    return {
        "resid": resid,
        "rmag": rmag,
        "rmse_xy": rmse_xy,
        "rmse_total": rmse_total,
        "mae_xy": mae_xy,
        "mean_xy": mean_xy,
        "std_xy": std_xy,
        "r2_x": r2_x,
        "r2_y": r2_y,
        "median_mag": p[0],
        "p68_mag": p[1],
        "p95_mag": p[2],
        "p99_mag": p[3],
        "max_mag": p[4],
    }


# ============================================================
# Print functions for model summaries
# ============================================================

def print_affine_model_summary(cal: AffineTipTiltCalibration) -> None:
    """Print summary of affine calibration model."""
    print("\n=== Affine calibration ===")
    print("Model:")
    print("    [x, y] = A @ [V1, V2] + b")
    print("\nA =")
    print(cal.A)
    print("\nb =")
    print(cal.b)
    print("\nEquations:")
    print(f"    x = {cal.A[0,0]: .6f} * V1 + {cal.A[0,1]: .6f} * V2 + {cal.b[0]: .6f}")
    print(f"    y = {cal.A[1,0]: .6f} * V1 + {cal.A[1,1]: .6f} * V2 + {cal.b[1]: .6f}")


def print_affine_inverse_summary(cal: AffineTipTiltCalibration) -> None:
    """Print summary of affine inverse mapping."""
    print("\n=== Affine inverse (analytic) ===")
    print("Absolute position to absolute voltages:")
    print("    [V1, V2] = A^{-1} @ ([x, y] - b)")
    print("\nA^{-1} =")
    print(cal.Ainv)
    print("\nFor pixel offsets:")
    print("    [dV1, dV2] = A^{-1} @ [dx, dy]")
    print(f"    dV1 = {cal.Ainv[0,0]: .6f} * dx + {cal.Ainv[0,1]: .6f} * dy")
    print(f"    dV2 = {cal.Ainv[1,0]: .6f} * dx + {cal.Ainv[1,1]: .6f} * dy")


def print_affine_geometric_interpretation(cal: AffineTipTiltCalibration) -> None:
    """Print geometric interpretation of affine model."""
    col_v1 = cal.A[:, 0]
    col_v2 = cal.A[:, 1]
    gain_v1 = np.linalg.norm(col_v1)
    gain_v2 = np.linalg.norm(col_v2)
    cosang = np.dot(col_v1, col_v2) / (gain_v1 * gain_v2)
    cosang = np.clip(cosang, -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(cosang))

    print("\n=== Geometric interpretation ===")
    print(
        f"Motion per +1 V on V1: dx={col_v1[0]:.6f} px, dy={col_v1[1]:.6f} px, "
        f"|motion|={gain_v1:.6f} px/V"
    )
    print(
        f"Motion per +1 V on V2: dx={col_v2[0]:.6f} px, dy={col_v2[1]:.6f} px, "
        f"|motion|={gain_v2:.6f} px/V"
    )
    print(f"Angle between actuation directions: {angle_deg:.4f} deg")


def print_quadratic_model_summary(cal: QuadraticTipTiltCalibration) -> None:
    """Print summary of quadratic calibration model."""
    print("\n=== Quadratic calibration ===")
    print("Model terms: [V1, V2, V1^2, V1*V2, V2^2, 1]")
    print("\nCoefficient matrix B =")
    print(cal.B)
    print("\nEquations:")
    print(
        f"    x = {cal.B[0,0]: .6f} * V1 + {cal.B[1,0]: .6f} * V2 "
        f"+ {cal.B[2,0]: .6f} * V1^2 + {cal.B[3,0]: .6f} * V1*V2 "
        f"+ {cal.B[4,0]: .6f} * V2^2 + {cal.B[5,0]: .6f}"
    )
    print(
        f"    y = {cal.B[0,1]: .6f} * V1 + {cal.B[1,1]: .6f} * V2 "
        f"+ {cal.B[2,1]: .6f} * V1^2 + {cal.B[3,1]: .6f} * V1*V2 "
        f"+ {cal.B[4,1]: .6f} * V2^2 + {cal.B[5,1]: .6f}"
    )


def print_quadratic_inverse_summary(cal: QuadraticTipTiltCalibration) -> None:
    """Print summary of quadratic inverse mapping."""
    print("\n=== Quadratic inverse (numerical) ===")
    print("xy_to_volts uses local least-squares minimisation in voltage space.")
    print("For best robustness, provide initial_guess and/or nearby reference point.")
    print("Offset inversion is reference-dependent and requires reference_volts or reference_xy.")


def print_model_summary(cal: BaseTipTiltCalibration) -> None:
    """Print model summary (dispatches to appropriate function)."""
    if isinstance(cal, AffineTipTiltCalibration):
        print_affine_model_summary(cal)
    elif isinstance(cal, QuadraticTipTiltCalibration):
        print_quadratic_model_summary(cal)


def print_inverse_summary(cal: BaseTipTiltCalibration) -> None:
    """Print inverse summary (dispatches to appropriate function)."""
    if isinstance(cal, AffineTipTiltCalibration):
        print_affine_inverse_summary(cal)
    elif isinstance(cal, QuadraticTipTiltCalibration):
        print_quadratic_inverse_summary(cal)


def print_residual_summary(stats: Dict[str, Any], label: str = "") -> None:
    """Print residual statistics."""
    prefix = f" ({label})" if label else ""
    print(f"\n=== Residual statistics{prefix} ===")
    print("Residual = measured_xy - fitted_xy")
    print(f"RMSE_x          : {stats['rmse_xy'][0]:.6f} px")
    print(f"RMSE_y          : {stats['rmse_xy'][1]:.6f} px")
    print(f"RMSE_total      : {stats['rmse_total']:.6f} px")
    print(f"MAE_x           : {stats['mae_xy'][0]:.6f} px")
    print(f"MAE_y           : {stats['mae_xy'][1]:.6f} px")
    print(f"Mean resid x    : {stats['mean_xy'][0]:.6f} px")
    print(f"Mean resid y    : {stats['mean_xy'][1]:.6f} px")
    print(f"Std resid x     : {stats['std_xy'][0]:.6f} px")
    print(f"Std resid y     : {stats['std_xy'][1]:.6f} px")
    print(f"R^2_x           : {stats['r2_x']:.8f}")
    print(f"R^2_y           : {stats['r2_y']:.8f}")
    print(f"|resid| median   : {stats['median_mag']:.6f} px")
    print(f"|resid| 68 pct   : {stats['p68_mag']:.6f} px")
    print(f"|resid| 95 pct   : {stats['p95_mag']:.6f} px")
    print(f"|resid| 99 pct   : {stats['p99_mag']:.6f} px")
    print(f"|resid| max      : {stats['max_mag']:.6f} px")


def print_model_comparison(
    base_label: str,
    base_stats: Dict[str, Any],
    comparison_label: str,
    comparison_stats: Dict[str, Any],
) -> None:
    """Print comparison between two models."""
    base_rmse = base_stats["rmse_total"]
    cmp_rmse = comparison_stats["rmse_total"]
    base_p95 = base_stats["p95_mag"]
    cmp_p95 = comparison_stats["p95_mag"]

    rmse_improvement_abs = base_rmse - cmp_rmse
    p95_improvement_abs = base_p95 - cmp_p95

    rmse_improvement_pct = 100.0 * rmse_improvement_abs / base_rmse if base_rmse != 0 else 0.0
    p95_improvement_pct = 100.0 * p95_improvement_abs / base_p95 if base_p95 != 0 else 0.0

    print("\n=== Model comparison ===")
    print(f"{base_label} RMSE_total       : {base_rmse:.6f} px")
    print(f"{comparison_label} RMSE_total : {cmp_rmse:.6f} px")
    print(f"Absolute RMSE change        : {rmse_improvement_abs:.6f} px")
    print(f"Percent RMSE change         : {rmse_improvement_pct:.3f} %")
    print(f"{base_label} |resid| 95 pct   : {base_p95:.6f} px")
    print(f"{comparison_label} |resid| 95 pct : {cmp_p95:.6f} px")
    print(f"Absolute 95 pct change      : {p95_improvement_abs:.6f} px")
    print(f"Percent 95 pct change       : {p95_improvement_pct:.3f} %")

    if rmse_improvement_abs > 0:
        print(f"{comparison_label} improves fit relative to {base_label}.")
    elif rmse_improvement_abs < 0:
        print(f"{comparison_label} is worse than {base_label} on this dataset.")
    else:
        print("Both models give identical RMSE on this dataset.")


# ============================================================
# Plotting
# ============================================================

def make_calibration_plot(
    volts: np.ndarray,
    xy: np.ndarray,
    model_cal: BaseTipTiltCalibration,
    model_stats: Dict[str, Any],
    output_plot: str | Path,
    comparison_cal: BaseTipTiltCalibration | None = None,
    residual_scale: float = 20.0,
    comparison_scale: float = 80.0,
) -> None:
    """
    Create calibration plot showing measured positions, model grid, and residuals.

    Parameters
    ----------
    volts : ndarray, shape (N, 2)
        Voltage values used in calibration
    xy : ndarray, shape (N, 2)
        Measured pixel positions
    model_cal : BaseTipTiltCalibration
        Primary calibration model
    model_stats : dict
        Residual statistics for primary model
    output_plot : str or Path
        Path to save plot
    comparison_cal : BaseTipTiltCalibration, optional
        Comparison model (e.g., quadratic vs affine)
    residual_scale : float
        Scale factor for residual arrows
    comparison_scale : float
        Scale factor for comparison arrows
    """
    pred = model_cal.volts_to_xy(volts)
    resid = model_stats["resid"]

    v1_vals = np.unique(volts[:, 0])
    v2_vals = np.unique(volts[:, 1])

    if comparison_cal is not None:
        cmp_pred = comparison_cal.volts_to_xy(volts)
        cmp_minus_model = cmp_pred - pred
    else:
        cmp_pred = None
        cmp_minus_model = None

    if comparison_cal is None:
        fig, ax = plt.subplots(figsize=(8, 8))
        axes = [ax]
    else:
        fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    ax = axes[0]
    ax.scatter(xy[:, 0], xy[:, 1], s=18, label="Measured positions")

    # Measured grid lines
    for v1 in v1_vals:
        m = np.isclose(volts[:, 0], v1)
        pts = xy[m]
        order = np.argsort(volts[m, 1])
        ax.plot(pts[order, 0], pts[order, 1], linewidth=1)

    for v2 in v2_vals:
        m = np.isclose(volts[:, 1], v2)
        pts = xy[m]
        order = np.argsort(volts[m, 0])
        ax.plot(pts[order, 0], pts[order, 1], linewidth=1)

    def map_model(v1_arr: np.ndarray, v2_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        vv = np.column_stack([np.ravel(v1_arr), np.ravel(v2_arr)])
        pp = model_cal.volts_to_xy(vv)
        pp2, _ = _as_points(pp, "pp")
        return pp2[:, 0].reshape(np.shape(v1_arr)), pp2[:, 1].reshape(np.shape(v2_arr))

    for v1 in v1_vals:
        xs, ys = map_model(np.full_like(v2_vals, v1), v2_vals)
        ax.plot(xs, ys, linestyle="--", linewidth=1.2, alpha=0.9)

    for v2 in v2_vals:
        xs, ys = map_model(v1_vals, np.full_like(v1_vals, v2))
        ax.plot(xs, ys, linestyle="--", linewidth=1.2, alpha=0.9)

    ax.quiver(
        pred[:, 0],
        pred[:, 1],
        resid[:, 0] * residual_scale,
        resid[:, 1] * residual_scale,
        angles="xy",
        scale_units="xy",
        scale=1,
        width=0.0025,
        label=f"Residuals ×{residual_scale:.0f}",
    )

    ax.set_xlabel("Camera x position [pixels]")
    ax.set_ylabel("Camera y position [pixels]")
    ax.set_title(f"Piezo tip/tilt calibration ({model_cal.model_type}): measured/model/residuals")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="best")

    txt = (
        f"Model: {model_cal.model_type}\n"
        f"RMSE: x={model_stats['rmse_xy'][0]:.4f} px, y={model_stats['rmse_xy'][1]:.4f} px\n"
        f"R²: x={model_stats['r2_x']:.6f}, y={model_stats['r2_y']:.6f}"
    )

    ax.text(
        0.02,
        0.98,
        txt,
        transform=ax.transAxes,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.9),
    )

    if comparison_cal is not None and cmp_minus_model is not None and cmp_pred is not None:
        ax2 = axes[1]
        ax2.scatter(pred[:, 0], pred[:, 1], s=18, label=f"{model_cal.model_type} predicted")

        for v1 in v1_vals:
            m = np.isclose(volts[:, 0], v1)
            pts = pred[m]
            order = np.argsort(volts[m, 1])
            ax2.plot(pts[order, 0], pts[order, 1], linewidth=1)

        for v2 in v2_vals:
            m = np.isclose(volts[:, 1], v2)
            pts = pred[m]
            order = np.argsort(volts[m, 0])
            ax2.plot(pts[order, 0], pts[order, 1], linewidth=1)

        ax2.quiver(
            pred[:, 0],
            pred[:, 1],
            cmp_minus_model[:, 0] * comparison_scale,
            cmp_minus_model[:, 1] * comparison_scale,
            angles="xy",
            scale_units="xy",
            scale=1,
            width=0.0025,
            label=f"{comparison_cal.model_type}-{model_cal.model_type} ×{comparison_scale:.0f}",
        )

        cmp_mag = np.linalg.norm(cmp_minus_model, axis=1)
        txt2 = (
            f"Correction field: {comparison_cal.model_type} - {model_cal.model_type}\n"
            f"median |Δ| = {np.median(cmp_mag):.5f} px\n"
            f"95th pct |Δ| = {np.percentile(cmp_mag, 95):.5f} px\n"
            f"max |Δ| = {np.max(cmp_mag):.5f} px"
        )

        ax2.text(
            0.02,
            0.98,
            txt2,
            transform=ax2.transAxes,
            va="top",
            ha="left",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.9),
        )

        ax2.set_xlabel("Camera x position [pixels]")
        ax2.set_ylabel("Camera y position [pixels]")
        ax2.set_title(f"{comparison_cal.model_type} correction relative to {model_cal.model_type}")
        ax2.set_aspect("equal", adjustable="box")
        ax2.legend(loc="best")

    fig.tight_layout()
    fig.savefig(output_plot, dpi=180, bbox_inches="tight")
    plt.show()
    print(f"\nSaved plot to: {output_plot}")


# ============================================================
# End-to-end analysis function
# ============================================================

def analyse_and_save_calibration(
    volts_file: str | Path,
    xy_file: str | Path,
    output_plot: str | Path = "piezo_tiptilt_calibration_plot.png",
    output_json: str | Path = "piezo_tiptilt_calibration.json",
    model_type: ModelType = "affine",
    compare_with_other_model: bool = True,
) -> BaseTipTiltCalibration:
    """
    Complete analysis pipeline: load data, fit models, print results, plot, save.

    Parameters
    ----------
    volts_file : str or Path
        Path to .npy file containing voltage data, shape (N, 2)
    xy_file : str or Path
        Path to .npy file containing pixel position data, shape (N, 2)
    output_plot : str or Path
        Path to save calibration plot
    output_json : str or Path
        Path to save calibration JSON
    model_type : str
        Primary model type: "affine" or "quadratic"
    compare_with_other_model : bool
        If True, also fit and compare the other model type

    Returns
    -------
    BaseTipTiltCalibration
        Fitted calibration object
    """
    volts_file = Path(volts_file)
    xy_file = Path(xy_file)

    volts = np.load(volts_file)
    xy = np.load(xy_file)

    print(f"Loaded volts file: {volts_file} shape={volts.shape}")
    print(f"Loaded xy file   : {xy_file} shape={xy.shape}")

    cal = fit_calibration(volts, xy, model_type=model_type)
    pred = cal.volts_to_xy(volts)
    stats = residual_statistics(xy, pred)

    comparison_cal = None
    comparison_stats = None
    if compare_with_other_model:
        other_type: ModelType = "quadratic" if model_type == "affine" else "affine"
        comparison_cal = fit_calibration(volts, xy, model_type=other_type)
        comparison_pred = comparison_cal.volts_to_xy(volts)
        comparison_stats = residual_statistics(xy, comparison_pred)

    print_model_summary(cal)
    print_inverse_summary(cal)
    if isinstance(cal, AffineTipTiltCalibration):
        print_affine_geometric_interpretation(cal)
    print_residual_summary(stats, label=cal.model_type)

    if comparison_cal is not None and comparison_stats is not None:
        print_model_summary(comparison_cal)
        print_inverse_summary(comparison_cal)
        print_residual_summary(comparison_stats, label=comparison_cal.model_type)
        print_model_comparison(
            base_label=cal.model_type,
            base_stats=stats,
            comparison_label=comparison_cal.model_type,
            comparison_stats=comparison_stats,
        )

    make_calibration_plot(
        volts,
        xy,
        model_cal=cal,
        model_stats=stats,
        output_plot=output_plot,
        comparison_cal=comparison_cal,
    )

    cal.save_json(output_json)
    print(f"Saved {model_type} calibration to {output_json}")
    return cal
