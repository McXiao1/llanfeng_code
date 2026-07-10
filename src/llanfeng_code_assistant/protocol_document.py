from __future__ import annotations

# ruff: noqa: RUF001

PROTOCOL_DOCUMENT_MARKDOWN = r"""
# 制作介绍
- 岚风科技 (岚风游戏) 出品
- 技术咨询: **QQ:2235359588**
- QQ群: **248137797**
- 开源地址: [点我跳转](https://lanfengai.cn)

# Web 端对接协议

Llanfeng Code Assistant(岚风科技) 使用 Windows URL Scheme：

```text
llanfeng-code://
```

正式安装包会在安装过程中为当前 Windows 用户自动注册该协议。
Web 页面发起导入后，桌面端会显示确认弹窗；只有用户确认后才会保存配置。

## 单条配置导入

```text
llanfeng-code://v1/import?target=codex|claude&name=&url=&key=&model=&enabled=true
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `target` | 是 | `codex` 或 `claude` |
| `name` | 是 | 配置名称 |
| `url` | 是 | API Base URL，例如 `https://api.example.com/v1` |
| `key` | 是 | API Key |
| `model` | 否 | 默认模型 |
| `enabled` | 否 | 建议启用标记；桌面端仍会要求用户确认 |

### HTML / JavaScript 示例

```html
<button id="import-codex">导入 Codex 配置</button>

<script>
  function openLlanfengCodeProfile(profile) {
    const params = new URLSearchParams({
      target: profile.target,
      name: profile.name,
      url: profile.url,
      key: profile.key,
    });

    if (profile.model) {
      params.set("model", profile.model);
    }

    if (profile.enabled) {
      params.set("enabled", "true");
    }

    window.location.href = `llanfeng-code://v1/import?${params.toString()}`;
  }

  document.querySelector("#import-codex").addEventListener("click", () => {
    openLlanfengCodeProfile({
      target: "codex",
      name: "Codex Relay",
      url: "https://api.example.com/v1",
      key: "sk-your-key",
      model: "gpt-5-codex",
      enabled: true,
    });
  });
</script>
```

## 批量配置导入

批量导入使用 `import-list`。先将 JSON 列表编码为 UTF-8，再进行 base64url 编码，并放入 `payload`：

```text
llanfeng-code://v1/import-list?payload=<base64url-json>
```

JSON 示例：

```json
[
  {
    "target": "codex",
    "name": "Codex Relay",
    "url": "https://codex.example.com/v1",
    "key": "sk-codex",
    "model": "gpt-5-codex"
  },
  {
    "target": "claude",
    "name": "Claude Relay",
    "url": "https://claude.example.com",
    "key": "sk-claude",
    "model": "claude-sonnet-4-5"
  }
]
```

### HTML / JavaScript 示例

```html
<button id="import-list">导入配置列表</button>

<script>
  function toBase64Url(value) {
    const bytes = new TextEncoder().encode(value);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });

    return btoa(binary)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
  }

  function openLlanfengCodeProfiles(profiles) {
    const payload = toBase64Url(JSON.stringify(profiles));
    window.location.href = `llanfeng-code://v1/import-list?payload=${payload}`;
  }

  document.querySelector("#import-list").addEventListener("click", () => {
    openLlanfengCodeProfiles([
      {
        target: "codex",
        name: "Codex Relay",
        url: "https://codex.example.com/v1",
        key: "sk-codex",
        model: "gpt-5-codex",
      },
      {
        target: "claude",
        name: "Claude Relay",
        url: "https://claude.example.com",
        key: "sk-claude",
        model: "claude-sonnet-4-5",
      },
    ]);
  });
</script>
```

也支持对象包裹格式：

```json
{
  "profiles": [
    {
      "target": "codex",
      "name": "Codex Relay",
      "url": "https://codex.example.com/v1",
      "key": "sk-codex",
      "model": "gpt-5-codex"
    }
  ]
}
```

## 安全与兼容性注意事项

- `payload` 只是编码，不是加密；不要在不可信页面或公开日志中暴露真实 API Key。
- 浏览器和 Windows 对 URL 长度有限制，列表较长时应拆分为多次导入。
- 桌面端只接受 `target=codex` 或 `target=claude`。
- 所有导入都会先显示确认弹窗，不会静默写入数据库或系统 Keyring。
- 浏览器可能要求用户确认是否打开外部应用，这是正常的安全行为。
- 如果浏览器无法唤起应用，请确认使用正式安装包完成安装，并检查浏览器或 Windows 是否拦截自定义协议。
""".strip()


