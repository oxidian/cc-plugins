#!/usr/bin/env python3
"""Install Codex plugins from a repo-level marketplace."""

from __future__ import annotations

import argparse
import json
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

DEFAULT_MARKETPLACE = "oxidian"
REQUEST_TIMEOUT_S = 120.0
INSTALL_TIMEOUT_S = 600.0


class JsonRpcError(RuntimeError):
    """Raised when the Codex app-server returns a JSON-RPC error."""


class CodexAppServer:
    """Small line-delimited JSON-RPC client for `codex app-server --listen stdio://`."""

    def __init__(self, codex_bin: str = "codex") -> None:
        self._process = subprocess.Popen(
            [codex_bin, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._next_id = 1

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def request(self, method: str, params: dict[str, object] | None, timeout_s: float) -> object:
        request_id = self._next_id
        self._next_id += 1
        message: dict[str, object] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

        while True:
            line = self._read_line(timeout_s)
            try:
                response: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JsonRpcError(f"invalid JSON-RPC response from Codex: {line}") from exc

            if not isinstance(response, dict):
                raise JsonRpcError(f"invalid JSON-RPC response from Codex: {line}")
            response_obj = cast(dict[str, object], response)

            if response_obj.get("id") != request_id:
                continue
            if "error" in response_obj:
                error = response_obj["error"]
                error_message = (
                    cast(dict[str, object], error).get("message", error) if isinstance(error, dict) else error
                )
                raise JsonRpcError(f"{method} failed: {error_message}")
            return response_obj.get("result")

    def _send(self, message: dict[str, object]) -> None:
        if self._process.stdin is None:
            raise JsonRpcError("Codex app-server stdin is unavailable")
        self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def _read_line(self, timeout_s: float) -> str:
        if self._process.stdout is None:
            raise JsonRpcError("Codex app-server stdout is unavailable")

        deadline = time.monotonic() + timeout_s
        while True:
            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr is not None else ""
                raise JsonRpcError(f"Codex app-server exited unexpectedly: {stderr.strip()}")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JsonRpcError("timed out waiting for Codex app-server response")

            readable, _, _ = select.select([self._process.stdout], [], [], remaining)
            if not readable:
                continue

            line = self._process.stdout.readline()
            if line:
                return line


def parse_plugins(value: str) -> list[str]:
    plugins = [plugin.strip() for plugin in value.split(",") if plugin.strip()]
    if not plugins:
        raise ValueError("at least one plugin name is required")
    return plugins


def object_list(value: object) -> list[object]:
    """Return value when it is a JSON array, otherwise an empty list."""
    return cast(list[object], value) if isinstance(value, list) else []


def marketplace_plugin(
    plugin_list_result: dict[str, object],
    marketplace_name: str,
    plugin_name: str,
) -> tuple[str, dict[str, object]]:
    marketplace_names: list[str] = []
    for marketplace_value in object_list(plugin_list_result.get("marketplaces")):
        if not isinstance(marketplace_value, dict):
            continue
        marketplace = cast(dict[str, object], marketplace_value)
        name = marketplace.get("name")
        if isinstance(name, str):
            marketplace_names.append(name)
        if name != marketplace_name:
            continue

        marketplace_path = marketplace.get("path")
        if not isinstance(marketplace_path, str):
            raise JsonRpcError(f"marketplace `{marketplace_name}` does not have a local path")

        plugins = object_list(marketplace.get("plugins"))
        for plugin_value in plugins:
            if not isinstance(plugin_value, dict):
                continue
            plugin = cast(dict[str, object], plugin_value)
            if plugin.get("name") == plugin_name:
                return marketplace_path, plugin

        available_names: list[str] = []
        for plugin_value in plugins:
            if not isinstance(plugin_value, dict):
                continue
            plugin = cast(dict[str, object], plugin_value)
            name_value = plugin.get("name")
            available_names.append(name_value if isinstance(name_value, str) else "?")
        available = ", ".join(available_names) if available_names else "none"
        raise JsonRpcError(
            f"plugin `{plugin_name}` was not found in marketplace `{marketplace_name}`; found: {available}"
        )

    available_marketplaces = ", ".join(marketplace_names) if marketplace_names else "none"
    raise JsonRpcError(
        f"marketplace `{marketplace_name}` was not found; discovered marketplaces: {available_marketplaces}"
    )


def list_plugins(client: CodexAppServer, cwd: Path) -> dict[str, object]:
    result = client.request("plugin/list", {"cwds": [str(cwd)]}, REQUEST_TIMEOUT_S)
    if not isinstance(result, dict):
        raise JsonRpcError("plugin/list returned an unexpected response")
    return cast(dict[str, object], result)


def install_plugins(
    cwd: Path, plugins: list[str], marketplace_name: str, codex_bin: str, *, quiet: bool = False
) -> None:
    client = CodexAppServer(codex_bin)
    try:
        client.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "oxidian-codex-plugin-installer",
                    "title": "Oxidian Codex plugin installer",
                    "version": "1.0.0",
                },
                "capabilities": {"experimentalApi": True},
            },
            REQUEST_TIMEOUT_S,
        )
        client.notify("initialized")

        plugin_list = list_plugins(client, cwd)
        for plugin_name in plugins:
            marketplace_path, plugin = marketplace_plugin(plugin_list, marketplace_name, plugin_name)
            if plugin.get("installed") is True and plugin.get("enabled") is True:
                if not quiet:
                    print(f"{plugin_name}@{marketplace_name} is already installed and enabled")
                continue

            if not quiet:
                print(f"Installing {plugin_name}@{marketplace_name}")
            client.request(
                "plugin/install",
                {"marketplacePath": marketplace_path, "pluginName": plugin_name},
                INSTALL_TIMEOUT_S,
            )

        plugin_list = list_plugins(client, cwd)
        failed: list[str] = []
        for plugin_name in plugins:
            _, plugin = marketplace_plugin(plugin_list, marketplace_name, plugin_name)
            if plugin.get("installed") is not True or plugin.get("enabled") is not True:
                failed.append(plugin_name)

        if failed:
            raise JsonRpcError(f"plugins were not installed and enabled: {', '.join(failed)}")
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Codex plugins from a repo marketplace")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Repository whose marketplace should be used")
    parser.add_argument("--plugins", required=True, help="Comma-separated plugin names to install")
    parser.add_argument("--marketplace", default=DEFAULT_MARKETPLACE, help="Marketplace name")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable")
    parser.add_argument("--quiet", action="store_true", help="Only print errors")
    args = parser.parse_args()

    try:
        plugins = parse_plugins(args.plugins)
        install_plugins(args.cwd.resolve(), plugins, args.marketplace, args.codex_bin, quiet=args.quiet)
    except (JsonRpcError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Installed Codex plugins: {', '.join(plugins)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
