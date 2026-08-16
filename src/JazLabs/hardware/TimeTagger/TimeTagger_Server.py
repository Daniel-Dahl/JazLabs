import multiprocessing as mp
import traceback

import numpy as np
import zmq

from JazLabs.hardware.TimeTagger.TimeTagger_Types import CoincidenceResults


class TimeTaggerZMQServer:
    """Own one physical Time Tagger and expose its measurements over ZMQ."""

    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        serial=None,
        create_kwargs=None,
        poll_timeout_ms=100,
        time_tagger_module=None,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.serial = serial
        self.create_kwargs = dict(create_kwargs or {})
        self.poll_timeout_ms = int(poll_timeout_ms)
        self.time_tagger_module = time_tagger_module
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Time Tagger server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Time Tagger server process started with PID {self.Process.pid}")

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

    def _load_time_tagger_module(self):
        if self.time_tagger_module is not None:
            return self.time_tagger_module

        try:
            import TimeTagger
        except ImportError as exc:
            raise RuntimeError(
                "The Swabian Instruments TimeTagger package is required on the "
                "machine running the Time Tagger server."
            ) from exc

        return TimeTagger

    def _create_time_tagger(self, time_tagger_module):
        create_kwargs = dict(self.create_kwargs)
        if self.serial is not None:
            create_kwargs.setdefault("serial", self.serial)
        return time_tagger_module.createTimeTagger(**create_kwargs)

    def _get_properties(self, tagger):
        serial = self.serial
        if hasattr(tagger, "getSerial"):
            serial = tagger.getSerial()

        model = None
        if hasattr(tagger, "getModel"):
            model = tagger.getModel()

        return {
            "role": "time_tagger_server",
            "command_port": self.command_port,
            "serial": serial,
            "model": model,
            "server_alive": True,
        }

    def _measure_countrate(self, time_tagger_module, tagger, message):
        channels = [int(channel) for channel in message["channels"]]
        counting_time = float(message["counting_time"])
        measurement = time_tagger_module.Countrate(tagger=tagger, channels=channels)
        if message.get("clear", True):
            measurement.clear()
        measurement.startFor(int(counting_time * 1e12))
        measurement.waitUntilFinished()
        return np.asarray(measurement.getData()).tolist()

    def _measure_counts(self, time_tagger_module, tagger, message):
        channels = [int(channel) for channel in message["channels"]]
        bin_width = int(message["bin_width"])
        bin_count = int(message["bin_count"])
        counting_time = float(message["counting_time"])
        measurement = time_tagger_module.Counter(
            tagger=tagger,
            channels=channels,
            binwidth=bin_width,
            n_values=bin_count,
        )
        if message.get("clear", True):
            measurement.clear()
        measurement.startFor(int(counting_time * 1e12))
        measurement.waitUntilFinished()
        return {
            "time_bins": np.asarray(measurement.getIndex()).tolist(),
            "counts": np.asarray(measurement.getData()).tolist(),
        }

    def _measure_correlation(self, time_tagger_module, tagger, message):
        channels = [int(channel) for channel in message["channels"]]
        if len(channels) != 2:
            raise ValueError("A correlation measurement requires exactly two channels.")

        measurement = time_tagger_module.Correlation(
            tagger=tagger,
            channel_1=channels[0],
            channel_2=channels[1],
            binwidth=int(message["bin_width"]),
            n_bins=int(message["bin_count"]),
        )
        measurement.startFor(int(float(message["counting_time"]) * 1e12))
        measurement.waitUntilFinished()
        return {
            "time_bins": np.asarray(measurement.getIndex()).tolist(),
            "counts": np.asarray(measurement.getData()).tolist(),
            "normalised_counts": np.asarray(
                measurement.getDataNormalized()
            ).tolist(),
        }

    def _calculate_coincidence_result(
        self,
        channel_counts,
        counting_time,
        coincidence_window,
    ):
        channel1_counts, channel2_counts, coincidences = [
            int(value) for value in channel_counts
        ]
        channel1_rate = channel1_counts / counting_time
        channel2_rate = channel2_counts / counting_time
        coincidence_rate = coincidences / counting_time

        accidental_rate = -1.0
        contrast_car = -1.0
        if channel1_counts != 0 and channel2_counts != 0:
            accidental_rate = (
                channel1_rate
                * channel2_rate
                * 2
                * (coincidence_window * 1e-12)
            )
            if accidental_rate != 0:
                contrast_car = coincidence_rate / accidental_rate

        return CoincidenceResults(
            channel1_counts=channel1_counts,
            channel2_counts=channel2_counts,
            coincidences=coincidences,
            channel1_rate=channel1_rate,
            channel2_rate=channel2_rate,
            coincidence_rate=coincidence_rate,
            accidental_rate=accidental_rate,
            contrast_CAR=contrast_car,
        )

    def _create_coincidence_measurements(self, time_tagger_module, tagger, message):
        channels = [int(channel) for channel in message["channels"]]
        if len(channels) != 2:
            raise ValueError("A coincidence measurement requires exactly two channels.")

        coincidence_window = int(message["coincidence_window"])
        coincidence_measurement = time_tagger_module.Coincidence(
            tagger=tagger,
            channels=channels,
            coincidenceWindow=coincidence_window,
            timestamp=time_tagger_module.CoincidenceTimestamp.Last,
        )
        coincidence_channel = coincidence_measurement.getChannel()
        countrate_measurement = time_tagger_module.Countrate(
            tagger=tagger,
            channels=[*channels, coincidence_channel],
        )
        return channels, coincidence_window, countrate_measurement

    def _measure_coincidences(self, time_tagger_module, tagger, message):
        _, coincidence_window, measurement = self._create_coincidence_measurements(
            time_tagger_module,
            tagger,
            message,
        )
        counting_time = float(message["counting_time"])
        measurement.startFor(int(counting_time * 1e12))
        measurement.waitUntilFinished()
        result = self._calculate_coincidence_result(
            measurement.getCountsTotal(),
            counting_time,
            coincidence_window,
        )
        return result.to_dict()

    def _measure_coincidences_and_correlation(
        self,
        time_tagger_module,
        tagger,
        message,
    ):
        channels, coincidence_window, countrate = self._create_coincidence_measurements(
            time_tagger_module,
            tagger,
            message,
        )
        correlation = time_tagger_module.Correlation(
            tagger=tagger,
            channel_1=channels[0],
            channel_2=channels[1],
            binwidth=int(message["bin_width"]),
            n_bins=int(message["bin_count"]),
        )

        counting_time = float(message["counting_time"])
        countrate.startFor(int(counting_time * 1e12))
        countrate.waitUntilFinished()
        coincidence_result = self._calculate_coincidence_result(
            countrate.getCountsTotal(),
            counting_time,
            coincidence_window,
        )
        return {
            "coincidences": coincidence_result.to_dict(),
            "time_bins": np.asarray(correlation.getIndex()).tolist(),
            "correlation_counts": np.asarray(correlation.getData()).tolist(),
            "normalised_correlation_counts": np.asarray(
                correlation.getDataNormalized()
            ).tolist(),
        }

    def _handle_command(self, time_tagger_module, tagger, message):
        command = message.get("cmd")

        if command == "get_properties":
            return self._get_properties(tagger), False
        if command == "set_trigger_level":
            channel = int(message["channel"])
            tagger.setTriggerLevel(channel, float(message["voltage"]))
            return float(tagger.getTriggerLevel(channel)), False
        if command == "get_trigger_level":
            return float(tagger.getTriggerLevel(int(message["channel"]))), False
        if command == "set_input_delay":
            channel = int(message["channel"])
            tagger.setInputDelay(channel, int(message["delay_ps"]))
            return int(tagger.getInputDelay(channel)), False
        if command == "get_input_delay":
            return int(tagger.getInputDelay(int(message["channel"]))), False
        if command == "measure_countrate":
            return self._measure_countrate(time_tagger_module, tagger, message), False
        if command == "measure_counts":
            return self._measure_counts(time_tagger_module, tagger, message), False
        if command == "measure_correlation":
            return self._measure_correlation(time_tagger_module, tagger, message), False
        if command == "measure_coincidences":
            return self._measure_coincidences(time_tagger_module, tagger, message), False
        if command == "measure_coincidences_and_correlation":
            return self._measure_coincidences_and_correlation(
                time_tagger_module,
                tagger,
                message,
            ), False
        if command == "shutdown":
            return None, True

        raise ValueError(f"Unknown command: {command}")

    def run_forever(self):
        time_tagger_module = self._load_time_tagger_module()
        tagger = None
        context = None
        command_socket = None

        try:
            tagger = self._create_time_tagger(time_tagger_module)
            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.setsockopt(zmq.LINGER, 0)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            print("Time Tagger ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Serial: {self._get_properties(tagger)['serial']}")

            poller = zmq.Poller()
            poller.register(command_socket, zmq.POLLIN)
            running = True
            while running:
                events = dict(poller.poll(self.poll_timeout_ms))
                if command_socket not in events:
                    continue
                message = command_socket.recv_json()
                client_id = message.get("client_id", "unknown_client")

                try:
                    result, should_shutdown = self._handle_command(
                        time_tagger_module,
                        tagger,
                        message,
                    )
                    reply = {"ok": True, "result": result, "client_id": client_id}
                    running = not should_shutdown
                except Exception as exc:
                    reply = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "client_id": client_id,
                    }

                command_socket.send_json(reply)
        finally:
            print("Closing Time Tagger ZMQ server...")
            if tagger is not None:
                try:
                    time_tagger_module.freeTimeTagger(tagger)
                except Exception:
                    pass
            if command_socket is not None:
                command_socket.close(0)
            if context is not None:
                context.term()
