"""Tests for install_codex_plugins.py."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

_script_path = Path(__file__).parent.parent / "scripts" / "install_codex_plugins.py"
_spec = importlib.util.spec_from_file_location("install_codex_plugins", _script_path)
assert _spec is not None
assert _spec.loader is not None
install_codex_plugins: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["install_codex_plugins"] = install_codex_plugins
_spec.loader.exec_module(install_codex_plugins)

JsonRpcError = install_codex_plugins.JsonRpcError
install_plugins = install_codex_plugins.install_plugins
marketplace_plugin = install_codex_plugins.marketplace_plugin
parse_plugins = install_codex_plugins.parse_plugins


def test_parse_plugins_trims_and_filters_empty_values() -> None:
    assert parse_plugins(" ox, oxgh ,,") == ["ox", "oxgh"]


def test_parse_plugins_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="at least one plugin"):
        parse_plugins(" , ")


def test_marketplace_plugin_finds_plugin_path_and_summary() -> None:
    result = {
        "marketplaces": [
            {
                "name": "oxidian",
                "path": "/repo/.agents/plugins/marketplace.json",
                "plugins": [{"name": "ox"}, {"name": "oxgh", "installed": False}],
            }
        ]
    }

    path, plugin = marketplace_plugin(result, "oxidian", "oxgh")

    assert path == "/repo/.agents/plugins/marketplace.json"
    assert plugin == {"name": "oxgh", "installed": False}


def test_marketplace_plugin_reports_missing_marketplace() -> None:
    with pytest.raises(JsonRpcError, match="marketplace `oxidian` was not found"):
        marketplace_plugin({"marketplaces": [{"name": "other", "plugins": []}]}, "oxidian", "ox")


def test_marketplace_plugin_reports_missing_plugin() -> None:
    result = {"marketplaces": [{"name": "oxidian", "path": "/m.json", "plugins": [{"name": "ox"}]}]}

    with pytest.raises(JsonRpcError, match="plugin `oxgh` was not found"):
        marketplace_plugin(result, "oxidian", "oxgh")


def test_install_plugins_skips_installed_and_installs_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeCodexAppServer:
        instances: ClassVar[list[FakeCodexAppServer]] = []

        def __init__(self, codex_bin: str = "codex") -> None:
            self.codex_bin = codex_bin
            self.closed = False
            self.notifications: list[str] = []
            self.requests: list[tuple[str, dict[str, object] | None, float]] = []
            self.plugin_lists: list[dict[str, object]] = [
                {
                    "marketplaces": [
                        {
                            "name": "oxidian",
                            "path": "/repo/.agents/plugins/marketplace.json",
                            "plugins": [
                                {"name": "ox", "installed": True, "enabled": True},
                                {"name": "oxgh", "installed": False, "enabled": False},
                            ],
                        }
                    ]
                },
                {
                    "marketplaces": [
                        {
                            "name": "oxidian",
                            "path": "/repo/.agents/plugins/marketplace.json",
                            "plugins": [
                                {"name": "ox", "installed": True, "enabled": True},
                                {"name": "oxgh", "installed": True, "enabled": True},
                            ],
                        }
                    ]
                },
            ]
            self.instances.append(self)

        def notify(self, method: str) -> None:
            self.notifications.append(method)

        def request(self, method: str, params: dict[str, object] | None, timeout_s: float) -> object:
            self.requests.append((method, params, timeout_s))
            if method == "initialize":
                return {}
            if method == "plugin/list":
                return self.plugin_lists.pop(0)
            if method == "plugin/install":
                return {"authPolicy": "ON_INSTALL", "appsNeedingAuth": []}
            raise AssertionError(f"unexpected method: {method}")

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(install_codex_plugins, "CodexAppServer", FakeCodexAppServer)

    install_plugins(Path("/repo"), ["ox", "oxgh"], "oxidian", "codex-test", quiet=True)

    client = FakeCodexAppServer.instances[0]
    assert capsys.readouterr().out == ""
    assert client.codex_bin == "codex-test"
    assert client.closed is True
    assert client.notifications == ["initialized"]
    install_requests = [request for request in client.requests if request[0] == "plugin/install"]
    assert install_requests == [
        (
            "plugin/install",
            {"marketplacePath": "/repo/.agents/plugins/marketplace.json", "pluginName": "oxgh"},
            install_codex_plugins.INSTALL_TIMEOUT_S,
        )
    ]
