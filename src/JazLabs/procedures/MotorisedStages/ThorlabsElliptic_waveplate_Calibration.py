import matplotlib.pyplot as plt
import numpy as np

from JazLabs.hardware.MotorisedStages.Thorlabs.Elliptec.ElliptecRotationMountObject import (
    ELL_RotationMountObj,
)
from JazLabs.utils import AlignmentFunctions as AlignFunc


class WaveplateAngleCalibration:
    def __init__(self, power_meter_obj, rot_stage_obj: ELL_RotationMountObj):
        self.power_meter_obj = power_meter_obj
        self.rot_stage_obj = rot_stage_obj

    def perform_waveplate_alignment(self, min_bracket: float = 0, max_bracket: float = 90):
        final_min_angle = None
        final_min_power = None

        for stage_idx in range(self.rot_stage_obj.stageCount):
            original_angle_offset = self.rot_stage_obj.AngleOffset[stage_idx]
            self.rot_stage_obj.AngleOffset[stage_idx] = 0

            self._active_stage_idx = stage_idx
            self.angles = np.empty(0)
            self.power_readings = np.empty(0)

            min_angle, min_power = AlignFunc.GoldenSectionSearchContinuous(
                min_bracket,
                max_bracket,
                self.rot_stage_obj.AngleResolution,
                self._set_waveplate_angle_and_read_power,
            )

            min_angle_rounded = min_angle
            self.rot_stage_obj.AngleOffset[stage_idx] = min_angle_rounded - 45

            print("Final results:", min_angle_rounded, min_angle, min_power)
            print("New AngleOffset:", self.rot_stage_obj.AngleOffset[stage_idx])
            print("Original AngleOffset:", original_angle_offset)
            print("Delta Offset:", min_angle_rounded - original_angle_offset)

            final_min_angle = min_angle
            final_min_power = min_power

        return final_min_angle, final_min_power

    def _set_waveplate_angle_and_read_power(self, angle_value):
        if angle_value < 0:
            angle_value = 0

        self.rot_stage_obj.HomeStages()
        actual_angle, _ = self.rot_stage_obj.SetAngle(angle_value, self._active_stage_idx)

        power = self.power_meter_obj.GetPower()

        self.angles = np.append(self.angles, actual_angle)
        self.power_readings = np.append(self.power_readings, power)

        return actual_angle, power

    def fine_sweep_about_offset(self, rota_count: int = 30, stage_idx: int = 0):
        self.rot_stage_obj.HomeStages()
        original_angle_offset = float(self.rot_stage_obj.AngleOffset[stage_idx])

        rota_min = (original_angle_offset + 45) - (rota_count // 2) * self.rot_stage_obj.AngleResolution
        rota_max = (original_angle_offset + 45) + (rota_count // 2) * self.rot_stage_obj.AngleResolution

        if rota_min < 0:
            rota_min = 0
        if rota_max >= 360:
            rota_max = 360 - self.rot_stage_obj.AngleResolution

        rot_angle_sweep = np.linspace(rota_min, rota_max, rota_count)
        power_reading = np.zeros(rota_count)
        rot_angle_actual = np.zeros(rota_count)

        self.rot_stage_obj.AngleOffset[stage_idx] = 0

        for irot in range(rota_count):
            self.rot_stage_obj.HomeStages()
            actual_angle, _ = self.rot_stage_obj.SetAngle(rot_angle_sweep[irot], stage_idx)
            power_reading[irot] = self.power_meter_obj.GetPower()
            rot_angle_actual[irot] = actual_angle

        min_idx_power = int(np.argmin(power_reading))
        min_angle_actual = rot_angle_actual[min_idx_power]

        print("Measured angle offset:", min_angle_actual)
        print("Original angle offset + 45:", original_angle_offset + 45)
        print("Delta:", min_angle_actual - (original_angle_offset + 45))

        plt.figure()
        plt.plot(rot_angle_actual, power_reading)

        self.rot_stage_obj.AngleOffset[stage_idx] = original_angle_offset

        return rot_angle_actual, power_reading

    def coarse_sweep_waveplates_power_meter(self, rota_count: int = 25):
        rota_min = 0
        rota_max = 360
        rot_angle_temp = np.linspace(rota_min, rota_max, rota_count + 1)
        rot_angle = np.delete(rot_angle_temp, -1)
        power_reading = np.zeros(rota_count)

        for irot in range(rota_count):
            power_reading[irot] = self.power_meter_obj.GetPower()
            actual_angle, _ = self.rot_stage_obj.SetAngle(rot_angle[irot])
            rot_angle[irot] = actual_angle

        return rot_angle, power_reading
