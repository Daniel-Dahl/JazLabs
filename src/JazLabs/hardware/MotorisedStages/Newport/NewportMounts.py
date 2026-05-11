import time
import pyvisa
from pyvisa import constants as vc
import enum
import numpy as np

class Axes(enum.Enum):
    YAW = "U"
    PITCH = "V"

class NewportM100D_VISA:
    """
    PyVISA driver for the Newport CONEX-AG-M100D (CONEX-AGAP controller).
    On macOS with pyvisa-py, use a resource like:
        'ASRL/dev/cu.usbmodemA69MCXZL::INSTR'
    """

    def __init__(self, resource: str, address: int = 1, timeout_ms: int = 500, backend: str = '@py'):
        """
        Parameters
        ----------
        resource : str
            VISA resource string, e.g. on macOS:
                'ASRL/dev/cu.usbmodemA69MCXZL::INSTR'
        address : int
            Controller address (usually 1).
        timeout_ms : int
            VISA timeout in milliseconds.
        backend : str
            VISA backend, '@py' for pyvisa-py (handy on macOS).
        """
        self.address = int(address)
        self.rm = pyvisa.ResourceManager(backend)
        self.inst = self.rm.open_resource(resource)

        # --- Configure serial parameters (match Newport manual) ---
        self.inst.baud_rate = 921600
        self.inst.data_bits = 8
        self.inst.parity = vc.Parity.none
        self.inst.stop_bits = vc.StopBits.one
        self.inst.flow_control = vc.VI_ASRL_FLOW_XON_XOFF

        # Termination & timeout
        self.inst.write_termination = "\r\n"
        self.inst.read_termination = "\r\n"
        self.inst.timeout = timeout_ms  # in ms

    # ---------- low-level helpers ----------

    def _build_cmd(self, body: str) -> str:
        # prepend controller address, e.g. '1PAU0.0000'
        return f"{self.address}{body}"

    def write(self, body: str):
        cmd = self._build_cmd(body)
        self.inst.write(cmd)

    def query(self, body: str) -> str:
        cmd = self._build_cmd(body)
        resp = self.inst.query(cmd)
        return resp.strip()

    # ---------- basic controller ops ----------

    def get_id(self) -> str:
        return self.query("ID?")

    def firmware_version(self) -> str:
        return self.query("VE")

    def enable(self):
        self.write("MM1")

    def disable(self):
        self.write("MM0")

    def get_status_raw(self) -> str:
        return self.query("TS")

    def is_ready(self) -> bool:
        ts = self.get_status_raw()
        if len(ts) < 2:
            return False
        state_hex = ts[-2:]
        moving_states = {"28", "29", "46"}  # MOVING, STEPPING, JOGGING
        return state_hex not in moving_states

    def wait_until_ready(self, poll_period=0.05, timeout=5.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_period)
        return False

    # ---------- position & motion ----------

    def get_position(self, axis: str = "U") -> float:
        resp = self.query(f"TP{axis}")
        try:
            return float(resp.split(axis)[-1])
        except ValueError:
            raise RuntimeError(f"Could not parse TP response: {resp!r}")

    def move_abs(self, position_deg: float, axis: str = "U", wait: bool = True):
        cmd = f"PA{axis}{position_deg:.6f}"
        self.write(cmd)
        # diff=100000000000
        # while diff>0.002:
        #     currentSteps=self.get_position()
        #     diff=abs(currentSteps-position_deg)
        if wait and not self.wait_until_ready():
            raise TimeoutError("Timeout waiting for absolute move to finish")

    def move_rel(self, delta_deg: float, axis: str = "U", wait: bool = True):
        cmd = f"PR{axis}{delta_deg:.6f}"
        self.write(cmd)
        if wait and not self.wait_until_ready():
            raise TimeoutError("Timeout waiting for relative move to finish")
    def get_limits(self, axis: str = "U"):
        """
        Return the (min_limit, max_limit) in degrees for the given axis.

        Uses:
            SL?<axis>  -> negative software limit
            SR?<axis>  -> positive software limit
        """
        # Query the negative (lower) limit
        sl_resp = self.query(f"SL?{axis}")
        # Query the positive (upper) limit
        sr_resp = self.query(f"SR?{axis}")

        # Each response looks like '1SLU-1.0000' or '1SRU+1.0000'
        try:
            min_limit = float(sl_resp.split(axis)[-1])
            max_limit = float(sr_resp.split(axis)[-1])
        except ValueError:
            raise RuntimeError(f"Could not parse limit responses: {sl_resp!r}, {sr_resp!r}")

        return min_limit, max_limit

    def stop(self):
        self.write("ST")

    # ---------- cleanup ----------

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
        

import time
import pyvisa
from pyvisa import constants as pv


class AgilisUC8Stage:
    """
    Control a single Agilis stage (e.g. AG-LS25 / AG-LS25-27) via an AG-UC8 controller
    over USB using PyVISA.

    Communication (USB) settings from manual:
      - Baud rate: 921600
      - Data bits: 8
      - Parity:    None
      - Stop bits: 1
      - Flow ctrl: None
      - Term:      CR/LF

    Motor addressing on AG-UC8 (manual, section 5.3):
      - Motors are grouped in 4 channels, 2 motors per channel.
      - CCn selects channel 1..4.
      - Within a channel, axis xx = 1 or 2 selects the first / second actuator.
    """

    def __init__(
        self,
        resource_name: str,channel:int =1,
        motor: int = 1,
        travel_mm: float | None = 12.0,
        timeout: float = 0.5,
    ):
        """
        Parameters
        ----------
        resource_name : str
            VISA resource string, e.g. "ASRL/dev/ttyUSB2::INSTR".
        motor : int
            Motor index 1..8 (see manual 5.3 for mapping).
        travel_mm : float or None
            Full travel range of the stage in mm.
            - AG-LS25      : 12.0 mm
            - AG-LS25-27   : 27.0 mm
            If None, mm-conversion helpers are disabled.
        timeout : float
            Default VISA timeout in seconds for "normal" commands.
        rm : pyvisa.ResourceManager or None
            Optional existing resource manager.
        """
        if not (1 <= int(motor) <= 8):
            raise ValueError("motor must be in [1..8] for AG-UC8")

        self.motor = int(motor)
        self.travel_mm = travel_mm

        # Map motor → channel (1..4), axis (1 or 2)
        # Motor 1 → channel 1, axis 1
        # Motor 2 → channel 1, axis 2
        # Motor 3 → channel 2, axis 1
        # ...
        self.channel = channel
        # (self.motor - 1) // 2 + 1
        self.axis = 1 
        # if (self.motor % 2) == 1 else 2

        self.rm = pyvisa.ResourceManager("@py")
        self.inst = self.rm.open_resource(resource_name)

        # Default timeout in ms
        self.default_timeout_ms = int(timeout * 1000)
        self.inst.timeout = self.default_timeout_ms

        # Serial configuration (USB virtual COM) from manual section 5.4.1
        # if resource_name.upper().startswith("ASRL"):
        #     self.inst.baud_rate = 921600
        #     self.inst.data_bits = 8
        #     self.inst.stop_bits = pv.StopBits.one
        #     self.inst.parity = pv.Parity.none
        #     self.inst.flow_control = pv.VI_ASRL_FLOW_NONE

        # # Termination CR/LF
        # self.inst.write_termination = "\r\n"
        # self.inst.read_termination = "\r\n"
        self.inst.timeout = 5000

        # Serial settings from manual
        self.inst.baud_rate = 921600
        self.inst.data_bits = 8
        self.inst.stop_bits = pv.StopBits.one
        self.inst.parity    = pv.Parity.none
        self.inst.flow_control = pv.VI_ASRL_FLOW_NONE

        # Termination
        self.inst.write_termination = "\r\n"
        self.inst.read_termination  = "\r\n"

        # Start in remote mode & select correct channel
        self._ensure_remote()
        self._select_channel()

    # ------------------------------------------------------------------ #
    # Context manager helpers
    # ------------------------------------------------------------------ #

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ------------------------------------------------------------------ #
    # Low-level helpers
    # ------------------------------------------------------------------ #

    def _ensure_remote(self):
        """
        Ensure controller is in remote mode (MR).
        MR is global (no axis, no parameter).
        """
        try:
            self.inst.write("MR")
        except Exception:
            # If already remote or command not supported, ignore.
            pass

    def _select_channel(self):
        """
        Select the correct channel for this motor via CCn.
        CCn is global (no axis); only on AG-UC8/UC8PC.
        Manual 5.7: must be in remote mode, both axes state 0, no PA/MA running.
        """
        # Best-effort; if CC fails, TE will contain error.
        self._ensure_remote()
        self.inst.write(f"CC{self.channel}")
        # Optional: read & ignore TE result
        try:
            _ = int(self.inst.query("TE").strip())
        except Exception:
            pass

    def _axis_prefix(self, cmd: str) -> str:
        """
        Return axis-prefixed command like '1PR100' or '2TS'.
        Axis xx = 1 or 2 within selected channel.
        """
        return f"{self.axis}{cmd}"

    def _write_axis(self, cmd: str):
        """Send axis-specific command, no reply expected."""
        # self._select_channel()
        self.inst.write(self._axis_prefix(cmd))

    def _query_axis(self, cmd: str) -> str:
        """Send axis-specific query and return stripped reply."""
        self._select_channel()
        return self.inst.query(self._axis_prefix(cmd)).strip()

    # ------------------------------------------------------------------ #
    # Global controller commands (no axis)
    # ------------------------------------------------------------------ #

    def get_firmware_version(self) -> str:
        """
        VE — firmware version of the controller (manual 4.6, VE).  [oai_citation:4‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        return self.inst.query("VE").strip()

    def get_last_error(self) -> int:
        """
        TE — error code of previous command (manual 4.6, TE).  [oai_citation:5‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        return int(self.inst.query("TE").strip())

    def reset_controller(self):
        """
        RS — reset controller; returns to local mode and defaults (manual 4.6, RS).  [oai_citation:6‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        self.inst.write("RS")

    def get_limit_status(self) -> str:
        """
        PH — global limit switch status (PH0..PH3); no axis allowed (manual PH).  [oai_citation:7‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        return self.inst.query("PH").strip()

    # ------------------------------------------------------------------ #
    # Axis-specific status / info
    # ------------------------------------------------------------------ #

    def get_status(self,retries=20,delay=0.05) -> int:
        """
        TS — get axis status (manual TS):
            0 = ready, 1 = stepping(PR), 2 = jogging(JA), 3 = moving to limit(MV/MA/PA).  [oai_citation:8‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        for _ in range(retries):
            try:
                # resp = self._query_axis("TS")
                self.inst.write(f"{self.axis}TP")
                
                reply = self.inst.read().strip()
                # Accept '1TS0' or 'TS0' or just '0'
                for prefix in (f"{self.axis}TS", "TS",'TTS'):
                    if reply.startswith(prefix):
                        return int(reply[len(prefix):])
                # return int(resp)
                time.sleep(delay)
            except Exception as e:
                print(f"Retry due to: {e}")
                time.sleep(delay)
    

    def get_stepsFromZero(self, retries=20, delay=0.05):
        """
        Query the step count more robustly by explicitly writing and reading.
        Retries until a valid 'TP' reply is received.
        """
        for _ in range(retries):
            try:
                # self.inst.write(f"{self.axis}TP")
                
                # reply = self.inst.read().strip()
                # if "TP" in reply:
                #     for prefix in (f"{self.axis}TP", "TP"):
                #         if reply.startswith(prefix):
                #             return int(reply[len(prefix):])
                self.inst.write(f"{self.axis}TP")
                
                reply = self.inst.read().strip()
                # print(reply)
                if "TP" in reply:
                    # print('true')
                    for prefix in (f"{self.axis}TP", "TP",'TTP'):
                        if reply.startswith(prefix):
                            # print('tes')
                            return int(reply[len(prefix):])
                time.sleep(delay)
            except Exception as e:
                print(f"Retry due to: {e}")
                time.sleep(delay)

        raise TimeoutError(f"Failed to get valid TP response after {retries} tries")
        
    def wait_until_ready(self, timeout: float = 60.0, poll_interval: float = 0.1):
        """
        Poll TS until axis status == 0 (READY) or timeout.  [oai_citation:9‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        t0 = time.time()
        while True:
            status = self.get_status()
            print(status)
            if status == 0:
                return
            if time.time() - t0 > timeout:
                print("bad")
                raise TimeoutError(
                    f"Timed out waiting for READY on motor {self.motor}, "
                    f"status={status}"
                )
            time.sleep(poll_interval)
            print("wait done")

    def tell_steps(self) -> int:
        """
        TP — tell number of accumulated steps since power-on or last ZP.  [oai_citation:10‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        Returns signed integer (forward steps - backward steps).
        """
        resp = self._query_axis("TP")
        for prefix in (f"{self.axis}TP", "TP"):
            if resp.startswith(prefix):
                return int(resp[len(prefix):])
        return int(resp)

    def zero_position(self):
        """
        ZP — zero the internal step counter for this axis (manual ZP).  [oai_citation:11‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        self._write_axis("ZP")

    # ------------------------------------------------------------------ #
    # Motion commands
    # ------------------------------------------------------------------ #

    # def move_relative_steps(self, nsteps: int, wait: bool = True, timeout: float = 60.0):
    #     """
    #     PR — relative move of 'nsteps' with current step amplitude SU (manual PR).  [oai_citation:12‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

    #     Parameters
    #     ----------
    #     nsteps : int
    #         Signed integer number of steps.
    #     wait : bool
    #         If True, block until axis is READY again.
    #     timeout : float
    #         Max time to wait for READY.
    #     """
    #     self._ensure_remote()
    #     self._write_axis(f"PR{int(nsteps)}")
    #     # if wait:
    #         # self.wait_until_ready(timeout=timeout)
    #     # self.StepsFromZero=self._query_axis(f"TP")
    #     time.sleep(2)
    #     self.StepsFromZero=self.get_stepsFromZero()
    #     return self.StepsFromZero
        
        
    def move_relative_steps(self, nsteps: int):
    
        self.inst.write(f"{self.axis}PR{nsteps}")
        moving=True
        # while moving:
        #     # status=self.get_status()
        #     reply=self.inst.query("TS")
        #     status=int(reply[-1])
        #     if status==0:
        #         moving=False
                
        PreviousSteps=self.get_stepsFromZero() 
        diff=100000000000
        while diff>2:
            currentSteps=self.get_stepsFromZero()
            diff=abs(currentSteps-PreviousSteps)
            PreviousSteps=np.copy(currentSteps)
        self.StepsFromZero=self.get_stepsFromZero() 
        return self.StepsFromZero
    

    def move_absolute_1000(self, pos_1000: int, timeout: float = 120.0) -> int:
        """
        PA — absolute move to position nn in 1/1000 of full travel (manual PA).  [oai_citation:13‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

        Parameters
        ----------
        pos_1000 : int
            Target position in [0..1000].
        timeout : float
            Maximum time (seconds) to wait for the PA to complete.

        Returns
        -------
        int
            The target position reported back by the controller (nn).
        """
        if not (0 <= int(pos_1000) <= 1000):
            raise ValueError("pos_1000 must be in [0..1000]")

        self._ensure_remote()
        self._select_channel()

        # PA blocks USB comms until motion is finished, then returns "xxPAnn"
        old_timeout = self.inst.timeout
        self.inst.timeout = int(timeout * 1000)
        try:
            self.inst.write(self._axis_prefix(f"PA{int(pos_1000)}"))
            reply = self.inst.read().strip()
        finally:
            self.inst.timeout = old_timeout

        # Parse XXPAnn
        for prefix in (f"{self.axis}PA", "PA"):
            if reply.startswith(prefix):
                return int(reply[len(prefix):])
        # Fallback: last integer in reply
        for tok in reply.split():
            try:
                return int(tok)
            except ValueError:
                continue
        raise RuntimeError(f"Unexpected PA reply: {reply!r}")

    def measure_position_1000(self, timeout: float = 120.0) -> int:
        """
        MA — measure current position in 1/1000 of full travel (AG-LS25 only).  [oai_citation:14‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

        USB comms are blocked until done; command can take up to ~2 min.
        """
        self._ensure_remote()
        self._select_channel()

        old_timeout = self.inst.timeout
        self.inst.timeout = int(timeout * 1000)
        try:
            self.inst.write(self._axis_prefix("MA"))
            reply = self.inst.read().strip()
        finally:
            self.inst.timeout = old_timeout

        # Reply is distance from negative limit in 1/1000 of travel.
        # Accept "1MAnn" or "MAnn" or just "nn".
        for prefix in (f"{self.axis}MA", "MA"):
            if reply.startswith(prefix):
                return int(reply[len(prefix):])
        return int(reply)

    def stop(self):
        """
        ST — stop motion on this axis, set state to READY (manual ST).  [oai_citation:15‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
        """
        self._ensure_remote()
        self._write_axis("ST")

    # ------------------------------------------------------------------ #
    # Step amplitude & jog helpers
    # ------------------------------------------------------------------ #

    def set_step_amplitude(self, amplitude: int):
        """
        SU — set step amplitude (step size) for this axis.  [oai_citation:16‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

        Parameters
        ----------
        amplitude : int
            Integer in [-50..-1] or [1..50]; 0 is not allowed.
            Positive = forward amplitude; negative = backward amplitude.
        """
        a = int(amplitude)
        if a == 0 or not (-50 <= a <= 50):
            raise ValueError("amplitude must be in [-50..-1] U [1..50]")
        self._ensure_remote()
        self._write_axis(f"SU{a}")

    def get_step_amplitude_forward(self) -> int:
        """
        SU+? — query step amplitude in forward direction.
        """
        resp = self._query_axis("SU+?")
        # reply like "1SU+16" or "SU+16"
        for prefix in (f"{self.axis}SU+", "SU+"):
            if resp.startswith(prefix):
                return int(resp[len(prefix):])
        return int(resp)

    def get_step_amplitude_backward(self) -> int:
        """
        SU-? — query step amplitude in backward direction.
        """
        resp = self._query_axis("SU-?")
        for prefix in (f"{self.axis}SU-", "SU-"):
            if resp.startswith(prefix):
                return int(resp[len(prefix):])
        return int(resp)

    def jog(self, mode: int):
        """
        JA — start jog motion (manual JA).  [oai_citation:17‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

        mode:
            -4: negative, 666 steps/s at defined amplitude
            -3: negative, 1700 steps/s at max amplitude
            -2: negative, 100 steps/s at max amplitude
            -1: negative, 5 steps/s at defined amplitude
             0: stop jog, go to READY
             1: positive, 5 steps/s at defined amplitude
             2: positive, 100 steps/s at max amplitude
             3: positive, 1700 steps/s at max amplitude
             4: positive, 666 steps/s at defined amplitude
        """
        if not (-4 <= int(mode) <= 4):
            raise ValueError("jog mode must be between -4 and 4")
        self._ensure_remote()
        self._write_axis(f"JA{int(mode)}")

    # ------------------------------------------------------------------ #
    # Convenience mm-based methods for LS25 / LS25-27
    # ------------------------------------------------------------------ #

    # def _require_travel_mm(self):
    #     if self.travel_mm is None:
    #         raise RuntimeError("travel_mm is None; mm-based helpers disabled for this stage.")

    # def steps1000_to_mm(self, pos_1000: int) -> float:
    #     """Convert 0–1000 units to mm based on configured travel_mm."""
    #     self._require_travel_mm()
    #     return (float(pos_1000) / 1000.0) * float(self.travel_mm)

    # def mm_to_steps1000(self, pos_mm: float) -> int:
    #     """Convert mm to 0–1000 units based on configured travel_mm."""
    #     self._require_travel_mm()
    #     if not (0.0 <= pos_mm <= self.travel_mm):
    #         raise ValueError(f"pos_mm must be in [0, {self.travel_mm}]")
    #     return int(round(1000.0 * pos_mm / float(self.travel_mm)))

    # def move_absolute_mm(self, pos_mm: float, timeout: float = 120.0) -> float:
    #     """
    #     Move to an absolute physical position in mm using PA (0..1000 units).  [oai_citation:18‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)

    #     Returns the actual position in mm based on the PAnn value returned.
    #     """
    #     pos_1000 = self.mm_to_steps1000(pos_mm)
    #     reached_1000 = self.move_absolute_1000(pos_1000, timeout=timeout)
    #     return self.steps1000_to_mm(reached_1000)

    # def measure_position_mm(self, timeout: float = 120.0) -> float:
    #     """
    #     Measure current position using MA and convert result to mm.  [oai_citation:19‡Agilis-Piezo-Motor-Driven-Components-User-Manual.pdf](sediment://file_00000000fe1c71f59902f985e54d0991)
    #     """
    #     pos_1000 = self.measure_position_1000(timeout=timeout)
    #     return self.steps1000_to_mm(pos_1000)
    
import serial
import time
class NewportAgilisAxis:
    """
    Simple driver for a Newport/Agilis axis (e.g. LS* stages on an Agilis controller).

    Typical commands:
      - nPAxxxx : absolute move (steps)
      - nPRxxxx : relative move (steps)
      - nTP     : get position (steps)
      - nTS     : get status (0 = ready)

    where n is the axis number: 1, 2, ...
    """

    def __init__(self, port: str, axis: int = 1,
                 baudrate: int = 921600, timeout: float = 0.5):
        """
        Parameters
        ----------
        port : str
            Serial port name, e.g. 'COM5' or '/dev/ttyUSB0'
        axis : int
            Axis number (1, 2, ...)
        baudrate : int
            Baudrate used by the controller (check manual; often 921600 or 115200)
        timeout : float
            Read timeout in seconds
        """
        self.axis = int(axis)
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )
        # Clean any junk in the buffer
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self._write('OR')# set to the closed loop
        self._write('HT4')

    # ---------- low-level helpers ----------

    def _write(self, cmd: str) -> None:
        """
        Send a command to this axis, appending axis number and CR/LF.
        e.g. cmd='PA1000' -> '1PA1000\\r\\n' (for axis 1)
        """
        full_cmd = f"{self.axis}{cmd}\r\n"
        self.ser.write(full_cmd.encode("ascii"))

    def _query(self, cmd: str) -> str:
        """
        Send a command and read a single response line.
        Returns the raw response (stripped).
        """
        self._write(cmd)
        line = self.ser.readline().decode("ascii", errors="ignore").strip()
        return line

    # ---------- high-level API ----------

    def identify(self) -> str:
        """
        Query ID string.
        """
        resp = self._query("ID?")
        return resp

    def get_status(self) -> int:
        """
        TS — get axis status:
          0 = ready
          1 = stepping (PR)
          2 = jogging (JA)
          3 = moving to limit (MV/MA/PA)
        """
        resp = self._query("TS")
        # Accept '1TS0', 'TS0', or just '0'
        for prefix in (f"{self.axis}TS", "TS"):
            if resp.startswith(prefix):
                return int(resp[len(prefix):])
        return int(resp)  # fall back to plain integer

    def wait_ready(self, poll_delay: float = 0.05, timeout: float = 30.0) -> None:
        """
        Block until the axis reports 'ready' or timeout is reached.
        """
        t0 = time.time()
        while True:
            status = self.get_status()
            if status == 0:
                return
            if time.time() - t0 > timeout:
                raise TimeoutError("Axis did not become ready in time.")
            time.sleep(poll_delay)

    def get_position(self) -> float:
        """
        TP — get position in controller steps.
        """
        resp = self._query("TP")
        # print(resp)
        # Accept '1TP1234', 'TP1234', or just '1234'
        for prefix in (f"{self.axis}TP", "TP"):
            if resp.startswith(prefix):
                return float(resp[len(prefix):])
        return (resp)

    def move_absolute(self, position:float, wait: bool = True) -> None:
        """
        Move to an absolute position (in steps).

        Parameters
        ----------
        position_steps : int
            Target position in controller steps.
        wait : bool
            If True, block until motion is complete.
        """
        self._write(f"PA{float(position)}")
        # PreviousSteps=self.get_position() 
        diff=100000000000
        while diff>0.005:
            currentSteps=self.get_position()
            diff=abs(currentSteps-position)
            # PreviousSteps=np.copy(currentSteps)
        # if wait:
        #     self.wait_ready()

    def move_relative(self, delta_steps, wait: bool = True) -> None:
        """
        Move relative by a number of steps.

        Parameters
        ----------
        delta_steps : int
            Relative move (positive or negative).
        wait : bool
            If True, block until motion is complete.
        """
        self._write(f"PR{(delta_steps)}")
        if wait:
            self.wait_ready()

    def stop(self) -> None:
        """
        ST — stop motion immediately.
        """
        self._write("ST")

    def close(self) -> None:
        """
        Close the serial port.
        """
        if self.ser and self.ser.is_open:
            self.ser.close()


import serial
import time


class NewportESP300:
    """
    Serial driver for Newport ESP300 Motion Controller.
    Fully compliant with ESP300 User Manual.
    """
    class HomeMode:
        ZERO = 0          # OM0
        SWITCH_INDEX = 1  # OM1
        SWITCH_ONLY = 2   # OM2
    def __init__(
        self,
        port: str,
        baudrate: int = 19200,
        timeout: float = 1.0,
    ):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
            rtscts=True,          # REQUIRED per manual
        )

        self.term = "\r"

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    # ---------------- low-level ----------------

    def _write(self, cmd: str):
        self.ser.write((cmd + self.term).encode("ascii"))

    def _read(self) -> str:
        return self.ser.readline().decode("ascii", errors="ignore").strip()

    def write_axis(self, axis: int, cmd: str):
        self._write(f"{axis}{cmd}")

    def query_axis(self, axis: int, cmd: str) -> str:
        self.write_axis(axis, cmd)
        return self._read()

    # ---------------- axis control ----------------

    def motor_on(self, axis: int):
        self.write_axis(axis, "MO")

    def motor_off(self, axis: int):
        self.write_axis(axis, "MF")

    def stop(self, axis: int):
        self.write_axis(axis, "ST")

    # ---------------- status ----------------

    def motion_done(self, axis: int) -> bool:
        """
        MD — motion done status (preferred over TS)
        Returns 1 if done, 0 if moving.
        """
        resp = self.query_axis(axis, "MD")
        return resp.endswith("1")

    def wait_until_done(
        self,
        axis: int,
        poll_interval: float = 0.05,
        timeout: float = 60.0,
    ):
        t0 = time.time()
        while True:
            if self.motion_done(axis):
                return
            if time.time() - t0 > timeout:
                raise TimeoutError(f"Axis {axis} motion timeout")
            time.sleep(poll_interval)

    # ---------------- motion ----------------

    def set_velocity(self, axis: int, vel: float):
        self.write_axis(axis, f"VA{vel}")

    def set_acceleration(self, axis: int, acc: float):
        self.write_axis(axis, f"AC{acc}")

    def move_abs(self, axis: int, pos: float, wait: bool = True):
        self.write_axis(axis, f"PA{pos}")
        if wait:
            self.wait_until_done(axis)

    def move_rel(self, axis: int, delta: float, wait: bool = True):
        self.write_axis(axis, f"PR{delta}")
        if wait:
            self.wait_until_done(axis)

    def get_position(self, axis: int) -> float:
        resp = self.query_axis(axis, "TP")
        return float(resp.split()[-1])

    def set_home_mode(self, axis: int, mode: int):
        """
        Set home (origin search) mode.

        mode:
            0 = go to zero position
            1 = switch + encoder index
            2 = switch only
        """
        if mode not in (0, 1, 2):
            raise ValueError("Invalid home mode")
        self.write_axis(axis, f"OM{mode}")
    def home(
        self,
        axis: int,
        mode: int = 1,
        wait: bool = True,
        timeout: float = 120.0,
    ):
        """
        Perform a home (origin) search.

        Parameters
        ----------
        axis : int
            Axis number
        mode : int
            Home mode (0, 1, or 2)
        wait : bool
            Block until homing completes
        timeout : float
            Max time to wait
        """
        self.set_home_mode(axis, mode)
        self.write_axis(axis, "OR")

        if wait:
            self.wait_until_done(axis, timeout=timeout)
    # ---------------- cleanup ----------------

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

