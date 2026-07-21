import importlib
import math
import multiprocessing as mp
import time
import traceback

import zmq


LASER_DRIVERS = {
    "Anritsu MG963x": "JazLabs.hardware.Lasers.Anritsu.AnritsuMG963xLaser",
    "JDS Tunable": "JazLabs.hardware.Lasers.JDS.JDSUniphaseTunableLaser",
    "Santec Swept": "JazLabs.hardware.Lasers.Santec.SantecSweeptLaser",
    "FYLA Horizon": "JazLabs.hardware.Lasers.FYLA.FYLAHorizonLaser",
}


class LaserZMQServer:
    """Own one laser connection and expose a small, explicit ZMQ API."""

    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        LaserType="Anritsu MG963x",
        LaserKwargs=None,
        PollTimeoutMS=100,
        LaserFactory=None,
    ):
        self.host = str(host)
        self.command_port = int(command_port)
        self.LaserType = str(LaserType)
        self.LaserKwargs = dict(LaserKwargs or {})
        self.PollTimeoutMS = int(PollTimeoutMS)
        self.LaserFactory = LaserFactory
        self.Process = None
        # Use mW as the initial display/setpoint unit.  Drivers that expose
        # their actual hardware units may still report those in get_status().
        self.power_units = "mW"

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Laser server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Laser server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.host}:{self.command_port}")
            socket.send_json({"cmd": "shutdown", "client_id": "server_controller"})
            socket.recv_json()
            socket.close(0)
            context.term()
        except Exception:
            pass

        if self.Process is not None:
            self.Process.join(timeout=2)
            if self.Process.is_alive():
                self.Process.terminate()
                self.Process.join(timeout=1)
            self.Process = None

    def _create_laser(self):
        if self.LaserFactory is not None:
            return self.LaserFactory(**self.LaserKwargs)

        module_name = LASER_DRIVERS.get(self.LaserType)
        if module_name is None:
            available = ", ".join(sorted(LASER_DRIVERS))
            raise ValueError(
                f"Unknown LaserType {self.LaserType!r}. Available types: {available}"
            )

        driver_module = importlib.import_module(module_name)
        return driver_module.LaserObject(**self.LaserKwargs)

    def _capabilities(self, laser):
        return {
            "wavelength": all(
                hasattr(laser, name)
                for name in ("get_wavelength_nm", "set_wavelength_nm")
            ),
            "power_dbm": hasattr(laser, "set_power_dbm"),
            "power_mw": hasattr(laser, "set_power_mw"),
            "power_readback": hasattr(laser, "get_power"),
            "output_control": all(
                hasattr(laser, name)
                for name in ("laser_on", "laser_off", "get_laser_output_state")
            ),
            "reset": hasattr(laser, "reset"),
        }

    @staticmethod
    def _read_optional_number(laser, method_name):
        """Read a numeric driver property without making status fail wholesale."""
        method = getattr(laser, method_name, None)
        if method is None:
            return None
        value = method()
        return None if value is None else float(value)

    def _read_status(self, laser):
        status = {
            "laser_type": self.LaserType,
            "power_units": self.power_units,
            "wavelength_nm": None,
            "power": None,
            "output_enabled": None,
            "errors": {},
        }

        status_queries = (
            ("wavelength_nm", "get_wavelength_nm"),
            ("power", "get_power"),
            ("output_enabled", "get_laser_output_state"),
        )
        for field_name, method_name in status_queries:
            method = getattr(laser, method_name, None)
            if method is None:
                status["errors"][field_name] = "Not supported by this laser driver"
                continue
            try:
                value = method()
                if field_name == "output_enabled":
                    value = None if value is None else bool(value)
                elif value is not None:
                    value = float(value)
                status[field_name] = value
            except Exception as exc:
                status["errors"][field_name] = f"{type(exc).__name__}: {exc}"

        get_power_units = getattr(laser, "get_power_units", None)
        if get_power_units is not None:
            try:
                self.power_units = str(get_power_units())
                status["power_units"] = self.power_units
            except Exception as exc:
                status["errors"]["power_units"] = f"{type(exc).__name__}: {exc}"

        return status

    def _read_limits(self, laser):
        limits = {
            "min_wavelength_nm": None,
            "max_wavelength_nm": None,
            "min_power_dbm": None,
            "max_power": None,
            "errors": {},
        }
        limit_queries = (
            ("min_wavelength_nm", "get_min_wavelength_nm"),
            ("max_wavelength_nm", "get_max_wavelength_nm"),
            ("min_power_dbm", "get_min_power_dbm"),
            ("max_power", "get_max_power"),
        )
        for field_name, method_name in limit_queries:
            method = getattr(laser, method_name, None)
            if method is None:
                continue
            try:
                value = method()
                limits[field_name] = None if value is None else float(value)
            except (NotImplementedError, AttributeError) as exc:
                limits["errors"][field_name] = str(exc)
            except Exception as exc:
                limits["errors"][field_name] = f"{type(exc).__name__}: {exc}"
        return limits

    def handle_command(self, laser, msg):
        cmd = msg.get("cmd")

        if cmd == "get_properties":
            result = {
                "laser_type": self.LaserType,
                "command_port": self.command_port,
                "capabilities": self._capabilities(laser),
            }
        elif cmd == "get_status":
            result = self._read_status(laser)
        elif cmd == "get_limits":
            result = self._read_limits(laser)
        elif cmd == "get_wavelength_nm":
            result = self._read_optional_number(laser, "get_wavelength_nm")
            if result is None:
                raise NotImplementedError("This laser does not expose wavelength readback")
        elif cmd == "set_wavelength_nm":
            wavelength_nm = float(msg["wavelength_nm"])
            if not math.isfinite(wavelength_nm):
                raise ValueError("Wavelength must be finite")
            result = laser.set_wavelength_nm(
                wavelength_nm,
                wait=bool(msg.get("wait", True)),
                timeout_s=float(msg.get("timeout_s", 30.0)),
                poll_interval_s=float(msg.get("poll_interval_s", 0.1)),
            )
            result = None if result is None else float(result)
        elif cmd == "get_power":
            result = self._read_optional_number(laser, "get_power")
            if result is None:
                raise NotImplementedError("This laser does not expose power readback")
        elif cmd == "set_power_dbm":
            power_dbm = float(msg["power_dbm"])
            if not math.isfinite(power_dbm):
                raise ValueError("Power must be finite")
            result = laser.set_power_dbm(power_dbm)
            self.power_units = "dBm"
            result = None if result is None else float(result)
        elif cmd == "set_power_mw":
            power_mw = float(msg["power_mw"])
            if not math.isfinite(power_mw) or power_mw < 0:
                raise ValueError("Power in mW must be finite and non-negative")
            result = laser.set_power_mw(power_mw)
            self.power_units = "mW"
            result = None if result is None else float(result)
        elif cmd == "get_laser_output_state":
            result = laser.get_laser_output_state()
            result = None if result is None else bool(result)
        elif cmd == "laser_on":
            result = laser.laser_on()
        elif cmd == "laser_off":
            result = laser.laser_off()
        elif cmd == "reset":
            result = laser.reset()
        elif cmd == "shutdown":
            return None, False
        else:
            raise ValueError(f"Unknown command: {cmd}")

        return result, True

    def run_forever(self):
        laser = None
        context = None
        command_socket = None
        try:
            laser = self._create_laser()
            get_power_units = getattr(laser, "get_power_units", None)
            if get_power_units is not None:
                try:
                    self.power_units = str(get_power_units())
                except Exception:
                    pass

            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.setsockopt(zmq.LINGER, 0)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")
            poller = zmq.Poller()
            poller.register(command_socket, zmq.POLLIN)

            print("Laser ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Laser type: {self.LaserType}")

            running = True
            while running:
                events = dict(poller.poll(self.PollTimeoutMS))
                if command_socket not in events:
                    continue

                msg = {}
                try:
                    msg = command_socket.recv_json()
                    result, running = self.handle_command(laser, msg)
                    reply = {
                        "ok": True,
                        "result": result,
                        "client_id": msg.get("client_id", "unknown_client"),
                    }
                except Exception as exc:
                    reply = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "client_id": msg.get("client_id", "unknown_client"),
                    }
                command_socket.send_json(reply)
        finally:
            print("Closing laser ZMQ server...")
            try:
                if laser is not None:
                    close = getattr(laser, "close", None) or getattr(laser, "Close", None)
                    if close is not None:
                        close()
            except Exception:
                print(traceback.format_exc())
            if command_socket is not None:
                command_socket.close(0)
            if context is not None:
                context.term()
            print("Laser ZMQ server closed.")


if __name__ == "__main__":
    mp.freeze_support()
    LaserZMQServer().run_forever()
