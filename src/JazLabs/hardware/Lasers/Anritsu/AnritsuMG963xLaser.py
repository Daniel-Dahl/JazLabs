import time
import serial


class LaserObject:
    STX = 0x02
    ETX = 0x03
    ACK = 0x06
    NAK = 0x15

    TYPE_COMMAND = 0x01
    TYPE_QUERY = 0x03
    TYPE_RESPONSE = 0x07
    TYPE_FORMAT_OK = 0x08
    TYPE_FORMAT_ERROR = 0x09

    def __init__(
        self,
        port="COM3",
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=5,
    ):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
        )

    def close(self):
        self.ser.close()

    def _make_frame(self, msg_type, data):
        data_bytes = data.encode("ascii")
        length = len(data_bytes)

        body = bytes([length, msg_type]) + data_bytes + bytes([self.ETX])

        bcc = 0
        for b in body:
            bcc ^= b

        return bytes([self.STX]) + body + bytes([bcc])

    def _read_frame(self):
        # wait for STX
        while True:
            b = self.ser.read(1)
            if not b:
                raise TimeoutError("Timed out waiting for STX")
            if b[0] == self.STX:
                break

        length = self.ser.read(1)[0]
        msg_type = self.ser.read(1)[0]
        data = self.ser.read(length)
        etx = self.ser.read(1)[0]
        bcc = self.ser.read(1)[0]

        body = bytes([length, msg_type]) + data + bytes([etx])

        calc_bcc = 0
        for x in body:
            calc_bcc ^= x

        if etx != self.ETX:
            raise RuntimeError("Invalid ETX in response")

        if bcc != calc_bcc:
            self.ser.write(bytes([self.NAK]))
            raise RuntimeError("BCC checksum failed")

        self.ser.write(bytes([self.ACK]))
        return msg_type, data.decode("ascii", errors="replace")

    def write(self, command):
        frame = self._make_frame(self.TYPE_COMMAND, command)
        self.ser.write(frame)

        ack = self.ser.read(1)
        if not ack or ack[0] != self.ACK:
            raise RuntimeError(f"No ACK after command: {command}")

        msg_type, _ = self._read_frame()

        if msg_type == self.TYPE_FORMAT_ERROR:
            raise RuntimeError(f"Laser rejected command: {command}")

        return True

    def query(self, command):
        frame = self._make_frame(self.TYPE_QUERY, command)
        self.ser.write(frame)

        ack = self.ser.read(1)
        if not ack or ack[0] != self.ACK:
            raise RuntimeError(f"No ACK after query: {command}")

        msg_type, data = self._read_frame()

        if msg_type == self.TYPE_FORMAT_ERROR:
            raise RuntimeError(f"Laser rejected query: {command}")

        if msg_type != self.TYPE_RESPONSE:
            raise RuntimeError(f"Unexpected response type: {msg_type}")

        return data.strip()

    # -------------------------
    # Laser commands
    # -------------------------

    def idn(self):
        return self.query("*IDN?")

    def reset(self):
        self.write("*RST")

    def clear_status(self):
        self.write("*CLS")

    def set_cw_mode(self):
        self.write("MCW")

    def set_sweep_mode(self):
        self.write("MSWP")

    
    def wait_until_wavelength_settled(
        self,
        target_nm=None,
        tolerance_nm=0.001,
        timeout_s=30,
        poll_interval_s=0.1,
    ):
        """
        Wait until the laser has finished tuning.

        Uses MOVE? first:
            0 = wavelength setting terminated
            1 = wavelength setting currently in progress

        Then optionally checks OUTW? against the target wavelength.

        tolerance_nm=0.001 means 1 pm.
        """
        start_time = time.time()

        while True:
            moving = int(float(self.query("MOVE?")))

            if moving == 0:
                if target_nm is None:
                    return True

                current_nm = self.get_wavelength_nm()

                if abs(current_nm - target_nm) <= tolerance_nm:
                    return True

            if time.time() - start_time > timeout_s:
                current_nm = self.get_wavelength_nm()
                raise TimeoutError(
                    f"Laser wavelength did not settle within {timeout_s} s. "
                    f"Target={target_nm:.6f} nm, current={current_nm:.6f} nm"
                )

            time.sleep(poll_interval_s)
            
    def set_wavelength_nm(self, wavelength_nm, wait=True, timeout_s=30, poll_interval_s=0.1):
        if not 1500 <= wavelength_nm <= 1580:
            raise ValueError("Wavelength must be between 1500 and 1580 nm.")

        self.set_cw_mode()
        self.write(f"WCNT {wavelength_nm:.3f}NM")

        if wait:
            self.wait_until_wavelength_settled(
                target_nm=wavelength_nm,
                timeout_s=timeout_s,
                poll_interval_s=poll_interval_s,
            )

    def get_wavelength_setpoint_nm(self):
        return float(self.query("WCNT?")) * 1e9
    
    def get_min_wavelength_nm(self):
        return 1500.0
        # return float(self.query("WMIN?")) * 1e9


    def get_max_wavelength_nm(self):
        return 1580.0

        # return float(self.query("WMAX?")) * 1e9

    def get_wavelength_nm(self):
        return float(self.query("OUTW?")) * 1e9

    def set_power_dbm(self, power_dbm):
        self.write("POWU DBM")
        self.write(f"POW {power_dbm:.2f}DBM")
        
    def set_power_mw(self, power_dbm):
        self.write("POWU MW")
        self.write(f"POW {power_dbm:.2f}MW")

    def get_power(self):
        return float(self.query("POW?"))
    
    def get_min_power_dbm(self):
        
        return float(self.query("PMIN?"))

    
    def get_max_power(self):
        return float(self.query("POWM?"))

    def laser_on(self):
        self.write("OUTP ON")

    def laser_off(self):
        self.write("OUTP OFF")

    def get_laser_output_state(self):
        return bool(int(float(self.query("OUTP?"))))

    def get_output_condition(self):
        value = int(float(self.query("OUTC?")))
        return {
            "raw": value,
            "key_on": bool(value & 1),
            "fibre_connected": bool(value & 2),
            "interlock_short": bool(value & 4),
            "ready": value == 7,
        }

    def get_heatup_percent(self):
        return float(self.query("TEMP?"))

    def wait_for_heatup(self, poll_interval=10):
        while self.get_heatup_percent() < 100:
            time.sleep(poll_interval)

    def configure_sweep_nm(self, start_nm, stop_nm, step_nm, dwell_s=1.0):
        self.set_sweep_mode()
        self.write(f"WSTA {start_nm:.3f}NM")
        self.write(f"WSTO {stop_nm:.3f}NM")
        self.write(f"WSTP {step_nm:.3f}NM")
        self.write(f"DWEL {dwell_s:.3f}S")

    def single_sweep(self):
        self.write("SNGL")

    def repeat_sweep(self):
        self.write("RPT")

    def pause_sweep(self):
        self.write("PAUS")

    def continue_sweep(self):
        self.write("CONT")