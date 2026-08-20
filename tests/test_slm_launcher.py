from pathlib import Path
import tomllib

import pytest

import JazLabs.launchers.launch_slm_bridge as slm_bridge_launcher
import JazLabs.launchers.launch_slm_milk_server as milk_slm_launcher
import JazLabs.launchers.launch_slm_server as slm_server_launcher
from JazLabs.launchers.config import load_config


def test_slm_console_scripts_select_distinct_stacks():
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with project_file.open("rb") as file_handle:
        scripts = tomllib.load(file_handle)["project"]["scripts"]

    assert scripts["jazlabs-server-slm"] == (
        "JazLabs.launchers.launch_slm_server:main"
    )
    assert scripts["jazlabs-server-slm-milk"] == (
        "JazLabs.launchers.launch_slm_milk_server:main"
    )
    assert "jazlabs-server-slm-stack" not in scripts


def test_default_lab_activates_only_normal_slm_configuration():
    config = load_config("default_lab")

    assert "SLM_SERVER" in config
    assert "SLM_BRIDGE" in config
    assert "SLM_VIEWER" in config
    assert "SLM_MILK_SERVER" not in config
    assert "SLM_MILK_BRIDGE" not in config


def test_milk_launcher_rejects_normal_config(monkeypatch):
    monkeypatch.setattr(
        milk_slm_launcher,
        "load_config",
        lambda config_name: {"SLM_SERVER": {"host": "0.0.0.0"}},
    )

    with pytest.raises(ValueError, match=r"jazlabs-server-slm\.$"):
        milk_slm_launcher.main(["--config", "HDStokes"])


def test_normal_server_rejects_milk_config(monkeypatch):
    monkeypatch.setattr(
        slm_server_launcher,
        "load_config",
        lambda config_name: {"SLM_MILK_SERVER": {"host": "0.0.0.0"}},
    )

    with pytest.raises(ValueError, match="jazlabs-server-slm-milk"):
        slm_server_launcher.main(["--config", "default_lab"])


def test_normal_bridge_rejects_milk_config(monkeypatch):
    monkeypatch.setattr(
        slm_bridge_launcher,
        "load_config",
        lambda config_name: {
            "SLM_MILK_BRIDGE": {"server_host": "10.161.4.65"}
        },
    )

    with pytest.raises(ValueError, match="jazlabs-bridge-slm-milk"):
        slm_bridge_launcher.main(["--config", "default_lab"])
