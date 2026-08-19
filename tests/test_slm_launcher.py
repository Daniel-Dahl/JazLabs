from pathlib import Path
import tomllib

import pytest

import JazLabs.launchers.launch_slm_server as milk_slm_launcher


def test_slm_console_scripts_select_distinct_stacks():
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with project_file.open("rb") as file_handle:
        scripts = tomllib.load(file_handle)["project"]["scripts"]

    assert scripts["jazlabs-server-slm"] == (
        "JazLabs.launchers.launch_slm_stack_server:main"
    )
    assert scripts["jazlabs-server-slm-milk"] == (
        "JazLabs.launchers.launch_slm_server:main"
    )
    assert "jazlabs-server-slm-stack" not in scripts


def test_milk_launcher_explains_stack_config_mismatch(monkeypatch):
    monkeypatch.setattr(
        milk_slm_launcher,
        "load_config",
        lambda config_name: {"SLM_STACK_SERVER": {"host": "0.0.0.0"}},
    )

    with pytest.raises(ValueError, match=r"jazlabs-server-slm\.$"):
        milk_slm_launcher.main(["--config", "HDStokes"])
