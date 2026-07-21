#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

from JazLabs.launchers.config import load_config


def tmux(*args, check=True):
    return subprocess.run(["tmux", *args], check=check)


def session_exists(session):
    result = tmux("has-session", "-t", session, check=False)
    return result.returncode == 0


def tmux_window_names(session):
    result = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def python_can_import(python, module_name):
    result = subprocess.run(
        [python, "-c", f"import {module_name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def choose_slm_python():
    python = os.environ.get("JAZLABS_SLM_SERVER_PYTHON", sys.executable)
    if "JAZLABS_SLM_SERVER_PYTHON" in os.environ or python_can_import(python, "pyMilk"):
        return python

    base_python = Path.home() / "miniforge3" / "bin" / "python"
    if base_python.exists() and python_can_import(str(base_python), "pyMilk"):
        return str(base_python)
    return python


def module_command(module, args, python):
    quoted_python = shlex.quote(str(python))
    parts = [quoted_python, "-m", module]
    for key, value in args:
        parts.append(key)
        if value is not None:
            parts.append(shlex.quote(str(value)))
    return " ".join(parts)


def start_window(session, window_name, command):
    if session_exists(session):
        existing_windows = tmux_window_names(session)
        if window_name in existing_windows:
            print(f"tmux window {session}:{window_name} is already running.")
            return False
        tmux("new-window", "-t", session, "-n", window_name, command)
        return True

    tmux("new-session", "-d", "-s", session, "-n", window_name, command)
    return True


def camera_tasks(config_name, config, camera_name=None):
    cameras = config.get("CAMERA_SERVERS", [])
    if camera_name is not None:
        cameras = [camera for camera in cameras if camera.get("name") == camera_name]
        if not cameras:
            raise ValueError(f"No camera named {camera_name!r}")

    python = os.environ.get("JAZLABS_CAMERA_SERVER_PYTHON", sys.executable)
    for camera in cameras:
        if camera.get("enabled", True):
            name = camera["name"]
            yield (
                name,
                module_command(
                    "JazLabs.launchers.launch_camera_server",
                    [("--config", config_name), ("--name", name)],
                    python,
                ),
            )


def slm_linux_task(config_name):
    return (
        "slm",
        module_command(
            "JazLabs.launchers.launch_slm_linux_server",
            [("--config", config_name)],
            choose_slm_python(),
        ),
    )


def slm_windows_task(config_name):
    return (
        "slm_windows",
        module_command(
            "JazLabs.launchers.launch_slm_windows_server",
            [("--config", config_name)],
            os.environ.get("JAZLABS_SLM_WINDOWS_SERVER_PYTHON", sys.executable),
        ),
    )


def slm_stack_task(config_name, config):
    slm = config.get("SLM_STACK_SERVER", {})
    return (
        slm.get("name", "slm_stack"),
        module_command(
            "JazLabs.launchers.launch_slm_stack_server",
            [("--config", config_name)],
            os.environ.get("JAZLABS_SLM_STACK_SERVER_PYTHON", sys.executable),
        ),
    )


def daq_tasks(config_name, config, daq_name=None):
    daqs = config.get("DAQ_SERVERS", [])
    if daq_name is not None:
        daqs = [daq for daq in daqs if daq.get("name") == daq_name]
        if not daqs:
            raise ValueError(f"No DAQ named {daq_name!r}")

    python = os.environ.get("JAZLABS_DAQ_SERVER_PYTHON", sys.executable)
    for daq in daqs:
        if daq.get("enabled", True):
            name = daq["name"]
            yield (
                name,
                module_command(
                    "JazLabs.launchers.launch_daq_server",
                    [("--config", config_name), ("--name", name)],
                    python,
                ),
            )


def optical_switch_tasks(config_name, config, switch_name=None):
    switches = config.get("OPTICAL_SWITCH_SERVERS", [])
    if switch_name is not None:
        switches = [
            switch for switch in switches if switch.get("name") == switch_name
        ]
        if not switches:
            raise ValueError(f"No optical switch named {switch_name!r}")

    python = os.environ.get("JAZLABS_OPTICAL_SWITCH_SERVER_PYTHON", sys.executable)
    for switch in switches:
        if switch.get("enabled", True):
            name = switch["name"]
            yield (
                name,
                module_command(
                    "JazLabs.launchers.launch_optical_switch_server",
                    [("--config", config_name), ("--name", name)],
                    python,
                ),
            )


def build_parser():
    parser = argparse.ArgumentParser(description="Start JazLabs servers in tmux.")
    parser.add_argument(
        "target",
        choices=(
            "all",
            "camera",
            "slm-linux",
            "slm-windows",
            "slm-stack",
            "daq",
            "optical-switch",
        ),
        help="Server group to start.",
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument(
        "--name",
        "--camera",
        "--daq",
        "--switch",
        dest="name",
        default=None,
    )
    parser.add_argument("--session", default=None)
    parser.add_argument("--restart", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    session = args.session or config.get("TMUX_SESSION", "jazlabs_servers")

    if args.restart and session_exists(session):
        tmux("kill-session", "-t", session)

    if args.target == "all" and args.name is not None:
        raise SystemExit(
            "--name can only be used with camera, daq, or optical-switch."
        )

    tasks = []
    if args.target in ("all", "camera"):
        camera_name = args.name if args.target == "camera" else None
        tasks.extend(camera_tasks(args.config, config, camera_name))
    if args.target in ("all", "slm-linux") and config.get("SLM_LINUX_SERVER", {}).get("enabled", True):
        tasks.append(slm_linux_task(args.config))
    if args.target == "slm-windows" and config.get("SLM_WINDOWS_SERVER", {}).get("enabled", True):
        tasks.append(slm_windows_task(args.config))
    if args.target in ("all", "slm-stack") and config.get("SLM_STACK_SERVER", {}).get("enabled", False):
        tasks.append(slm_stack_task(args.config, config))
    if args.target in ("all", "daq"):
        daq_name = args.name if args.target == "daq" else None
        tasks.extend(daq_tasks(args.config, config, daq_name))
    if args.target in ("all", "optical-switch"):
        switch_name = args.name if args.target == "optical-switch" else None
        tasks.extend(optical_switch_tasks(args.config, config, switch_name))

    if not tasks:
        raise SystemExit("No enabled server tasks matched the request.")

    started = []
    for window_name, command in tasks:
        if start_window(session, window_name, command):
            started.append(window_name)

    print(f"tmux session: {session}")
    if started:
        print(f"Started windows: {', '.join(started)}")
    print(f"Attach with: tmux attach -t {session}")


if __name__ == "__main__":
    main()
