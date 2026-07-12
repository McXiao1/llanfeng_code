from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from llanfeng_code_assistant.codex_plugin_marketplace import (
    PLUGIN_MARKETPLACE_SCRIPT,
    build_plugin_marketplace_script,
)


def _run_node_harness(body: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable")
    harness = f"""
const calls = [];
const listeners = new Map();
global.window = globalThis;
window.electronBridge = {{
  sendMessageFromView(message) {{ calls.push(message); return message; }}
}};
window.addEventListener = (name, callback) => listeners.set(name, callback);
window.dispatchEvent = (event) => event;
global.document = {{
  scripts: [],
  querySelectorAll() {{ return []; }}
}};
global.performance = {{ getEntriesByType() {{ return []; }} }};
global.fetch = async () => ({{ ok: false, text: async () => '' }});
global.setInterval = (callback) => {{ callback(); return 1; }};
global.clearInterval = () => undefined;
global.setTimeout = (callback) => {{ callback(); return 1; }};
const source = {json.dumps(PLUGIN_MARKETPLACE_SCRIPT)};
eval(source);
{body}
"""
    completed = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_build_plugin_marketplace_script_is_stable_and_self_contained() -> None:
    assert build_plugin_marketplace_script() == PLUGIN_MARKETPLACE_SCRIPT
    assert PLUGIN_MARKETPLACE_SCRIPT.startswith("(function")
    assert "list-plugins" in PLUGIN_MARKETPLACE_SCRIPT
    assert "install-plugin" in PLUGIN_MARKETPLACE_SCRIPT
    assert "available_models" not in PLUGIN_MARKETPLACE_SCRIPT
    assert "default_model" not in PLUGIN_MARKETPLACE_SCRIPT


def test_bridge_patch_expands_list_request_and_restores_aliases() -> None:
    result = _run_node_harness(
        """
window.electronBridge.sendMessageFromView({
  type: 'mcp-request',
  request: {
    id: 7,
    method: 'plugin/list',
    params: { marketplaceKinds: ['codex-plus-openai-curated', 'local'] }
  }
});
console.log(JSON.stringify(calls[0]));
"""
    )

    request = result["request"]
    assert request["method"] == "plugin/list"
    assert request["params"]["marketplaceKinds"] == [
        "openai-curated",
        "local",
        "vertical",
    ]


def test_bridge_patch_repairs_remote_install_request() -> None:
    result = _run_node_harness(
        """
window.electronBridge.sendMessageFromView({
  method: 'vscode://codex/plugin/install',
  params: {
    pluginName: 'example',
    marketplacePath: 'remote:codex-plus-openai-curated'
  }
});
console.log(JSON.stringify(calls[0]));
"""
    )

    assert result["params"]["remoteMarketplaceName"] == "openai-curated"
    assert "marketplacePath" not in result["params"]


def test_filter_patch_bypasses_known_hidden_marketplace_filter_without_calling_it() -> None:
    result = _run_node_harness(
        """
global.t = ['openai-curated'];
let callbackCalls = 0;
const hiddenFilter = function(e) { callbackCalls += 1; return !t.includes(e.name); };
const official = [{ name: 'openai-curated' }];
const unrelated = [{ name: 'community' }];
const officialResult = official.filter(hiddenFilter);
const unrelatedResult = unrelated.filter(() => true);
console.log(JSON.stringify({ officialResult, unrelatedResult, callbackCalls }));
"""
    )

    assert result["officialResult"] == [{"name": "openai-curated"}]
    assert result["unrelatedResult"] == [{"name": "community"}]
    assert result["callbackCalls"] == 0


def test_filter_patch_bypasses_known_build_flavor_filter() -> None:
    result = _run_node_harness(
        """
global.u = () => false;
global.r = 'community';
const buildFilter = function(e) { return !u(e.marketplaceName) || e.marketplaceName === r; };
const plugins = [
  { name: 'one', marketplaceName: 'openai-bundled' },
  { name: 'two', marketplaceName: 'community' }
];
console.log(JSON.stringify(plugins.filter(buildFilter)));
"""
    )

    assert result == [
        {"name": "one", "marketplaceName": "openai-bundled"},
        {"name": "two", "marketplaceName": "community"},
    ]
