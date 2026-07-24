#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run one configured JazLabs JDS optical switch server."
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--switch", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument(
        "--switch-type",
        choices=("JDS_SC", "JDS_Pol"),
        default=None,
    )
    parser.add_argument("--serial-port", default=None)
    parser.add_argument("--serial-timeout", type=float, default=None)
    parser.add_argument(
        "--rtscts",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--dsrdtr",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser


def build_switch_kwargs(switch):
    return {
        "port": switch["serial_port"],
        "timeout": switch["serial_timeout"],
        "rtscts": switch["rtscts"],
        "dsrdtr": switch["dsrdtr"],
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    switch_config = get_named_config(
        config,
        "OPTICAL_SWITCH_SERVERS",
        args.name,
    )
    switch = merge_overrides(
        switch_config,
        {
            "host": args.host,
            "command_port": args.command_port,
            "switch_type": args.switch_type,
            "serial_port": args.serial_port,
            "serial_timeout": args.serial_timeout,
            "rtscts": args.rtscts,
            "dsrdtr": args.dsrdtr,
        },
    )
    switch.setdefault("host", config.get("OPTICAL_SWITCH_HOST", "127.0.0.1"))
    switch.setdefault("serial_timeout", 2.0)
    switch.setdefault("rtscts", True)
    switch.setdefault("dsrdtr", True)

    mp.freeze_support()

    from JazLabs.hardware.OpticalSwitch.OpticalSwitch_Server import (
        OpticalSwitchZMQServer,
    )

    server = OpticalSwitchZMQServer(
        host=switch["host"],
        command_port=switch["command_port"],
        switch_type=switch["switch_type"],
        switch_kwargs=build_switch_kwargs(switch),
    )

    print(f"Launching optical switch server {switch['name']!r}.")
    print(f"Host: {switch['host']}")
    print(f"Command port: {switch['command_port']}")
    print(f"Switch type: {switch['switch_type']}")
    print(f"Serial port: {switch['serial_port']}")
    print(f"Serial timeout: {switch['serial_timeout']} s")
    print(f"RTS/CTS handshaking: {switch['rtscts']}")
    print(f"DSR/DTR handshaking: {switch['dsrdtr']}")
    server.run_forever()


if __name__ == "__main__":
    main()
