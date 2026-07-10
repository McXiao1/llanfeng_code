"""CDP-based ChatGPT Desktop (Codex) launcher and script injector.

OpenAI's ChatGPT Desktop (package name ``OpenAI.Codex``) is distributed
through the Microsoft Store and is an **Electron** application.  Electron
apps expose Chrome DevTools Protocol via ``--remote-debugging-port``.

Injection approach reverse-engineered from the CodexPlusPlus open-source
project (https://github.com/BigPizzaV3/CodexPlusPlus), specifically
``assets/inject/renderer-inject.js``.

Key mechanisms:
1. **Statsig in-memory patch** — patches ``window.__STATSIG__`` clients'
   ``getDynamicConfig("107580212")`` to add custom models to
   ``available_models`` (the account whitelist).
2. **Response.prototype.json patch** — intercepts every JSON response and
   injects custom model descriptors into model arrays / sets.
3. **dispatchEvent patch** — intercepts MCP ``model/list`` requests to
   include hidden models.
4. **Plugin unlock** — patches ``Array.prototype.filter`` using source-only
   detection (never calls the original callback during detection) to bypass
   build-flavor and marketplace-hidden filters; also patches
   ``window.electronBridge.sendMessageFromView``.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path

# websockets is imported lazily inside inject_scripts() so that the module
# loads cleanly even when the package is absent (e.g. a stale build without
# websockets bundled).  The button will always be visible; only the actual
# injection step fails if websockets is missing at runtime.

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CDP_DEFAULT_PORT: int = 9222
CDP_WAIT_TIMEOUT: float = 30.0
CDP_WAIT_INTERVAL: float = 0.5

STORE_PACKAGE_NAME: str = "OpenAI.Codex"
STORE_EXE_RELPATH: str = r"app\ChatGPT.exe"
STORE_EXE_RELPATH_ALT: str = r"app\Codex.exe"

_NPM_WIN32_X64_RELPATH = (
    "@openai/codex/node_modules/@openai/codex-win32-x64"
    "/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
)
_NPM_WIN32_ARM64_RELPATH = (
    "@openai/codex/node_modules/@openai/codex-win32-arm64"
    "/vendor/aarch64-pc-windows-msvc/bin/codex.exe"
)

# ---------------------------------------------------------------------------
# Script factories
# ---------------------------------------------------------------------------


def _build_config_script(
    model_names: Sequence[str],
    default_model: str,
    provider_name: str,
) -> str:
    """Return JS that sets window.__LF_CATALOG__ with embedded model data."""
    data = {
        "models": list(model_names),
        "defaultModel": default_model,
        "providerName": provider_name or "Custom model",
    }
    return f"window.__LF_CATALOG__ = {json.dumps(data, ensure_ascii=False)};"


# ---------------------------------------------------------------------------
# Static injection scripts
# ---------------------------------------------------------------------------

_GUARD = "(function(){var G='__lf_{tag}__';if(window[G])return;window[G]=true;"
_END = "})();"


def _wrap(tag: str, body: str) -> str:
    return _GUARD.replace("{tag}", tag) + body + _END


# ---------------------------------------------------------------------------
# Script 1 — Statsig fast-startup timeout
# ---------------------------------------------------------------------------
FAST_STARTUP_SCRIPT: str = _wrap("fast_startup", r"""
  var TIMEOUT_MS = 800;
  var STATSIG_HOSTS = new Set([
    'ab.chatgpt.com','featureassets.org','prodregistryv2.org',
    'api.statsigcdn.com','statsigapi.net','cloudflare-dns.com'
  ]);
  function isStatsig(input) {
    try {
      var u = new URL(typeof input==='string'?input:(input&&input.url)||'', location.href);
      return STATSIG_HOSTS.has(u.hostname);
    } catch { return false; }
  }
  function mkTimeoutSignal(orig) {
    var ctrl = new AbortController();
    var t = setTimeout(function(){ ctrl.abort(); }, TIMEOUT_MS);
    if (orig) {
      if (orig.aborted) ctrl.abort();
      else orig.addEventListener('abort', function(){ ctrl.abort(); }, {once:true});
    }
    return { signal: ctrl.signal, clear: function(){ clearTimeout(t); } };
  }
  if (!window.fetch.__lf_fast_patched) {
    var _origFetch = window.fetch.bind(window);
    var _pf = function(input, init) {
      if (!isStatsig(input)) return _origFetch(input, init);
      var ts = mkTimeoutSignal(init&&init.signal);
      return _origFetch(input, Object.assign({}, init||{}, {signal:ts.signal})).finally(ts.clear);
    };
    _pf.__lf_fast_patched = true;
    window.fetch = _pf;
  }
""")

# ---------------------------------------------------------------------------
# Script 2 — Plugin marketplace unlock
#
# SAFETY FIX: detect plugin arrays by SOURCE + STRUCTURE only.
# Previous version called !cb(p) which executed the original callback during
# detection — this caused React render crashes because Array.prototype.filter
# is called during rendering and the callbacks can throw or mutate state.
# ---------------------------------------------------------------------------
PLUGIN_UNLOCK_SCRIPT: str = _wrap("plugin_unlock", r"""
  var OFFICIAL = new Set([
    'openai-bundled','openai-curated','openai-primary-runtime',
    'openai-api-curated','openai-curated-remote'
  ]);
  function restoreName(n) {
    if (n==='codex-plus-openai-curated') return 'openai-curated';
    if (n==='codex-plus-openai-curated-remote') return 'openai-curated-remote';
    return n;
  }
  function isOfficial(n) { return OFFICIAL.has(restoreName(String(n||''))); }
  function fnSource(cb) {
    try { return Function.prototype.toString.call(cb); } catch { return ''; }
  }
  // Detect plugin-hide filters by SOURCE text and array STRUCTURE — never call cb().
  function isPluginHideFilter(cb, arr) {
    if (!Array.isArray(arr) || !arr.length || typeof cb !== 'function') return false;
    var src = fnSource(cb);
    if (!src.includes('!t.includes(e.name)') && !src.includes('!t.has(e.model)')) return false;
    // Array must contain at least one item that looks like a plugin or marketplace entry.
    return arr.some(function(item) {
      if (!item || typeof item !== 'object') return false;
      var n = item.marketplaceName || item.name;
      return typeof n === 'string' && isOfficial(n);
    });
  }
  if (!Array.prototype.filter.__lf_plugin_patched) {
    var _origFilter = Array.prototype.filter;
    var _pf = function(cb, thisArg) {
      try {
        if (isPluginHideFilter(cb, this)) return Array.from(this);
      } catch {}
      return _origFilter.call(this, cb, thisArg);
    };
    _pf.__lf_plugin_patched = true;
    Array.prototype.filter = _pf;
  }
  function patchBridge() {
    var b = window.electronBridge;
    if (!b || typeof b.sendMessageFromView !== 'function' || b.__lf_bridge_patched) return;
    var _orig = b.sendMessageFromView.bind(b);
    b.sendMessageFromView = function(msg) {
      try {
        if (msg && msg.method === 'list-plugins') {
          msg = Object.assign({}, msg, {params: Object.assign({}, msg.params || {}, {marketplaceKinds: ['openai-curated']})});
        }
        if (msg && msg.method === 'install-plugin' && msg.params && msg.params.remoteMarketplaceName) {
          msg = Object.assign({}, msg, {params: Object.assign({}, msg.params, {remoteMarketplaceName: restoreName(msg.params.remoteMarketplaceName)})});
        }
      } catch {}
      return _orig(msg);
    };
    b.__lf_bridge_patched = true;
  }
  patchBridge();
  window.addEventListener('load', patchBridge);
  var _bTimer = setInterval(function() {
    patchBridge();
    if (window.electronBridge && window.electronBridge.__lf_bridge_patched) clearInterval(_bTimer);
  }, 100);
  setTimeout(function() { clearInterval(_bTimer); }, 5000);
""")

# ---------------------------------------------------------------------------
# Script 3 — Model whitelist unlock (3 safe layers)
#
# SAFETY FIX 1: patchModelArray now requires modelArrayLooksPatchable() before
# pushing descriptors. This prevents corrupting non-model arrays (including
# React fiber arrays).
#
# SAFETY FIX 2: Removed walkFiber / MutationObserver / React fiber patching
# entirely. Walking the full React fiber graph and calling patchModelPayload()
# on arbitrary objects corrupts React internal state.  The Statsig + Response
# JSON layers are sufficient for the model whitelist fix.
# ---------------------------------------------------------------------------
MODEL_WHITELIST_SCRIPT: str = _wrap("model_whitelist", r"""
  var EFFORTS = ['minimal','low','medium','high','xhigh','ultra'].map(function(e) {
    return {reasoningEffort: e, description: e + ' effort'};
  });

  function catalog() {
    var c = window.__LF_CATALOG__;
    return (c && Array.isArray(c.models)) ? c : {models: [], defaultModel: '', providerName: 'Custom model'};
  }
  function modelNames() {
    var c = catalog();
    var all = [c.defaultModel].concat(c.models).filter(function(m) { return typeof m === 'string' && m.trim(); });
    return Array.from(new Set(all));
  }
  function modelDescriptor(name) {
    var c = catalog();
    return {
      model: name, id: name, slug: name, name: name, displayName: name,
      description: c.providerName || 'Custom model',
      hidden: false, isDefault: name === (c.defaultModel || c.models[0]),
      defaultReasoningEffort: 'medium', supportedReasoningEfforts: EFFORTS
    };
  }
  // Guard: only treat arrays as model arrays when every item is an object with a model:string.
  function modelArrayLooksPatchable(arr) {
    if (!Array.isArray(arr) || !arr.length) return false;
    return arr.every(function(item) {
      return item && typeof item === 'object' && typeof item.model === 'string';
    });
  }

  // ── Layer 1: Statsig in-memory patch ──────────────────────────────────────
  function patch107580212(cfg) {
    var names = modelNames();
    var val = cfg && cfg.value;
    if (!names.length || !val || typeof val !== 'object') return cfg;
    var avail = Array.isArray(val.available_models) ? val.available_models.slice() : [];
    var changed = false;
    names.forEach(function(n) { if (!avail.includes(n)) { avail.push(n); changed = true; } });
    if (!changed && val.default_model === names[0]) return cfg;
    var next = Object.assign({}, val, {available_models: avail, default_model: names[0] || val.default_model});
    try { cfg.value = next; } catch { return Object.assign({}, cfg, {value: next}); }
    return cfg;
  }
  function patchStatsigClient(client) {
    if (!client || typeof client.getDynamicConfig !== 'function' || client.__lf_model_patched) return;
    client.__lf_model_patched = true;
    var orig = client.getDynamicConfig.bind(client);
    client.getDynamicConfig = function(name, opts) {
      var r = orig(name, opts);
      return name === '107580212' ? patch107580212(r) : r;
    };
    try { patch107580212(client.getDynamicConfig('107580212', {disableExposureLog: true})); } catch {}
  }
  function patchStatsigRoot(root) {
    if (!root || typeof root !== 'object' || root.__lf_statsig_root_patched) return;
    root.__lf_statsig_root_patched = true;
    ['firstInstance', 'instance'].forEach(function(key) {
      var cur;
      try { cur = root[key]; } catch { return; }
      patchStatsigClient(typeof cur === 'function' && key === 'instance' ? cur.call(root) : cur);
      try {
        Object.defineProperty(root, key, {
          configurable: true,
          get: function() { return cur; },
          set: function(next) {
            cur = next;
            patchStatsigClient(typeof next === 'function' && key === 'instance' ? next.call(root) : next);
          }
        });
      } catch {}
    });
    if (root.instances && typeof root.instances === 'object') {
      Object.values(root.instances).forEach(patchStatsigClient);
    }
  }
  function installStatsigRootSetter() {
    var d = Object.getOwnPropertyDescriptor(window, '__STATSIG__');
    if (d && d.configurable === false) return;
    var cur = window.__STATSIG__;
    patchStatsigRoot(cur);
    try {
      Object.defineProperty(window, '__STATSIG__', {
        configurable: true,
        get: function() { return cur; },
        set: function(next) { cur = next; patchStatsigRoot(next); }
      });
    } catch {}
  }
  function runStatsigPatch() {
    installStatsigRootSetter();
    var root = window.__STATSIG__ || globalThis.__STATSIG__;
    patchStatsigRoot(root);
    var clients = [];
    if (root) {
      if (root.firstInstance) clients.push(root.firstInstance);
      if (typeof root.instance === 'function') try { clients.push(root.instance()); } catch {}
      if (root.instances) clients.push.apply(clients, Object.values(root.instances));
    }
    clients.filter(Boolean).forEach(patchStatsigClient);
  }

  // ── Layer 2: Response.prototype.json patch ────────────────────────────────
  // SAFETY: patchModelArray only pushes descriptors into arrays where every
  // existing item already has a model:string property.
  function patchModelArray(arr) {
    if (!modelArrayLooksPatchable(arr)) return false;
    var names = modelNames();
    if (!names.length) return false;
    var changed = false;
    var existing = new Set(arr.map(function(item) { return item && item.model; }));
    // Unhide custom models that already exist in the array
    arr.forEach(function(item) {
      if (item && item.model && names.includes(item.model) && item.hidden !== false) {
        item.hidden = false; changed = true;
      }
    });
    // Add missing custom models
    names.forEach(function(n) {
      if (!existing.has(n)) { arr.push(modelDescriptor(n)); changed = true; }
    });
    return changed;
  }
  function patchAvailSet(s) {
    if (!(s instanceof Set)) return;
    modelNames().forEach(function(n) { s.add(n); });
  }
  function patchAvailArray(a) {
    if (!Array.isArray(a) || !a.every(function(x) { return typeof x === 'string'; })) return;
    modelNames().forEach(function(n) { if (!a.includes(n)) a.push(n); });
  }
  function patchModelPayload(payload) {
    if (!payload || typeof payload !== 'object') return payload;
    patchModelArray(payload.data);
    patchModelArray(payload.models);
    if (Array.isArray(payload.result)) patchModelArray(payload.result);
    patchModelArray(payload.result && payload.result.data);
    patchModelArray(payload.result && payload.result.models);
    patchModelArray(payload.message && payload.message.result && payload.message.result.data);
    patchAvailSet(payload.availableModels);
    patchAvailSet(payload.available_models);
    patchAvailArray(payload.availableModels);
    patchAvailArray(payload.available_models);
    if (Array.isArray(payload.hiddenModels)) {
      var names = modelNames();
      payload.hiddenModels = payload.hiddenModels.filter(function(n) { return !names.includes(n); });
    }
    return payload;
  }
  function installResponseJsonPatch() {
    if (Response.prototype.json.__lf_resp_patched) return;
    var orig = Response.prototype.json;
    Response.prototype.json = async function() {
      var payload = await orig.apply(this, arguments);
      try {
        if (modelNames().length) patchModelPayload(payload);
      } catch {}
      return payload;
    };
    Response.prototype.json.__lf_resp_patched = true;
  }

  // ── Layer 3: dispatchEvent patch for MCP model/list ───────────────────────
  var _modelListReqIds = new Set();
  if (!window.dispatchEvent.__lf_model_dispatch_patched) {
    var _origDispatch = window.dispatchEvent;
    window.dispatchEvent = function(event) {
      try {
        var detail = event && event.detail;
        var req = detail && detail.request;
        if (event && event.type === 'codex-message-from-view' &&
            detail && detail.type === 'mcp-request' &&
            req && req.method === 'model/list') {
          req.params = Object.assign({}, req.params || {}, {includeHidden: true});
          if (req.id != null) _modelListReqIds.add(String(req.id));
        }
        if (event && event.type === 'message') patchMcpModelResponse(event.data);
      } catch {}
      return _origDispatch.call(this, event);
    };
    window.dispatchEvent.__lf_model_dispatch_patched = true;
    window.addEventListener('message', function(evt) {
      try { patchMcpModelResponse(evt && evt.data); } catch {};
    }, true);
  }
  function patchMcpModelResponse(data) {
    if (!data || data.type !== 'mcp-response') return;
    var msg = data.message || data.response;
    var rid = (msg && msg.id != null) ? String(msg.id) : '';
    if (_modelListReqIds.size > 0 && !_modelListReqIds.has(rid)) return;
    _modelListReqIds.delete(rid);
    try {
      patchModelPayload(data);
      patchModelPayload(msg);
      patchModelPayload(msg && msg.result);
      patchModelPayload(msg && msg.result && msg.result.data);
    } catch {}
  }

  // ── Bootstrap ─────────────────────────────────────────────────────────────
  installResponseJsonPatch();
  runStatsigPatch();
  var _startedAt = Date.now();
  var _refreshTimer = setInterval(function() {
    try { runStatsigPatch(); } catch {}
    if (Date.now() - _startedAt > 5000) clearInterval(_refreshTimer);
  }, 120);
  window.addEventListener('load', function() {
    try { runStatsigPatch(); } catch {}
  });
""")


def build_injection_scripts(
    model_names: Sequence[str],
    default_model: str = "",
    provider_name: str = "",
) -> list[str]:
    """Build the full CDP injection script list with model data embedded.

    @param model_names: Model IDs to inject (e.g. ``["gpt-5.6-sol"]``).
    @param default_model: Default model slug written in config.toml.
    @param provider_name: Human-readable provider name for model descriptors.
    @returns: Ordered list of scripts ready for :func:`inject_scripts`.
    """
    effective_default = default_model or (list(model_names)[0] if model_names else "")
    return [
        _build_config_script(list(model_names), effective_default, provider_name),
        FAST_STARTUP_SCRIPT,
        PLUGIN_UNLOCK_SCRIPT,
        MODEL_WHITELIST_SCRIPT,
    ]


#: Default scripts when no profile model data is available.
DEFAULT_SCRIPTS: list[str] = build_injection_scripts([])


# ---------------------------------------------------------------------------
# Executable discovery
# ---------------------------------------------------------------------------


def find_chatgpt_exe() -> Path | None:
    """Locate ChatGPT Desktop via ``Get-AppxPackage -Name "OpenAI.Codex"``."""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(Get-AppxPackage -Name '{STORE_PACKAGE_NAME}').InstallLocation",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        loc = result.stdout.strip()
    except Exception:
        return None
    if not loc:
        return None
    root = Path(loc)
    for rel in (STORE_EXE_RELPATH, STORE_EXE_RELPATH_ALT):
        p = root / rel
        if p.exists():
            return p
    return None


def find_npm_codex_exe(npm_global_root: str | None = None) -> Path | None:
    """Locate the npm-installed Codex native binary (fallback)."""
    if npm_global_root is None:
        try:
            r = subprocess.run(
                ["npm", "root", "-g"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            npm_global_root = r.stdout.strip()
        except Exception:
            return None
    if not npm_global_root:
        return None
    root = Path(npm_global_root)
    for rel in (_NPM_WIN32_X64_RELPATH, _NPM_WIN32_ARM64_RELPATH):
        p = root / rel
        if p.exists():
            return p
    return None


def find_codex_exe() -> Path | None:
    """Find the best available ChatGPT / Codex executable.

    Search order: Microsoft Store installation, then npm global install.
    """
    return find_chatgpt_exe() or find_npm_codex_exe()


# ---------------------------------------------------------------------------
# Process launch
# ---------------------------------------------------------------------------


def launch_codex_with_cdp(
    codex_exe: Path,
    cdp_port: int = CDP_DEFAULT_PORT,
    extra_args: Sequence[str] = (),
) -> "subprocess.Popen[bytes]":
    """Launch ChatGPT.exe with Electron CDP remote-debugging enabled."""
    creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(
        [str(codex_exe), f"--remote-debugging-port={cdp_port}", *extra_args],
        creationflags=creation_flags,
    )


# ---------------------------------------------------------------------------
# CDP connection
# ---------------------------------------------------------------------------


async def get_cdp_ws_url(
    cdp_port: int = CDP_DEFAULT_PORT,
    timeout: float = CDP_WAIT_TIMEOUT,
) -> str:
    """Poll the CDP HTTP endpoint and return the first renderer WebSocket URL."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://localhost:{cdp_port}/json", timeout=2,
            ) as resp:
                pages: list[dict[str, object]] = json.loads(resp.read().decode())
                for page in pages:
                    ws = page.get("webSocketDebuggerUrl")
                    if isinstance(ws, str) and ws:
                        return ws
        except Exception:
            pass
        await asyncio.sleep(CDP_WAIT_INTERVAL)
    raise TimeoutError(
        f"CDP not available on port {cdp_port} after {timeout}s. "
        "Check that ChatGPT.exe accepted --remote-debugging-port."
    )


async def inject_scripts(ws_url: str, scripts: Sequence[str]) -> None:
    """Inject scripts via CDP: persist with addScriptToEvaluateOnNewDocument
    and execute immediately with Runtime.evaluate."""
    import websockets  # deferred — not needed at module-import time

    async with websockets.connect(ws_url) as ws:
        mid = 1
        for script in scripts:
            await ws.send(json.dumps({
                "id": mid,
                "method": "Page.addScriptToEvaluateOnNewDocument",
                "params": {"source": script},
            }))
            await ws.recv()
            mid += 1
            await ws.send(json.dumps({
                "id": mid,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "returnByValue": False},
            }))
            await ws.recv()
            mid += 1


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


async def launch_and_inject(
    codex_exe: Path,
    scripts: Sequence[str] | None = None,
    cdp_port: int = CDP_DEFAULT_PORT,
    wait_timeout: float = CDP_WAIT_TIMEOUT,
) -> "subprocess.Popen[bytes]":
    """Launch ChatGPT Desktop with CDP and inject all enhancement scripts."""
    effective = list(DEFAULT_SCRIPTS if scripts is None else scripts)
    process = launch_codex_with_cdp(codex_exe, cdp_port=cdp_port)
    try:
        ws_url = await get_cdp_ws_url(cdp_port=cdp_port, timeout=wait_timeout)
        await inject_scripts(ws_url, effective)
    except Exception:
        raise
    return process
