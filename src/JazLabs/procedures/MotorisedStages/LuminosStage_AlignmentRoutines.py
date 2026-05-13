import time
from typing import List

import cma
import numpy as np
from scipy.optimize import minimize

from JazLabs.hardware.MotorisedStages.Luminos.LuminosStage import Axes, LuminosStage
from JazLabs.utils import AlignmentFunctions as AlignFunc
from JazLabs.utils.camera_utils import get_relative_power


class AlignmentObj:
    def __init__(self, stage_objs: List[LuminosStage], pwr_objs: list | None = None, cam_objs: list | None = None):
        self.stage_objs = stage_objs
        self.pwr_objs = [] if pwr_objs is None else pwr_objs
        self.cam_objs = [] if cam_objs is None else cam_objs

        if not self.stage_objs:
            raise ValueError("stage_objs cannot be empty.")

        if not self.pwr_objs and not self.cam_objs:
            raise ValueError("Provide at least one measurement device list: pwr_objs or cam_objs.")

        self.axis_name_to_enum = {
            "AlignX": Axes.X,
            "AlignY": Axes.Y,
            "AlignZ": Axes.Z,
            "AlignYAW": Axes.YAW,
            "AlignPITCH": Axes.PITCH,
            "AlignROLL": Axes.ROLL,
        }
        self.step_name_for_axis = {
            "AlignX": "d_X",
            "AlignY": "d_Y",
            "AlignZ": "d_Z",
            "AlignYAW": "d_YAW",
            "AlignPITCH": "d_PITCH",
            "AlignROLL": "d_ROLL",
        }

    def multi_dim_alignment_of_stage(
        self,
        stage_align_obj_idx: List[int],
        properties_to_align: List[dict],
        initial_step_sizes: List[dict] | None = None,
        optimiser: str = "CMA-ES",
        max_attempts: int = 100,
        f_tol: float = 1e-7,
        x_tol: float = 1.0,
        sigma0: float = 0.2,
        population_size: int | None = None,
        pwr_meter_obj_idx: int | None = None,
        cam_obj_idx: int | None = None,
        ix_cam_center: int | None = None,
        iy_cam_center: int | None = None,
        x_half_width: int | None = None,
        y_half_width: int | None = None,
        metric_log10: bool = True,
    ):
        if not isinstance(stage_align_obj_idx, list) or not stage_align_obj_idx:
            raise TypeError("stage_align_obj_idx must be a non-empty list.")
        if not isinstance(properties_to_align, list):
            raise TypeError("properties_to_align must be a list.")

        if initial_step_sizes is None:
            initial_step_sizes = [{"d_X": 5, "d_Y": 5, "d_Z": 5, "d_YAW": 5, "d_PITCH": 5, "d_ROLL": 5} for _ in range(len(self.stage_objs))]
        if not isinstance(initial_step_sizes, list):
            raise TypeError("initial_step_sizes must be a list.")

        use_power_meter = pwr_meter_obj_idx is not None
        use_camera = cam_obj_idx is not None
        if use_power_meter == use_camera:
            raise ValueError("Choose exactly one metric source: pwr_meter_obj_idx or cam_obj_idx.")

        if use_power_meter and (pwr_meter_obj_idx < 0 or pwr_meter_obj_idx >= len(self.pwr_objs)):
            raise IndexError("pwr_meter_obj_idx is out of range.")
        if use_camera and (cam_obj_idx < 0 or cam_obj_idx >= len(self.cam_objs)):
            raise IndexError("cam_obj_idx is out of range.")

        active_axes = []
        initial_physical = []
        step_array = []
        for stage_idx in stage_align_obj_idx:
            stage_props = properties_to_align[stage_idx]
            stage_steps = initial_step_sizes[stage_idx]
            current_positions = self.stage_objs[stage_idx].Get_all_stage_Positions()
            for key in ["AlignX", "AlignY", "AlignZ", "AlignYAW", "AlignPITCH", "AlignROLL"]:
                if stage_props.get(key, False):
                    axis_enum = self.axis_name_to_enum[key]
                    step_key = self.step_name_for_axis[key]
                    active_axes.append((stage_idx, axis_enum))
                    initial_physical.append(current_positions[axis_enum])
                    step_array.append(stage_steps[step_key])

        if not active_axes:
            raise ValueError("No active alignment axes selected in properties_to_align.")

        initial_physical = np.asarray(initial_physical, dtype=float)
        step_array = np.asarray(step_array, dtype=float)

        lower_bounds, upper_bounds = AlignFunc.MakeBoundsFromCentre(initial_physical, step_array)
        initial_norm = AlignFunc.physical_to_normalised(initial_physical, lower_bounds, upper_bounds)

        x_tol_norm = AlignFunc.physical_to_normalised(
            initial_physical + x_tol,
            lower_bounds,
            upper_bounds,
        ) - AlignFunc.physical_to_normalised(initial_physical, lower_bounds, upper_bounds)
        x_tol_norm = float(np.max(np.abs(x_tol_norm)))

        eval_counter = 0
        best_metric = np.inf
        best_physical_vertex = None

        if use_camera and hasattr(self.cam_objs[cam_obj_idx], "SetSoftwareTriggerMode"):
            self.cam_objs[cam_obj_idx].SetSoftwareTriggerMode()

        def objective(x_norm):
            nonlocal eval_counter, best_metric, best_physical_vertex
            eval_counter += 1

            if AlignFunc.CheckFileForStopAliginment():
                raise RuntimeError("Optimisation manually terminated.")

            physical_vertex = AlignFunc.normalised_to_physical(x_norm, lower_bounds, upper_bounds)

            for i, (stage_idx, axis_enum) in enumerate(active_axes):
                self.stage_objs[stage_idx].Set_Single_Stage_State_abs(axis_enum, physical_vertex[i])

            if use_power_meter:
                metric_value = float(self.pwr_objs[pwr_meter_obj_idx].GetPower())
            else:
                metric_value = float(
                    get_relative_power(
                        cam=self.cam_objs[cam_obj_idx],
                        centre=[iy_cam_center, ix_cam_center],
                        x_half_width=x_half_width,
                        y_half_width=y_half_width,
                        avg_count=1,
                    )
                )
                if metric_log10:
                    metric_value = np.log10(max(metric_value, np.finfo(float).tiny))

            objective_value = -metric_value
            if objective_value < best_metric:
                best_metric = objective_value
                best_physical_vertex = physical_vertex.copy()

            print(f"Func Evals: {eval_counter} Metric: {metric_value}")
            return objective_value

        result = None
        try:
            if optimiser == "CMA-ES":
                if population_size is None:
                    population_size = int(4 + (3 * np.log10(initial_norm.size)))
                lower_norm = np.array([-1.0] * len(initial_norm))
                upper_norm = np.array([1.0] * len(initial_norm))
                result = cma.fmin(
                    objective_function=objective,
                    x0=initial_norm,
                    sigma0=sigma0,
                    options={
                        "bounds": [lower_norm, upper_norm],
                        "popsize": population_size,
                        "maxiter": max_attempts,
                        "verb_disp": 1,
                    },
                )
            elif optimiser == "Nelder-Mead":
                initial_simplex = AlignFunc.MakeIntialSimplex(
                    initial_physical,
                    step_array,
                    lower_bounds,
                    upper_bounds,
                )
                result = minimize(
                    objective,
                    initial_norm,
                    method="Nelder-Mead",
                    options={
                        "disp": True,
                        "initial_simplex": initial_simplex,
                        "xatol": x_tol_norm,
                        "fatol": f_tol,
                        "maxiter": max_attempts,
                    },
                )
            else:
                result = minimize(
                    objective,
                    initial_norm,
                    method=optimiser,
                    bounds=[(-1, 1)] * initial_norm.size,
                    options={
                        "disp": True,
                        "xtol": x_tol_norm,
                        "ftol": f_tol,
                        "maxiter": max_attempts,
                    },
                )
        except RuntimeError as err:
            print(f"\nOptimisation stopped: {err}")
            print(f"Best-so-far: {best_metric} at x = {best_physical_vertex}")
        finally:
            if use_camera and hasattr(self.cam_objs[cam_obj_idx], "SetContinuousMode"):
                self.cam_objs[cam_obj_idx].SetContinuousMode()

        if best_physical_vertex is not None:
            print("Updating the stage to the best-found properties")
            for i, (stage_idx, axis_enum) in enumerate(active_axes):
                self.stage_objs[stage_idx].Set_Single_Stage_State_abs(axis_enum, best_physical_vertex[i])

        AlignFunc.ChangeFileForStopAliginment(0)

        if result is not None:
            print(f"Best objective: {best_metric}")

        return {
            "best_objective": best_metric,
            "best_physical_vertex": best_physical_vertex,
            "result": result,
            "eval_count": eval_counter,
        }
