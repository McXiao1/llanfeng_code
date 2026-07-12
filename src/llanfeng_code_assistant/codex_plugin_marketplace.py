"""Self-contained Codex plugin marketplace runtime compatibility patch."""
from __future__ import annotations

_PLUGIN_MARKETPLACE_SCRIPT = r"""(function () {
  "use strict";

  const VERSION = "1";
  const INSTALL_MARKER = "__llanfengPluginMarketplaceVersion";
  const FILTER_MARKER = "__llanfengPluginMarketplaceFilterVersion";
  const BRIDGE_MARKER = "__llanfengPluginMarketplaceBridgeVersion";
  const EVENT_MARKER = "__llanfengPluginMarketplaceEventVersion";
  const CLIENT_MARKER = "__llanfengPluginMarketplaceClientVersion";
  const root = window;

  if (root[INSTALL_MARKER] === VERSION) {
    return { installed: true, version: VERSION, reused: true };
  }

  const officialMarketplaces = new Set([
    "openai-bundled",
    "openai-curated",
    "openai-primary-runtime",
    "openai-api-curated",
    "openai-curated-remote"
  ]);

  const marketplaceAliases = new Map([
    ["codex-plus-openai-bundled", "openai-bundled"],
    ["codex-plus-openai-curated", "openai-curated"],
    ["codex-plus-openai-primary-runtime", "openai-primary-runtime"],
    ["codex-plus-openai-api-curated", "openai-api-curated"],
    ["codex-plus-openai-curated-remote", "openai-curated-remote"]
  ]);

  function restoreMarketplaceName(value) {
    const name = String(value || "").trim();
    return marketplaceAliases.get(name) || name;
  }

  function normalizeMarketplaceKind(value) {
    const kind = String(value || "").trim();
    if (kind.startsWith("remote:")) {
      return restoreMarketplaceName(kind.slice("remote:".length));
    }
    return restoreMarketplaceName(kind);
  }

  function isOfficialMarketplace(value) {
    return officialMarketplaces.has(restoreMarketplaceName(value));
  }

  function normalizePluginMethod(method, params) {
    const raw = String(method || "");
    if (raw === "send-cli-request-for-host" && params && params.method) {
      return String(params.method);
    }
    if (raw === "vscode://codex/list-plugins" || raw === "plugin/list") {
      return "list-plugins";
    }
    if (raw === "vscode://codex/plugin/install" || raw === "plugin/install") {
      return "install-plugin";
    }
    if (raw === "vscode://codex/plugin/uninstall" || raw === "plugin/uninstall") {
      return "uninstall-plugin";
    }
    return raw;
  }

  function patchRequestParams(method, params) {
    if (!params || typeof params !== "object") {
      return params;
    }
    const next = { ...params };
    if (method === "list-plugins") {
      const sourceKinds = Array.isArray(next.marketplaceKinds)
        ? next.marketplaceKinds
        : ["local"];
      const kinds = sourceKinds
        .map(normalizeMarketplaceKind)
        .filter(Boolean);
      if (!kinds.includes("vertical")) {
        kinds.push("vertical");
      }
      next.marketplaceKinds = Array.from(new Set(kinds));
    }
    if (method === "install-plugin") {
      if (next.remoteMarketplaceName) {
        next.remoteMarketplaceName = restoreMarketplaceName(next.remoteMarketplaceName);
      }
      if (typeof next.marketplacePath === "string" && next.marketplacePath.startsWith("remote:")) {
        next.remoteMarketplaceName = restoreMarketplaceName(
          next.marketplacePath.slice("remote:".length)
        );
        delete next.marketplacePath;
      }
    }
    return next;
  }

  function patchRequestMessage(message) {
    if (!message || typeof message !== "object") {
      return message;
    }

    if (message.type === "fetch" && typeof message.url === "string") {
      const method = normalizePluginMethod(message.url, message.body);
      if (method !== "list-plugins" && method !== "install-plugin") {
        return message;
      }
      let parsedBody = message.body;
      if (typeof parsedBody === "string") {
        try {
          parsedBody = JSON.parse(parsedBody);
        } catch {
          return message;
        }
      }
      const patchedBody = patchRequestParams(method, parsedBody);
      return {
        ...message,
        body: typeof message.body === "string" ? JSON.stringify(patchedBody) : patchedBody
      };
    }

    if (message.request && typeof message.request === "object") {
      const method = normalizePluginMethod(message.request.method, message.request.params);
      if (method === "list-plugins" || method === "install-plugin") {
        return {
          ...message,
          request: {
            ...message.request,
            params: patchRequestParams(method, message.request.params || {})
          }
        };
      }
    }

    const method = normalizePluginMethod(message.method, message.params);
    if (method === "list-plugins" || method === "install-plugin") {
      return {
        ...message,
        params: patchRequestParams(method, message.params || {})
      };
    }
    return message;
  }

  function patchMarketplaceObject(marketplace) {
    if (!marketplace || typeof marketplace !== "object") {
      return;
    }
    if (typeof marketplace.name === "string") {
      marketplace.name = restoreMarketplaceName(marketplace.name);
    }
    if (typeof marketplace.remoteMarketplaceName === "string") {
      marketplace.remoteMarketplaceName = restoreMarketplaceName(
        marketplace.remoteMarketplaceName
      );
    }
    if (Array.isArray(marketplace.plugins)) {
      marketplace.plugins.forEach((plugin) => {
        if (plugin && typeof plugin === "object" && typeof plugin.marketplaceName === "string") {
          plugin.marketplaceName = restoreMarketplaceName(plugin.marketplaceName);
        }
      });
    }
  }

  function patchMarketplaceResult(result) {
    if (!result || typeof result !== "object") {
      return result;
    }
    if (Array.isArray(result.marketplaces)) {
      result.marketplaces.forEach(patchMarketplaceObject);
    }
    if (result.data && typeof result.data === "object") {
      patchMarketplaceResult(result.data);
    }
    if (result.result && typeof result.result === "object") {
      patchMarketplaceResult(result.result);
    }
    return result;
  }

  function normalizedFunctionSource(callback) {
    try {
      return Function.prototype.toString.call(callback).replace(/\s+/g, "");
    } catch {
      return "";
    }
  }

  function isKnownBuildFlavorFilter(callback, sample) {
    if (!Array.isArray(sample) || sample.length === 0 || typeof callback !== "function") {
      return false;
    }
    const source = normalizedFunctionSource(callback);
    const knownSource = source.includes("!u(e.marketplaceName)||e.marketplaceName===r")
      || source.includes("!ne(e.marketplaceName)||e.marketplaceName===n");
    return knownSource && sample.some((item) => (
      item && typeof item === "object" && isOfficialMarketplace(item.marketplaceName)
    ));
  }

  function isKnownHiddenMarketplaceFilter(callback, sample) {
    if (!Array.isArray(sample) || sample.length === 0 || typeof callback !== "function") {
      return false;
    }
    const source = normalizedFunctionSource(callback);
    return source.includes("!t.includes(e.name)") && sample.some((item) => (
      item && typeof item === "object" && isOfficialMarketplace(item.name)
    ));
  }

  function installFilterPatch() {
    if (Array.prototype.filter[FILTER_MARKER] === VERSION) {
      return true;
    }
    const originalFilter = Array.prototype.__llanfengOriginalFilter || Array.prototype.filter;
    if (!Array.prototype.__llanfengOriginalFilter) {
      Object.defineProperty(Array.prototype, "__llanfengOriginalFilter", {
        value: originalFilter,
        configurable: true,
        writable: true
      });
    }
    const patchedFilter = function (callback, thisArg) {
      if (
        isKnownBuildFlavorFilter(callback, this)
        || isKnownHiddenMarketplaceFilter(callback, this)
      ) {
        return Array.from(this);
      }
      return originalFilter.call(this, callback, thisArg);
    };
    patchedFilter[FILTER_MARKER] = VERSION;
    Array.prototype.filter = patchedFilter;
    return true;
  }

  function installBridgePatch() {
    const bridge = root.electronBridge;
    if (!bridge || typeof bridge.sendMessageFromView !== "function") {
      return false;
    }
    if (bridge[BRIDGE_MARKER] === VERSION) {
      return true;
    }
    const originalSend = bridge.__llanfengOriginalSendMessageFromView
      || bridge.sendMessageFromView.bind(bridge);
    bridge.__llanfengOriginalSendMessageFromView = originalSend;
    bridge.sendMessageFromView = function (message) {
      return originalSend(patchRequestMessage(message));
    };
    bridge[BRIDGE_MARKER] = VERSION;
    return true;
  }

  function replaceObjectContents(target, source) {
    if (target === source || !target || !source) {
      return;
    }
    Object.keys(target).forEach((key) => delete target[key]);
    Object.assign(target, source);
  }

  function installWindowEventPatch() {
    if (root[EVENT_MARKER] === VERSION) {
      return true;
    }
    const originalDispatch = root.__llanfengOriginalDispatchEvent || root.dispatchEvent;
    if (typeof originalDispatch === "function" && !root.__llanfengOriginalDispatchEvent) {
      root.__llanfengOriginalDispatchEvent = originalDispatch;
      root.dispatchEvent = function (event) {
        try {
          if (event && event.type === "codex-message-from-view" && event.detail) {
            replaceObjectContents(event.detail, patchRequestMessage(event.detail));
          }
          if (event && event.type === "message" && event.data) {
            patchMarketplaceResult(event.data);
          }
        } catch {
        }
        return originalDispatch.call(this, event);
      };
    }
    if (typeof root.addEventListener === "function") {
      root.addEventListener("message", (event) => {
        try {
          patchMarketplaceResult(event && event.data);
        } catch {
        }
      }, true);
    }
    root[EVENT_MARKER] = VERSION;
    return true;
  }

  function appAssetUrl(namePart) {
    const scriptUrls = Array.from(document.scripts || []).map((item) => item.src);
    const linkUrls = Array.from(document.querySelectorAll("link[href]") || [])
      .map((item) => item.href);
    const resourceUrls = typeof performance.getEntriesByType === "function"
      ? performance.getEntriesByType("resource").map((item) => item.name)
      : [];
    return [...scriptUrls, ...linkUrls, ...resourceUrls]
      .filter(Boolean)
      .find((url) => (
        url.includes("/assets/")
        && url.includes(namePart)
        && url.split("?")[0].endsWith(".js")
      ))
      || "";
  }

  function patchRequestClient(client) {
    if (!client || typeof client.sendRequest !== "function") {
      return false;
    }
    if (client[CLIENT_MARKER] === VERSION) {
      return true;
    }
    const originalSendRequest = client.__llanfengOriginalSendRequest
      || client.sendRequest.bind(client);
    client.__llanfengOriginalSendRequest = originalSendRequest;
    client.sendRequest = async function (method, params, options) {
      const normalizedMethod = normalizePluginMethod(method, params);
      const patchedParams = patchRequestParams(normalizedMethod, params);
      const result = await originalSendRequest(method, patchedParams, options);
      return normalizedMethod === "list-plugins" ? patchMarketplaceResult(result) : result;
    };
    client[CLIENT_MARKER] = VERSION;
    return true;
  }

  async function installDirectClientPatch() {
    try {
      const url = appAssetUrl("app-server-manager-signals-");
      if (!url) {
        return false;
      }
      const module = await import(url);
      let patched = false;
      Object.values(module || {}).forEach((candidate) => {
        if (patchRequestClient(candidate)) {
          patched = true;
        }
        if (candidate && typeof candidate.get === "function") {
          try {
            if (patchRequestClient(candidate.get())) {
              patched = true;
            }
          } catch {
          }
        }
      });
      return patched;
    } catch {
      return false;
    }
  }

  const filterInstalled = installFilterPatch();
  const bridgeInstalled = installBridgePatch();
  const eventsInstalled = installWindowEventPatch();
  void installDirectClientPatch();

  let bridgeTimer = 0;
  bridgeTimer = setInterval(() => {
    if (installBridgePatch()) {
      clearInterval(bridgeTimer);
    }
  }, 100);
  setTimeout(() => clearInterval(bridgeTimer), 5000);

  root[INSTALL_MARKER] = VERSION;
  return {
    installed: true,
    version: VERSION,
    filterInstalled,
    bridgeInstalled,
    eventsInstalled
  };
})();"""

PLUGIN_MARKETPLACE_SCRIPT: str = _PLUGIN_MARKETPLACE_SCRIPT


def build_plugin_marketplace_script() -> str:
    """Return the self-contained Codex plugin marketplace patch.

    @returns: JavaScript suitable for CDP new-document and immediate evaluation.
    """

    return PLUGIN_MARKETPLACE_SCRIPT
