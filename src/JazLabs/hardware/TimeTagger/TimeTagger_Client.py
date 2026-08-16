import uuid

import numpy as np
import zmq

from JazLabs.hardware.TimeTagger.TimeTagger_Types import CoincidenceResults


class TimeTaggerClient:
    """Client for either a Time Tagger server or a local bridge server."""

    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        timeout_ms=120000,
        client_id=None,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id or str(uuid.uuid4())
        self.context = zmq.Context()
        self.socket = None
        self._connect_command_socket()
        self.properties = self.GetProperties()

    def _connect_command_socket(self):
        if self.socket is not None:
            self.socket.close(0)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.command_port}")

    def ResetCommandSocket(self):
        self._connect_command_socket()

    def SendCommand(self, message, timeout_ms=None):
        message = dict(message)
        message["client_id"] = self.client_id
        command_timeout_ms = self.timeout_ms if timeout_ms is None else int(timeout_ms)
        self.socket.setsockopt(zmq.RCVTIMEO, command_timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, command_timeout_ms)

        try:
            self.socket.send_json(message)
            reply = self.socket.recv_json()
        except zmq.ZMQError:
            self.ResetCommandSocket()
            raise
        finally:
            if self.socket is not None:
                self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
                self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)

        if not reply.get("ok", False):
            error = reply.get("error", "Unknown Time Tagger server error")
            traceback_text = reply.get("traceback", "")
            if traceback_text:
                error += "\n" + traceback_text
            raise RuntimeError(error)
        return reply.get("result")

    def _measurement_timeout_ms(self, counting_time):
        return max(self.timeout_ms, int(float(counting_time) * 1000) + 5000)

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def SetTriggerLevel(self, channel, voltage):
        return float(
            self.SendCommand(
                {
                    "cmd": "set_trigger_level",
                    "channel": int(channel),
                    "voltage": float(voltage),
                }
            )
        )

    def GetTriggerLevel(self, channel):
        return float(
            self.SendCommand({"cmd": "get_trigger_level", "channel": int(channel)})
        )

    def SetInputDelay(self, channel, delay_ps):
        return int(
            self.SendCommand(
                {
                    "cmd": "set_input_delay",
                    "channel": int(channel),
                    "delay_ps": int(delay_ps),
                }
            )
        )

    def GetInputDelay(self, channel):
        return int(
            self.SendCommand({"cmd": "get_input_delay", "channel": int(channel)})
        )

    def MeasureCountrate(self, channels, counting_time, clear=True):
        if not isinstance(channels, (list, tuple, np.ndarray)):
            channels = [channels]
        values = self.SendCommand(
            {
                "cmd": "measure_countrate",
                "channels": [int(channel) for channel in channels],
                "counting_time": float(counting_time),
                "clear": bool(clear),
            },
            timeout_ms=self._measurement_timeout_ms(counting_time),
        )
        return np.asarray(values)

    def MeasureCounts(self, channels, bin_width, bin_count, counting_time, clear=True):
        if not isinstance(channels, (list, tuple, np.ndarray)):
            channels = [channels]
        result = self.SendCommand(
            {
                "cmd": "measure_counts",
                "channels": [int(channel) for channel in channels],
                "bin_width": int(bin_width),
                "bin_count": int(bin_count),
                "counting_time": float(counting_time),
                "clear": bool(clear),
            },
            timeout_ms=self._measurement_timeout_ms(counting_time),
        )
        return np.asarray(result["time_bins"]), np.asarray(result["counts"])

    def MeasureCorrelation(self, channels, bin_width, bin_count, counting_time):
        result = self.SendCommand(
            {
                "cmd": "measure_correlation",
                "channels": [int(channel) for channel in channels],
                "bin_width": int(bin_width),
                "bin_count": int(bin_count),
                "counting_time": float(counting_time),
            },
            timeout_ms=self._measurement_timeout_ms(counting_time),
        )
        return (
            np.asarray(result["time_bins"]),
            np.asarray(result["counts"]),
            np.asarray(result["normalised_counts"]),
        )

    def MeasureCoincidences(self, channels, coincidence_window, counting_time):
        result = self.SendCommand(
            {
                "cmd": "measure_coincidences",
                "channels": [int(channel) for channel in channels],
                "coincidence_window": int(coincidence_window),
                "counting_time": float(counting_time),
            },
            timeout_ms=self._measurement_timeout_ms(counting_time),
        )
        return CoincidenceResults.from_dict(result)

    def MeasureCoincidencesAndCorrelation(
        self,
        channels,
        coincidence_window,
        bin_count,
        counting_time,
    ):
        result = self.SendCommand(
            {
                "cmd": "measure_coincidences_and_correlation",
                "channels": [int(channel) for channel in channels],
                "coincidence_window": int(coincidence_window),
                "bin_width": int(coincidence_window),
                "bin_count": int(bin_count),
                "counting_time": float(counting_time),
            },
            timeout_ms=self._measurement_timeout_ms(counting_time),
        )
        return (
            CoincidenceResults.from_dict(result["coincidences"]),
            np.asarray(result["time_bins"]),
            np.asarray(result["correlation_counts"]),
            np.asarray(result["normalised_correlation_counts"]),
        )

    # Vendor-style aliases ease migration of existing scripts.
    def setTriggerLevel(self, channel, voltage):
        return self.SetTriggerLevel(channel, voltage)

    def getTriggerLevel(self, channel):
        return self.GetTriggerLevel(channel)

    def setInputDelay(self, channel, delay):
        return self.SetInputDelay(channel, delay)

    def getInputDelay(self, channel):
        return self.GetInputDelay(channel)

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    def close(self):
        if self.socket is not None:
            self.socket.close(0)
            self.socket = None
        if self.context is not None:
            self.context.term()
            self.context = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

