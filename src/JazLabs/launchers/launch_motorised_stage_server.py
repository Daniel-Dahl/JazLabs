"""Run one named motor server; this is the only launcher that opens hardware."""
import argparse
from copy import deepcopy
import json
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run one configured JazLabs motor server.")
    parser.add_argument("--config", default="motorised_mounts")
    parser.add_argument("--name", "--motor", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--serial-port", default=None)
    parser.add_argument("--driver-options", type=json.loads, default=None)
    parser.add_argument("--limits", type=json.loads, default=None)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    motor = deepcopy(get_named_config(config, "MOTOR_SERVERS", args.name))
    motor = merge_overrides(motor, {"host": args.host, "command_port": args.command_port,
                                    "limits": args.limits})
    if args.driver_options is not None and not isinstance(args.driver_options, dict):
        parser.error("--driver-options must be a JSON object")
    if not isinstance(motor.get("limits", {}), dict):
        parser.error("--limits must be a JSON object")
    options = dict(motor.get("stage_kwargs", {}))
    options.update(args.driver_options or {})
    if args.serial_port is not None:
        options["port"] = args.serial_port
    if motor["stage_type"] != "simulation" and not str(options.get("port") or "").strip():
        parser.error("Set stage_kwargs.port in the config or supply --serial-port")
    mp.freeze_support()
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer
    server = MotorisedStageZMQServer(
        host=motor.get("host", "127.0.0.1"), command_port=motor["command_port"],
        stage_type=motor["stage_type"], stage_kwargs=options, limits=motor.get("limits", {}),
    )
    print(f"Launching motor server {motor['name']!r} ({motor['stage_type']}).")
    print(f"Command endpoint: tcp://{server.host}:{server.command_port}")
    if motor["stage_type"] != "simulation":
        print(f"Serial port: {options['port']}")
    try:
        server.run_forever()
    except KeyboardInterrupt:
        print("Motor server stopped.")


if __name__ == "__main__":
    main()
