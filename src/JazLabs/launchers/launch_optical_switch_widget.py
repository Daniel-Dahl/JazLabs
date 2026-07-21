#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(
        description="Open configured JazLabs optical switch control widgets."
    )
    parser.add_argument("--config", default="default_lab")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", "--switch", dest="name")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--refresh-ms", type=int, default=1000)
    return parser


def selected_switches(config, name=None, include_all=False):
    if include_all:
        return [
            dict(switch)
            for switch in config.get("OPTICAL_SWITCH_SERVERS", [])
            if switch.get("enabled", True)
        ]
    return [get_named_config(config, "OPTICAL_SWITCH_SERVERS", name)]


def start_optical_switch_widgets(
    config_name="default_lab",
    name=None,
    include_all=False,
    timeout_ms=5000,
    refresh_ms=1000,
):
    config = load_config(config_name)
    default_host = config.get("OPTICAL_SWITCH_HOST", "127.0.0.1")
    switches = selected_switches(config, name=name, include_all=include_all)
    processes = []

    from JazLabs.hardware.OpticalSwitch.OpticalSwitch_widget import (
        launch_optical_switch_widget_process,
    )

    for switch in switches:
        switch_host = switch.get("host", default_host)
        process = launch_optical_switch_widget_process(
            host=switch_host,
            command_port=switch["command_port"],
            timeout_ms=timeout_ms,
            refresh_ms=refresh_ms,
        )
        processes.append((f"{switch['name']} widget", process))

    return processes


def wait_for_processes(processes):
    try:
        while any(process.is_alive() for _, process in processes):
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping optical switch widgets.")
    finally:
        for _, process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)


def main(argv=None):
    args = build_parser().parse_args(argv)
    mp.freeze_support()
    processes = start_optical_switch_widgets(
        config_name=args.config,
        name=args.name,
        include_all=args.all,
        timeout_ms=args.timeout_ms,
        refresh_ms=args.refresh_ms,
    )
    if not processes:
        raise SystemExit("No enabled optical switch widgets matched the request.")
    wait_for_processes(processes)


if __name__ == "__main__":
    main()
