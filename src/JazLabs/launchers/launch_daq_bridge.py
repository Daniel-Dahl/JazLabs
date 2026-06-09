#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run a local bridge for a remote JazLabs DAQ server."
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--daq", dest="name", required=True)
    parser.add_argument("--remote-host", required=True)
    parser.add_argument("--local-host", default=None)
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--local-voltage-pub-port", type=int, default=None)
    parser.add_argument("--remote-command-port", type=int, default=None)
    parser.add_argument("--remote-voltage-pub-port", type=int, default=None)
    parser.add_argument("--voltage-topic", default=None)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--poll-sleep", type=float, default=0.0)
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Ask an existing DAQ bridge on the local port to stop before starting.",
    )
    return parser


def request_existing_bridge_shutdown(local_host, local_command_port, timeout_ms):
    import zmq

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, int(timeout_ms))
    socket.setsockopt(zmq.SNDTIMEO, int(timeout_ms))

    try:
        socket.connect(f"tcp://{local_host}:{local_command_port}")
        socket.send_json({"cmd": "shutdown_bridge", "client_id": "bridge_launcher"})
        reply = socket.recv_json()
        return bool(reply.get("ok", False)), reply
    except Exception as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            socket.close(0)
        finally:
            context.term()


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    daq_config = get_named_config(config, "DAQ_SERVERS", args.name)
    daq = merge_overrides(
        daq_config,
        {
            "voltage_topic": args.voltage_topic,
        },
    )

    local_host = args.local_host or daq.get("local_host", "127.0.0.1")
    local_command_port = args.local_command_port or daq["command_port"]
    local_voltage_pub_port = args.local_voltage_pub_port or daq["voltage_pub_port"]
    remote_command_port = args.remote_command_port or daq["command_port"]
    remote_voltage_pub_port = args.remote_voltage_pub_port or daq["voltage_pub_port"]
    voltage_topic = daq.get("voltage_topic", "daq.voltages")

    mp.freeze_support()

    if args.restart:
        stopped, reply = request_existing_bridge_shutdown(
            local_host,
            local_command_port,
            args.timeout_ms,
        )
        if stopped:
            print(
                "Stopped existing DAQ bridge on "
                f"tcp://{local_host}:{local_command_port}."
            )
            time.sleep(0.5)
        else:
            print(
                "No existing DAQ bridge was stopped on "
                f"tcp://{local_host}:{local_command_port}: "
                f"{reply.get('error', reply)}"
            )

    from JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Server_Bridge import (
        DAQZMQBridgeServer,
    )

    bridge = DAQZMQBridgeServer(
        local_host=local_host,
        local_command_port=local_command_port,
        local_voltage_pub_port=local_voltage_pub_port,
        remote_host=args.remote_host,
        remote_command_port=remote_command_port,
        remote_voltage_pub_port=remote_voltage_pub_port,
        voltage_topic=voltage_topic,
        timeout_ms=args.timeout_ms,
        PollSleep=args.poll_sleep,
    )

    print("Launching DAQ bridge.")
    print(f"Local host: {local_host}")
    print(f"Local command port: {local_command_port}")
    print(f"Local voltage PUB port: {local_voltage_pub_port}")
    print(f"Remote host: {args.remote_host}")
    print(f"Remote command port: {remote_command_port}")
    print(f"Remote voltage PUB port: {remote_voltage_pub_port}")
    print(f"Voltage topic: {voltage_topic}")
    try:
        bridge.run_forever()
    except Exception as exc:
        if "Address already in use" in str(exc):
            raise SystemExit(
                "Could not start DAQ bridge because the local endpoint is already "
                f"in use: tcp://{local_host}:{local_command_port}. "
                "If this is an old bridge, rerun with --restart. If it is another "
                "process, stop that process or choose --local-command-port and "
                "--local-voltage-pub-port overrides."
            ) from exc
        raise


if __name__ == "__main__":
    main()
