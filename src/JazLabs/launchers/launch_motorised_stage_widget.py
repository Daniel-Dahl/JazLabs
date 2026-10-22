"""Launch a motor server and GUI, or connect the GUI to an existing server."""
from copy import deepcopy
import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(description="JazLabs motor alignment and axis console")
    parser.add_argument("--config", help="Named JazLabs launcher config or a Python config file")
    parser.add_argument("--name", help="MOTOR_SERVERS entry in --config")
    parser.add_argument("--stage", default=None, choices=("simulation", "KST201Serial", "KDC101Serial", "BSC203Serial", "UMC2Serial", "CONEXAGPSerial", "CONEXAGAPSerial"))
    parser.add_argument("--port", help="Hardware serial port (e.g. COM5)")
    parser.add_argument("--driver-options", type=json.loads, default=None, help="JSON keyword arguments for the stage driver")
    parser.add_argument("--limits", type=json.loads, default=None, help='Travel limits in displayed units, e.g. {"X": [0, 10]}')
    parser.add_argument("--demo-axes", type=int, choices=(1, 2, 3), default=None)
    parser.add_argument("--demo-mirror", action="store_true")
    parser.add_argument("--layout", choices=("alignment", "console"), default="alignment")
    parser.add_argument("--connect", metavar="HOST", help="Connect the GUI to a motion server")
    parser.add_argument("--serve", action="store_true", help="Run a motion server without a GUI")
    parser.add_argument("--bind", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    args = parser.parse_args(argv)
    if args.serve and args.connect:
        parser.error("Choose --serve or --connect")
    if bool(args.config) != bool(args.name):
        parser.error("Use --config and --name together")
    if args.driver_options is not None and not isinstance(args.driver_options, dict):
        parser.error("--driver-options must be a JSON object")
    if args.limits is not None and not isinstance(args.limits, dict):
        parser.error("--limits must be a JSON object")
    configured = {}
    if args.config:
        from JazLabs.launchers.config import get_named_config, load_config
        configured = deepcopy(get_named_config(load_config(args.config), "MOTOR_SERVERS", args.name))
    stage_type = args.stage or configured.get("stage_type", "simulation")
    options = dict(configured.get("stage_kwargs", {}))
    options.update(args.driver_options or {})
    limits = args.limits if args.limits is not None else configured.get("limits", {})
    command_port = args.command_port if args.command_port is not None else configured.get("command_port")
    bind_host = args.bind or configured.get("host", "127.0.0.1")
    if stage_type == "simulation":
        if not configured and not args.driver_options:
            options = {"axes": 2, "absolute_sensor": False}
        if args.demo_axes is not None:
            options["axes"] = args.demo_axes
        if args.demo_mirror:
            options.update(axes=2, absolute_sensor=True)
    elif not args.connect:
        if args.port:
            options["port"] = args.port
        if not str(options.get("port") or "").strip():
            parser.error("Set the mount's stage_kwargs.port in the config or supply --port")
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer
    if args.serve:
        MotorisedStageZMQServer(bind_host, command_port or 50931, stage_type, options, limits).run_forever()
        return
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Widget import MotorisedStageControlWindow
    server = None
    if args.connect:
        client = MotorisedStageClient(args.connect, command_port or 50931)
    else:
        # Even on the hardware computer the GUI communicates through a client.
        # Port 0 asks the server to choose an unused localhost port for this run.
        server = MotorisedStageZMQServer("127.0.0.1", command_port or 0,
                                        stage_type, options, limits)
        server.start()
        client = MotorisedStageClient("127.0.0.1", server.command_port)
    try:
        MotorisedStageControlWindow(client, args.layout).run()
    finally:
        client.close()
        if server:
            server.stop()


if __name__ == "__main__":
    main()
