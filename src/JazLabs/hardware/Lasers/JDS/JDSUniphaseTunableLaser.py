import re
import time

import pyvisa


class LaserObject:
    """
    JDS/Photonetics/EXFO-style tunable laser over GPIB/VISA.

    The public API matches the shared tunable-laser calls used by the Anritsu
    and Santec drivers while keeping the JDS command set internally.
    """

    def __init__(self, LaserID=None):
        rm = pyvisa.ResourceManager()

        if LaserID is None:
            print(rm.list_resources())
            print("Select the correct VISA resource from the list and re-initialise.")
            self.Laser = None
            return

        self.LaserID = LaserID
        self.Laser = rm.open_resource(self.LaserID, timeout=2000)
        self.Laser.write_termination = "\n"
        self.Laser.read_termination = "\n"
        self.Laser.send_end = True

        self.channel = 0
        self.source = 0
        self.try_count = 5
        self.power_units = "mW"

        try:
            self._idn = self.idn()
            print("Connection successful. Device ID:", self._idn)
        except Exception:
            self._idn = None

        self.get_laser_output_state()

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, "Laser") and self.Laser is not None:
            self.Laser.close()
            self.Laser = None

    def write(self, command):
        if self.Laser is None:
            return None
        self.Laser.write(command)
        return True

    def query(self, command):
        if self.Laser is None:
            return None
        return self.Laser.query(command).strip()

    def idn(self):
        return self.query("*IDN?")

    def reset(self):
        return self.write("*RST")

    def clear_status(self):
        return self.write("*CLS")

    def set_cw_mode(self):
        return True

    def set_sweep_mode(self):
        raise NotImplementedError("Sweep mode is not implemented for this JDS laser.")

    def _poll_stable(self, delay_s=0.1):
        time.sleep(delay_s)

    def _parse_numeric_equals(self, response, key):
        if response is None:
            return None
        match = re.match(
            rf"^\s*{re.escape(key)}\s*=\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*$",
            response.strip(),
            flags=re.IGNORECASE,
        )
        return float(match.group(1)) if match else None

    # -------------------------
    # Wavelength
    # -------------------------

    def wait_until_wavelength_settled(
        self,
        target_nm=None,
        tolerance_nm=0.001,
        timeout_s=30,
        poll_interval_s=0.1,
    ):
        start_time = time.time()
        last_nm = None

        while True:
            current_nm = self.get_wavelength_nm()

            if target_nm is not None:
                if abs(current_nm - target_nm) <= tolerance_nm:
                    return True
            elif last_nm is not None and current_nm == last_nm:
                return True

            if time.time() - start_time > timeout_s:
                if target_nm is None:
                    raise TimeoutError(
                        f"Laser wavelength did not settle within {timeout_s} s."
                    )
                raise TimeoutError(
                    f"Laser wavelength did not settle within {timeout_s} s. "
                    f"Target={target_nm:.6f} nm, current={current_nm:.6f} nm"
                )

            last_nm = current_nm
            time.sleep(poll_interval_s)

    def set_wavelength_nm(self, wavelength_nm, wait=True, timeout_s=30, poll_interval_s=0.1):
        self.set_cw_mode()
        self.write(f"L={float(wavelength_nm)}")

        if wait:
            self.wait_until_wavelength_settled(
                target_nm=wavelength_nm,
                timeout_s=timeout_s,
                poll_interval_s=poll_interval_s,
            )

        return self.get_wavelength_nm()

    def get_wavelength_setpoint_nm(self):
        return self.get_wavelength_nm()

    def get_min_wavelength_nm(self):
        raise NotImplementedError("Minimum wavelength query is not implemented for this JDS laser.")

    def get_max_wavelength_nm(self):
        raise NotImplementedError("Maximum wavelength query is not implemented for this JDS laser.")

    def get_wavelength_nm(self):
        last_nm = None
        for _ in range(self.try_count):
            response = self.query("L?")
            wavelength_nm = self._parse_numeric_equals(response, "L")
            if wavelength_nm is not None:
                if wavelength_nm == last_nm:
                    self.wavelength = wavelength_nm
                    return self.wavelength
                last_nm = wavelength_nm
            self._poll_stable()

        if last_nm is not None:
            self.wavelength = last_nm
            return self.wavelength

        raise RuntimeError("No valid wavelength response from JDS laser.")

    # -------------------------
    # Frequency
    # -------------------------

    def get_frequency_ghz(self):
        last_ghz = None
        for _ in range(self.try_count):
            response = self.query("f?")
            frequency_ghz = self._parse_numeric_equals(response, "f")
            if frequency_ghz is not None:
                if frequency_ghz == last_ghz:
                    self.frequency = frequency_ghz
                    return self.frequency
                last_ghz = frequency_ghz
            self._poll_stable()

        if last_ghz is not None:
            self.frequency = last_ghz
            return self.frequency

        raise RuntimeError("No valid frequency response from JDS laser.")

    def set_frequency_ghz(
        self,
        frequency_ghz,
        wait=True,
        tolerance_ghz=0.5,
        timeout_s=30,
        poll_interval_s=0.1,
    ):
        self.write(f"f={float(frequency_ghz)}")

        if wait:
            start_time = time.time()
            while True:
                current_ghz = self.get_frequency_ghz()
                if abs(current_ghz - frequency_ghz) <= tolerance_ghz:
                    return current_ghz
                if time.time() - start_time > timeout_s:
                    raise TimeoutError(
                        f"Laser frequency did not settle within {timeout_s} s. "
                        f"Target={frequency_ghz:.6f} GHz, current={current_ghz:.6f} GHz"
                    )
                time.sleep(poll_interval_s)

        return self.get_frequency_ghz()

    # -------------------------
    # Power
    # -------------------------

    def get_laser_output_state(self):
        response = self.query("P?")
        if response is None:
            return None

        response = response.strip().upper()
        self.output_state = not response.startswith("DISABLE")
        return self.output_state

    def laser_on(self):
        self.write("ENABLE")
        return self.get_laser_output_state()

    def laser_off(self):
        self.write("DISABLE")
        return self.get_laser_output_state()

    def get_power_units(self):
        return self.power_units

    def set_power_units(self, units):
        if units not in ("dBm", "mW"):
            raise ValueError("Invalid power units. Use 'dBm' or 'mW'.")

        command = "DBM" if units == "dBm" else "MW"
        self.write(command)
        self.power_units = units
        return self.get_power_units()

    def set_power_dbm(self, power_dbm):
        self.set_power_units("dBm")
        return self.set_power_level(power_dbm)

    def set_power_mw(self, power_mw):
        self.set_power_units("mW")
        return self.set_power_level(power_mw)

    def get_power_level(self):
        return self.get_power()

    def set_power_level(self, power_level=1.0, tolerance=0.011):
        self.write(f"P={float(power_level)}")
        self._poll_stable(0.4)

        current_power = self.get_power()
        if abs(current_power - power_level) <= tolerance:
            return current_power

        for _ in range(self.try_count - 1):
            self.write(f"P={float(power_level)}")
            self._poll_stable(0.4)
            current_power = self.get_power()
            if abs(current_power - power_level) <= tolerance:
                return current_power

        raise RuntimeError(
            f"Power setting did not converge. "
            f"Target={power_level:.6f} {self.power_units}, "
            f"current={current_power:.6f} {self.power_units}"
        )

    def get_power(self):
        for _ in range(self.try_count):
            response = self.query("P?")
            power = self._parse_numeric_equals(response, "P")
            if power is not None:
                self.power = power
                return self.power
            time.sleep(0.1)

        raise RuntimeError("No valid power response from JDS laser.")

    def get_min_power_dbm(self):
        raise NotImplementedError("Minimum power query is not implemented for this JDS laser.")

    def get_max_power(self):
        raise NotImplementedError("Maximum power query is not implemented for this JDS laser.")
