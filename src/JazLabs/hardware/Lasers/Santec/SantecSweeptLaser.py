import time

import pyvisa


class LaserObject:
    def __init__(self, LaserID=None):
        super().__init__()
        rm = pyvisa.ResourceManager()

        if LaserID is None:
            print(rm.list_resources())
            print("Need to identify the Santec resource and re-initialize the class with LaserID")
            return

        self.LaserID = LaserID
        self.Laser = rm.open_resource(self.LaserID, timeout=2000)
        self.channel = 0
        self.source = 0

        self._idn = self.idn()
        print("Connection successful. Device ID:", self._idn)

        self.get_wavelength_units()
        self.get_wavelength_nm()
        self.get_laser_output_state()
        self.set_power_units("mW")
        self.get_power_units()
        self.get_power_level()
        self.get_power_attenuation()

    def __del__(self):
        print("Scope has been disconnected")
        self.close()

    def close(self):
        if hasattr(self, "Laser") and self.Laser is not None:
            self.Laser.close()

    def query(self, command):
        return self.Laser.query(command)

    def write(self, command):
        self.Laser.write(command)
        return True

    def idn(self):
        return self.query("*IDN?")

    def reset(self):
        self.write("*RST")

    def clear_status(self):
        self.write("*CLS")

    def set_cw_mode(self):
        return True

    def set_sweep_mode(self):
        return True

    def get_wavelength_units(self):
        wavelength_units_int = int(self.query(":WAVelength:UNIT?"))
        self.wavelength_units = "nm" if wavelength_units_int == 0 else "THz"
        return self.wavelength_units

    def set_wavelength_units(self, wavelength_units="nm"):
        if wavelength_units not in ("nm", "THz"):
            raise ValueError("Invalid wavelength units. Use 'nm' or 'THz'.")
        self.write(":WAVelength:UNIT " + wavelength_units)
        return self.get_wavelength_units()

    def wait_until_wavelength_settled(
        self,
        target_nm=None,
        tolerance_nm=0.001,
        timeout_s=30,
        poll_interval_s=0.1,
    ):
        start_time = time.time()
        while True:
            current_nm = self.get_wavelength_nm()
            if target_nm is None or abs(current_nm - target_nm) <= tolerance_nm:
                return True
            if time.time() - start_time > timeout_s:
                raise TimeoutError(
                    f"Laser wavelength did not settle within {timeout_s} s. "
                    f"Target={target_nm:.6f} nm, current={current_nm:.6f} nm"
                )
            time.sleep(poll_interval_s)

    def set_wavelength_nm(self, wavelength_nm, wait=True, timeout_s=30, poll_interval_s=0.1):
        wavelength_m = wavelength_nm * 1e-9
        self.write(":WAVELENGTH " + str(wavelength_m))
        if wait:
            self.wait_until_wavelength_settled(
                target_nm=wavelength_nm,
                timeout_s=timeout_s,
                poll_interval_s=poll_interval_s,
            )
        return self.get_wavelength_nm()

    def get_wavelength_setpoint_nm(self):
        return float(self.query(":WAVELENGTH?"))

    def get_min_wavelength_nm(self):
        return 1250.0

    def get_max_wavelength_nm(self):
        return 1630.0

    def get_wavelength_nm(self):
        self.wavelength = float(self.query(":WAVELENGTH?"))
        return self.wavelength

    def get_laser_output_state(self):
        return self.query(":POWer:STATe?").strip() == "1"

    def laser_on(self):
        self.write(":POWer:STATe 1")

    def laser_off(self):
        self.write(":POWer:STATe 0")

    def get_power_units(self):
        power_units_int = int(self.query(":POWer:UNIT?"))
        self.power_units = "dBm" if power_units_int == 0 else "mW"
        return self.power_units

    def set_power_units(self, units):
        if units not in ("dBm", "mW"):
            raise ValueError("Invalid power units. Use 'dBm' or 'mW'.")
        unit_code = 0 if units == "dBm" else 1
        self.write(":POWer:UNIT " + str(unit_code))
        return self.get_power_units()

    def set_power_dbm(self, power_dbm):
        self.set_power_units("dBm")
        self.set_power_level(power_dbm)

    def set_power_mw(self, power_mw):
        self.set_power_units("mW")
        self.set_power_level(power_mw)

    def get_power_level(self):
        self.power_level_set = float(self.query(":POWer?"))
        self.power_level = float(self.query(":POWer:ACTual?"))
        return self.power_level

    def set_power_level(self, power_level=0.0):
        if power_level < 0:
            raise ValueError("Invalid power level value. It must be non-negative.")
        self.write(":POWer " + str(power_level))
        return self.get_power_level()

    def get_power(self):
        return float(self.query(":POWer:ACTual?"))

    def get_min_power_dbm(self):
        raise NotImplementedError("Minimum power query is not implemented for this Santec laser.")

    def get_max_power(self):
        raise NotImplementedError("Maximum power query is not implemented for this Santec laser.")

    def get_power_attenuation(self):
        self.power_attenuation = float(self.query(":POWer:ATTenuation?"))
        return self.power_attenuation

    def set_power_attenuation(self, power_attenuation=0.0):
        if power_attenuation < 0:
            raise ValueError("Invalid attenuation value. It must be non-negative.")
        self.write(":POWer:ATTenuation " + str(power_attenuation))
        return self.get_power_attenuation()

    def get_coherence_control(self):
        self.coherence_control = int(self.query(":COHCtrl?"))
        return self.coherence_control

    def set_coherence_control(self, coherence_control=0):
        if coherence_control not in (0, 1):
            raise ValueError("Invalid coherence_control value. Use 0 (OFF) or 1 (ON).")
        self.write(":COHCtrl " + str(coherence_control))
        return self.get_coherence_control()

    def get_output_condition(self):
        state = self.get_laser_output_state()
        return {
            "raw": int(state),
            "key_on": True,
            "fibre_connected": True,
            "interlock_short": True,
            "ready": state,
        }

    def get_heatup_percent(self):
        return 100.0

    def wait_for_heatup(self, poll_interval=10):
        return True

    def configure_sweep_nm(self, start_nm, stop_nm, step_nm, dwell_s=1.0):
        self._sweep_start_nm = float(start_nm)
        self._sweep_stop_nm = float(stop_nm)
        self._sweep_step_nm = float(step_nm)
        self._sweep_dwell_s = float(dwell_s)

    def single_sweep(self):
        raise NotImplementedError("Sweep commands are not implemented for this Santec class yet.")

    def repeat_sweep(self):
        raise NotImplementedError("Sweep commands are not implemented for this Santec class yet.")

    def pause_sweep(self):
        raise NotImplementedError("Sweep commands are not implemented for this Santec class yet.")

    def continue_sweep(self):
        raise NotImplementedError("Sweep commands are not implemented for this Santec class yet.")
