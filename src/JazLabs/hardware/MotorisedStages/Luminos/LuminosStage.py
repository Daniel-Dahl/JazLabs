"""
A module that connects to Zaber motors on an Luminos alignment board and
aligns two fibres
"""

import enum
import numpy as np

# docs: https://software.zaber.com/motion-library/
import concurrent.futures
from zaber_motion.ascii import Connection as AsciiConnection
from zaber_motion import Tools, NoDeviceFoundException, SerialPortBusyException
from zaber_motion.binary import Connection, BinarySettings
from zaber_motion import Units

__all__ = ["LuminosStage", "Axes"]


class Axes(enum.IntEnum):
    """
    Defines the order in which the motors on the platform are connected
    """

    Z = 0
    X = 1
    Y = 2
    ROLL = 3
    YAW = 4
    PITCH = 5


class LuminosStage:
    """
    A chain of Zaber motors that are connected to the same port
    """
    def __init__(self, port: str | None = None, expected_devices: int = 6) -> None:
        """
        Connect to the motors on the specified port.  If no port is given, scan
        all serial ports and pick the first port with the expected number of
        Zaber devices.

        Parameters
        ----------
        port : str | None
            The port to connect to the motors on, e.g. "COM3".  If None,
            scan all ports and pick the first that has the expected number of devices.
        expected_devices : int
            The number of devices expected to be present on a valid port.
        """
        if port is None:
            print("unplug and replug the stage to work out what the comport is dummy")
            # candidates = LuminosStage.scan_available_ports(expected_devices)
            # if not candidates:
            #     raise RuntimeError(
            #         f"No serial ports found with {expected_devices} connected devices."
            #     )
            # port = next(iter(candidates.keys()))  # take the first port found

        # open the binary connection to the selected port
        self.connection = Connection.open_serial_port(port)
        self.devices = self.connection.detect_devices()
        # self.validate_connection()
        # self.read_positions()
        self.deviceCount=len(self.devices)
        self.deviceMinLimits=np.zeros(self.deviceCount)
        self.deviceMaxLimits=np.zeros(self.deviceCount)
        
        self.StoredStagePositions_arr=np.zeros((1,self.deviceCount))
        self.Get_all_stage_Positions(displayState=True)
        self.get_stage_limits()
    def __del__(self):
        self.connection.close()
        
    def StoreStagePositions(self,istore,appendToCurrentpositions=False):
        storedstateCount=self.StoredStagePositions_arr.shape[0]
        # for idevice in range(self.deviceCount):
        #     postionsToStore=self.devices[idevice].get_position()
        postionsToStore=self.Get_all_stage_Positions()
        
        if appendToCurrentpositions:
            self.StoredStagePositions_arr = np.vstack((self.StoredStagePositions_arr, postionsToStore))
        else:
            if istore>storedstateCount-1:
                self.StoredStagePositions_arr = np.vstack((self.StoredStagePositions_arr, postionsToStore))
                print("istore was greater then the current stored state array so has been append")
            else:
                self.StoredStagePositions_arr[istore,:]=postionsToStore
            
    def clearStoredStageStates(self):
        self.StoredStagePositions_arr=np.zeros((1,self.deviceCount))
    
   
    
    def get_stage_limits(self):
        for deviceIdx in range(self.deviceCount):
            device=self.devices[deviceIdx]
            self.deviceMaxLimits[deviceIdx]=device.settings.get(BinarySettings.MAXIMUM_POSITION)
            self.deviceMinLimits[deviceIdx]=device.settings.get(BinarySettings.MINIMUM_POSITION)
            print(f"    Position range: {self.deviceMinLimits[deviceIdx]} – {self.deviceMaxLimits[deviceIdx]} (native units)")
            

    

    def Set_Single_Stage_State_abs(
        self,
        motor_num: int,
        position: float,
        units=Units.NATIVE,
    ):
        """
        Move a motor to an absolute position

        Parameters
        ----------
        motor_num : int
            The motor_num to move
        position : float
            The position to move the motor to (in um)
        """
        # Clamp position within limits
        if position > self.deviceMaxLimits[motor_num]:
            position = self.deviceMaxLimits[motor_num]
        elif position < self.deviceMinLimits[motor_num]:
            position = self.deviceMinLimits[motor_num]

        # Now move to the (possibly clamped) position
        self.devices[motor_num].move_absolute(position, units)
                    

    def Set_Single_Stage_State_rel(
        self,
        motor_num: int,
        distance: float,
        units=Units.NATIVE,
    ):
        """
        Move a motor a relative distance

        Parameters
        ----------
        motor_num : int
            The motor_num to move
        distance : float
            The distance to move the motor (in um)
        """
        self.devices[motor_num].move_relative(distance, units)
    

    def home_all(self):
        """
        Return all motors to the home position. Required to read accurate
        positions.

        Returns
        -------
        None
        """
        for dev in self.devices:
            dev.home()
    def Set_all_stage_Position_Nominal(self):
        nominal_positions=self.deviceMaxLimits[:]//2
        self.Set_all_stage_Positions_abs(nominal_positions)

 
    def Set_all_stage_Positions_abs(
        self,
        posistions,
        units: Units = Units.NATIVE,
    ):
        if len(posistions)!=self.deviceCount:
            print("positions array not the correct lenght")
            return
        
        for idevice in range(self.deviceCount):
            self.devices[idevice].move_absolute(posistions[idevice],units)
            
    def Get_all_stage_Positions(
        self,
        units: Units = Units.NATIVE,
        displayState=False
    ):
        positions=np.zeros(self.deviceCount)
        for idevice in range(self.deviceCount):
            positions[idevice]=self.devices[idevice].get_position()
        if(displayState):
            print(positions)
        return positions

    # def middle_all(self, units=Units.NATIVE):
    #     """
    #     Set all motors to halfway between their max and min

    #     Parameters
    #     ----------
    #     units : Units
    #         The units to return the positions in

    #     Returns
    #     -------
    #     None
    #     """
    #     axes = [Axes.Z, Axes.X, Axes.Y, Axes.ROLL, Axes.YAW, Axes.PITCH]
    #     for axis in axes:
    #         min_pos = self.devices[axis.value].settings.get(
    #             BinarySettings.MINIMUM_POSITION,
    #             units,
    #         )
    #         max_pos = self.devices[axis.value].settings.get(
    #             BinarySettings.MAXIMUM_POSITION,
    #             units,
    #         )

    #         self.devices[axis.value].move_absolute(
    #             (max_pos - min_pos) / 2 + min_pos,
    #         )

    # def move_proportion(
    #     self,
    #     axes: Axes,
    #     proportions: list[float],
    # ):
    #     """
    #     Set all motors to a proportion of their range

    #     Parameters
    #     ----------
    #     axes : list
    #         A list of axes to move
    #     proportions : list[float]
    #         A list of proportions to move the axes to. Each proportion should
    #         be between 0 and 1.

    #     Returns
    #     -------
    #     None
    #     """
    #     assert len(proportions) == len(axes)
    #     # check all proportions are between 0 and 1
    #     for prop in proportions:
    #         assert 0 <= prop <= 1

    #     units = Units.NATIVE
    #     for axis, prop in zip(axes, proportions):
    #         min_pos = self.devices[axis.value].settings.get(
    #             BinarySettings.MINIMUM_POSITION, units
    #         )
    #         max_pos = self.devices[axis.value].settings.get(
    #             BinarySettings.MAXIMUM_POSITION, units
    #         )

    #         self.devices[axis.value].move_absolute(
    #             (max_pos - min_pos) * prop + min_pos,
    #         )

    # def reset_to_nominal(self):
    #     self.home_all()

    #     ax = [
    #         Axes.X,
    #         Axes.ROLL,
    #         Axes.YAW,
    #         Axes.PITCH,
    #     ]
    #     self.move_proportion(ax, [0.5] * len(ax))

    #     self.move_proportion([Axes.Y], [0.5])

    #     z_prop_final = 1.0
    #     self.move_proportion([Axes.Z], [z_prop_final])
 # @staticmethod
    # def scan_available_ports(expected_devices: int = 6) -> dict[str, str]:
    #     """
    #     Scan all COM ports and return a dictionary of ports with Zaber devices.

    #     Parameters
    #     ----------
    #     expected_devices : int
    #         If provided, only ports with exactly this many devices are returned.

    #     Returns
    #     -------
    #     dict[str, str]
    #         Mapping of COM port names to a comma‑separated string of device names.
    #     """
    #     ports_with_devices: dict[str, str] = {}

    #     def _scan_port(com: str):
    #         try:
    #             with AsciiConnection.open_serial_port(com) as connection:
    #                 devices = connection.detect_devices()
    #                 # filter by expected number of devices if provided
    #                 if expected_devices is None or len(devices) == expected_devices:
    #                     ports_with_devices[com] = ", ".join(d.name for d in devices)
    #         except (NoDeviceFoundException, SerialPortBusyException):
    #             pass
    #         except Exception as err:
    #             print(f"Error scanning {com}: {err}")

    #     # scan ports concurrently
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    #         for com in Tools.list_serial_ports():
    #             executor.submit(_scan_port, com)

    #     return ports_with_devices

    # def validate_connection(self, expected_devices: int) -> None:
    #     """
    #     Verify that the expected number of devices are connected.

    #     Raises AssertionError if the number does not match.
    #     """
    #     assert len(self.devices) == expected_devices, (
    #         f"Not all devices are connected; expected {expected_devices}, "
    #         f"found {len(self.devices)}."
    #     )

    # ... rest of your methods remain unchanged ...
        

    # def validate_connection(self):
    #     """
    #     assumes the connection has already been opened and verifies
    #     we are connected to a valid set of devices

    #     Returns
    #     -------
    #     None
    #     """
    #     assert len(self.devices) == 6, "Not all devices are connected"

    # def read_positions(self, units: Units = Units.LENGTH_MICROMETRES):
    #     """
    #     Return a list of the positions of the motors

    #     Parameters
    #     ----------
    #     units : Units
    #         The units to return the positions in

    #     Returns
    #     -------
    #     positions : list
    #         A list of the positions of the motors
    #     """

    #     positions = []
    #     for dev in self.devices:
    #         positions.append(dev.get_position(units))
    #     return positions

# if __name__ == "__main__":
#     motor = MotorChain("/dev/ttyUSB1")

#     for axis in [Axes.X, Axes.Y, Axes.Z, Axes.ROLL, Axes.YAW, Axes.PITCH]:
#         print(
#             f"Axis {axis.name} position: {motor.devices[axis.value].get_position(Units.LENGTH_MILLIMETRES)} mm"
#         )

#     motor.home_all()

#     motor.move_proportion([Axes.X, Axes.Y, Axes.ROLL, Axes.YAW, Axes.PITCH], [0.5] * 5)
#     motor.move_proportion([Axes.Z], [1.0])
