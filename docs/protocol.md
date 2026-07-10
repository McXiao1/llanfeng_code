# Llanfeng Code URL Protocol

本文档说明 Web 端如何通过浏览器唤起桌面应用并传入配置。应用使用 Windows URL Scheme：

```text
llanfeng-code://
```

正式安装包会在安装过程中为当前 Windows 用户自动注册该协议。Web 页面发起导入后，桌面端会显示确认弹窗；只有用户确认后才会保存配置。直接运行开发源码不会注册协议。

## 单条配置

格式：

```text
llanfeng-code://v1/import?target=codex|claude&name=&url=&key=&model=&enabled=true
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `target` | 是 | `codex` 或 `claude` |
| `name` | 是 | 配置名称 |
| `url` | 是 | API Base URL，例如 `https://api.example.com/v1` |
| `key` | 是 | API Key |
| `model` | 否 | 默认模型 |
| `enabled` | 否 | 建议启用标记，桌面端仍会要求用户确认 |

Web 调用示例：

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

## 列表导入

列表使用 `import-list`，把 JSON 列表做 UTF-8 base64url 编码后放入 `payload`：

```text
llanfeng-code://v1/import-list?payload=<base64url-json>
```

JSON 结构：

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

Web 调用示例：

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

## 注意事项

- `payload` 是编码，不是加密；不要在不可信页面或公开日志中暴露真实 Key。
- 浏览器和系统对 URL 长度有限制，列表很长时应拆分多次导入。
- 桌面端只接受 `target=codex` 或 `target=claude`。
- 桌面端导入前会展示确认弹窗；用户点击确认后才会写入本地数据库和系统 Keyring。
- 浏览器可能要求用户确认是否打开外部应用，这是正常的安全行为。
- 如果浏览器没有唤起应用，请确认已通过正式安装包完成安装，并检查 Windows 或浏览器是否拦截自定义协议。
