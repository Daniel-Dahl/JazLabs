import pyvisa
import time
import re

class LaserObject_JDSUniphaseTunableLaser:
    """
    JDS/Photonetics/EXFO-style tunable laser over GPIB/VISA.
    Adds robust write/read with LF+EOI, serial-poll sync, and verification loops
    for Set_Power() and Set_wavelength().
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

        # Per manual: terminate with LF and/or EOI
        self.Laser.write_termination = "\n"
        self.Laser.read_termination  = "\n"
        self.Laser.send_end = True

        # User prefs / defaults
        self.channel = 0
        self.Source = 0
        self.TryCount = 5
        self.PowerUnits = "MW"  # default (no unit query exists on this model)

        # Optional: identify (not all firmwares support *IDN?)
        try:
            idn = self.Laser.query("*IDN?").strip()
            if idn:
                print("Connected to:", idn)
        except Exception:
            pass
        self.Get_PowerState()

    # --------------------------
    # Low-level helpers
    # --------------------------
    # This should really be using Laser.read_stb() to do a serial poll and look at the bit to see if status messages have 
    # changed but the device doesnt seem to support the serial polling so we just do a simple delay here.
    def _poll_stable(self, max_time=0.1, dwell=0.01, stable_reads=2):
        time.sleep(max_time)
        return None

    def _parse_numeric_equals(self, resp, key):
        """
        Parse responses like 'L=1550' or 'P=1.23'.
        Returns float or None.
        """
        if resp is None:
            return None
        m = re.match(rf"^\s*{re.escape(key)}\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$", resp.strip(), flags=re.IGNORECASE)
        return float(m.group(1)) if m else None

    # --------------------------
    # Wavelength
    # --------------------------
    def Get_wavelength(self, printResponse=True):
        """
        Robust wavelength read using 'L?' with pre/post serial-poll sync and stability check.
        Expected response: 'L=1550.000'
        """
        if not self.Laser:
            return None

        self._poll_stable(max_time=0.3)

        last_val = None
        for _ in range(self.TryCount):
            try:
                resp = self.Laser.query("L?").strip()
            except Exception:
                # transient I/O hiccup; brief pause then retry
                time.sleep(0.12)
                continue

            wl = self._parse_numeric_equals(resp, "L")
            if wl is not None:
                if wl == last_val:
                    # stable reading
                    if printResponse:
                        print(f"Wavelength is {wl:.3f} nm")
                    self.wavelength = wl
                    return wl
                last_val = wl

            self._poll_stable(max_time=0.3)
            time.sleep(0.12)

        # Fallback: return last seen good number if we had one
        if last_val is not None:
            if printResponse:
                print(f"Wavelength (last read): {last_val:.3f} nm")
            self.wavelength = last_val
            return last_val

        print("No valid wavelength response.")
        return None

    def Set_wavelength(self, wavelength=1550.0, tol_nm=0.01,Wait=True):
        """
        Robust wavelength set:
          - send 'L=<nm>'
          - serial-poll sync
          - verify via L? until within tol_nm, with auto-resend as needed
        """
        if not self.Laser:
            return None

        cmd = f"L={float(wavelength)}"
        if Wait:
            self._poll_stable(max_time=0.3)

            last_read = None
            for _ in range(self.TryCount):
                try:
                    self.Laser.write(cmd)
                except Exception:
                    # Clear and re-try on transient write error
                    try:
                        self.Laser.clear()
                    except Exception:
                        pass

                self._poll_stable(max_time=1)
                time.sleep(0.12)

                current = self.Get_wavelength(printResponse=False)
                last_read = current

                if isinstance(current, float) and abs(current - wavelength) <= tol_nm:
                    # Converged
                    self.wavelength = current
                    return self.wavelength

                # Not converged: resend command on next loop

            print("Warning: Wavelength setting did not converge within the maximum number of tries.")
            if last_read is not None:
                self.wavelength = last_read
            return getattr(self, "wavelength", None)
        else:
            self.Laser.write(cmd)

    

    # --------------------------
    # Frequency
    # --------------------------
    def Get_frequency(self, printResponse=True):
        """
        Robust wavelength read using 'L?' with pre/post serial-poll sync and stability check.
        Expected response: 'L=1550.000'
        """
        if not self.Laser:
            return None

        self._poll_stable(max_time=0.3)

        last_val = None
        for _ in range(self.TryCount):
            try:
                resp = self.Laser.query("f?").strip()
            except Exception:
                # transient I/O hiccup; brief pause then retry
                time.sleep(0.12)
                continue

            wl = self._parse_numeric_equals(resp, "f")
            if wl is not None:
                if wl == last_val:
                    # stable reading
                    if printResponse:
                        print(f"Frequency is {wl:.1f} GHz")
                    self.frequency = wl
                    return wl
                last_val = wl

            self._poll_stable(max_time=0.3)
            time.sleep(0.12)

        # Fallback: return last seen good number if we had one
        if last_val is not None:
            if printResponse:
                print(f"Frequency (last read): {last_val:.1f} GHz")
            self.frequency = last_val
            return last_val

        print("No valid wavelength response.")
        return None

    def Set_frequency(self, frequency=193414.5, tol_GHz=0.5):
        """
        Robust frequency set:
          - send 'f=<GHz>'
          - serial-poll sync
          - verify via f? until within tol_GHz, with auto-resend as needed
        """
        if not self.Laser:
            return None

        cmd = f"f={float(frequency)}"
        self._poll_stable(max_time=0.3)

        last_read = None
        for _ in range(self.TryCount):
            try:
                self.Laser.write(cmd)
            except Exception:
                # Clear and re-try on transient write error
                try:
                    self.Laser.clear()
                except Exception:
                    pass

            self._poll_stable(max_time=1)
            time.sleep(0.12)

            current = self.Get_frequency(printResponse=False)
            last_read = current

            if isinstance(current, float) and abs(current - frequency) <= tol_GHz:
                # Converged
                self.frequency = current
                return self.frequency

            # Not converged: resend command on next loop

        print("Warning: frequency setting did not converge within the maximum number of tries.")
        if last_read is not None:
            self.frequency = last_read
        return getattr(self, "frequency", None)

    # --------------------------
    # Power state
    # --------------------------
    def Get_PowerState(self):
        """
        'P?' returns either 'DISABLE' or 'P=<value>'.
        """
        if not self.Laser:
            return None

        state = None
        last = None
        for _ in range(self.TryCount):
            try:
                resp = self.Laser.query("P?").strip()
            except Exception:
                time.sleep(0.1)
                continue

            if resp.upper().startswith("DISABLE"):
                state = 0
                break
            if resp.upper().startswith("ENABLE"):
                state = 1
                break
            if resp.upper().startswith("P"):
                state = 1
                break

            last = resp
            time.sleep(0.1)

        if state == 0:
            print("Laser Power is OFF")
        elif state == 1:
            print("Laser Power is ON")
        else:
            print("Unknown Power State response:", last if last is not None else "None")
        self.PowerState = state
        return self.PowerState

    def Set_PowerState(self, PowerState=0):
        """
        ENABLE/DISABLE emission; verify via Get_PowerState().
        """
        if PowerState not in (0, 1):
            print("Invalid Power state value: use 0=OFF or 1=ON")
            return None

        cmd = "ENABLE" if PowerState == 1 else "DISABLE"
        self._poll_stable(max_time=0.3)
        try:
            self.Laser.write(cmd)
        except Exception:
            try:
                self.Laser.clear()
            except Exception:
                pass
        self._poll_stable(max_time=0.3)
        return self.Get_PowerState()

    # --------------------------
    # Power units / level
    # --------------------------
    def Get_PowerUnits(self):
        if self.PowerUnits == "DBM":
            print("Power units are in dBm")
        elif self.PowerUnits == "MW":
            print("Power units are in mW")
        return self.PowerUnits

    def Set_PowerUnits(self, PowerUnits="MW"):
        if PowerUnits not in ("DBM", "MW"):
            print("Invalid Power units: use 'DBM' or 'MW'")
            return self.PowerUnits
        self.PowerUnits = PowerUnits
        try:
            self.Laser.write(str(PowerUnits))
        except Exception:
            pass
        return self.Get_PowerUnits()

    def Get_Power(self, printResponse=True):
        """
        Query output power with 'P?' and parse 'P=<value>'.
        """
        if not self.Laser:
            return None

        # Some firmwares occasionally echo ENABLE/DISABLE first; loop until numeric
        val = None
        for _ in range(self.TryCount):
            try:
                resp = self.Laser.query("P?").strip()
            except Exception:
                time.sleep(0.1)
                continue
            val = self._parse_numeric_equals(resp, "P")
            if val is not None:
                break
            time.sleep(0.1)

        if val is None:
            print("No valid power response.")
            return None

        self.Power = val
        if printResponse:
            print(f"Power is {self.Power:.3f} {self.PowerUnits}")
        return self.Power

    def Set_Power(self, Power=1.0, tol=0.011):
        """
        Robust power set:
          - send 'P=<value>'
          - serial-poll sync
          - verify via P? until within tolerance, with auto-resend as needed
        """
        if not self.Laser:
            return None

        cmd = f"P={float(Power)}"
        self._poll_stable(max_time=0.3)

        last_read = None
        for _ in range(self.TryCount):
            try:
                self.Laser.write(cmd)
            except Exception:
                try:
                    self.Laser.clear()
                except Exception:
                    pass

            self._poll_stable(max_time=0.4)
            time.sleep(0.12)

            current = self.Get_Power(printResponse=False)
            last_read = current

            if isinstance(current, float) and abs(current - Power) <= tol:
                self.Power = current
                return self.Power
            # else: resend next loop

        print("Warning: Power setting did not converge within the maximum number of tries.")
        if last_read is not None:
            self.Power = last_read
        return getattr(self, "Power", None)

    # --------------------------
    # Utilities
    # --------------------------
    def SendCommand(self, command):
        if not self.Laser:
            return None
        return self.Laser.write(command)

    def QueryCommand(self, command):
        if not self.Laser:
            return None
        message=self.Laser.query(command)
        print( message )
        return 

    def __del__(self):
        try:
            if hasattr(self, "Laser") and self.Laser is not None:
                self.Laser.close()
                print("Laser disconnected")
        except Exception:
            pass