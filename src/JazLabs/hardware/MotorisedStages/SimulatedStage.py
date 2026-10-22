"""Hardware-free stage driver with the same API as serial stage drivers."""
from copy import deepcopy
import math
import time


class SimulatedStage:
    def __init__(self, axes=2, absolute_sensor=False):
        if axes not in (1, 2, 3):
            raise ValueError("Simulation supports one, two or three axes")
        self.name = "Simulated mirror mount" if absolute_sensor else "Simulated translation stage"
        self.axes = []
        self.positions = {}
        self.targets = {}
        self.homed = {}
        self.homing = set()
        self.velocity = {}
        self.last_update = time.monotonic()
        names = ["U", "V"] if absolute_sensor else ["X", "Y", "Z"]
        if absolute_sensor and axes != 2:
            raise ValueError("The simulated mirror has two axes")
        for index, axis in enumerate(names[:axes]):
            lower, upper = (-0.75, 0.75) if absolute_sensor else (0.0, 25.0)
            self.axes.append({"id": axis, "label": {"U": "Yaw U", "V": "Pitch V"}.get(axis, axis),
                              "units": "deg" if absolute_sensor else "mm",
                              "minimum": lower, "maximum": upper,
                              "resolution": 0.001, "step": 0.005 if absolute_sensor else 0.01,
                              "home": not absolute_sensor, "stop": True, "speed": True,
                              "speed_minimum": 0.01, "speed_maximum": 2.0,
                              "speed_units": "deg/s" if absolute_sensor else "mm/s"})
            self.positions[axis] = 0.0 if absolute_sensor else 5.0 + index
            self.targets[axis] = self.positions[axis]
            self.homed[axis] = absolute_sensor or index == 0
            self.velocity[axis] = 0.2 if absolute_sensor else 1.0

    def GetAxisState(self, axis):
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now
        # Advance every axis using the same elapsed interval, regardless of which
        # readout is being requested. No GUI timer owns simulated motion.
        for name in self.positions:
            difference = self.targets[name] - self.positions[name]
            distance = min(abs(difference), elapsed * self.velocity[name])
            self.positions[name] += math.copysign(distance, difference)
            if abs(self.targets[name] - self.positions[name]) < 1e-9 and name in self.homing:
                self.homing.remove(name)
                self.homed[name] = True
        return {"position": self.positions[axis], "moving": abs(self.targets[axis] - self.positions[axis]) > 1e-9,
                "homed": self.homed[axis], "homing": axis in self.homing,
                "enabled": True, "fault": None, "speed": self.velocity[axis]}

    def MoveTo(self, axis, target):
        self.targets[axis] = target

    def HomeAxis(self, axis):
        self.homed[axis] = False
        self.homing.add(axis)
        self.targets[axis] = 0.0

    def StopAll(self):
        self.targets = dict(self.positions)
        self.homing.clear()

    def SetSpeed(self, axis, value):
        self.velocity[axis] = value

    def CloseStage(self):
        self.StopAll()

    def GetMotionCapabilities(self):
        return deepcopy(self.axes)

    def GetProperties(self):
        return {"stage_type": "simulation", "move_timeout": 60.0}

    def EnableAxis(self, axis):
        if axis not in self.positions:
            raise ValueError(f"Unknown axis {axis}")
