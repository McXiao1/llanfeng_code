<div align="center">

# Llanfeng Code Assistant

**Codex / Claude 一键安装与 Codex Desktop 增强工具**

面向 Windows 开发者的轻量桌面助手，只保留 CLI 安装、模型白名单解锁、安全配置恢复与插件市场增强。

[![Version](https://img.shields.io/github/v/release/McXiao1/llanfeng_code?label=版本&color=4A90E2)](https://github.com/McXiao1/llanfeng_code/releases/latest)
[![Platform](https://img.shields.io/badge/平台-Windows-0078D4)](https://github.com/McXiao1/llanfeng_code/releases/latest)
[![License](https://img.shields.io/badge/许可-MIT-green)](#)

</div>

---

## 项目定位

Llanfeng Code Assistant 不再管理 API 上游、密钥或本地 provider profiles。主界面保持为五个明确操作：

1. **安装/更新 Codex**
2. **安装/更新 Claude**
3. **解锁模型**
4. **恢复配置**
5. **增强启动 Codex**

应用仍保留环境状态检测、单实例运行和软件内更新横幅。

## 功能

| 功能 | 行为 |
| --- | --- |
| Codex 一键安装 | 使用固定版本的 `@openai/codex` npm 包完成全局安装或更新 |
| Claude 一键安装 | 使用固定版本的 `@anthropic-ai/claude-code` npm 包完成全局安装或更新 |
| 前置环境处理 | 检测 Node.js、npm 与 Git；缺失时下载并打开对应官方安装程序 |
| 模型解锁 | 从已安装 Codex CLI 的 bundled catalog 发现候选模型，并仅追加缺失的 Statsig 白名单项 |
| 安全配置恢复 | 备份并移除 `config.toml` / `models.json`，定向清除 Statsig 模型缓存，同时保留 `auth.json` 与用户数据 |
| 插件市场增强 | 以 CDP 模式启动 Microsoft Store Codex Desktop，在受验证的 `app://` renderer 中加载市场兼容脚本 |
| 自动更新 | 启动后静默检查 GitHub Release，并在应用内下载和启动新版安装包 |

## 安装

### 使用安装包

1. 前往 [Releases 页面](https://github.com/McXiao1/llanfeng_code/releases/latest)。
2. 下载 `Llanfeng-Code-Assistant-Setup-x.y.z.exe`。
3. 运行安装向导；桌面快捷方式可选。

安装器使用当前用户权限，默认安装到 `%LOCALAPPDATA%\Programs\Llanfeng Code Assistant`，不会写入 URL scheme 注册表项。

### 系统要求

- Windows 10 / 11（64 位）
- Codex / Claude CLI：Node.js 22 或更高版本及 npm
- Claude Code：需要 Git
- Codex 增强功能：需要 Microsoft Store 版本 Codex Desktop，并至少正常启动过一次

应用会在缺少 Node.js 或 Git 时打开对应安装程序；完成外部安装后，再次点击目标按钮即可继续。

## 使用

### 安装或更新 CLI

点击 **安装/更新 Codex** 或 **安装/更新 Claude**。应用会：

1. 检查所需环境；
2. 设置项目使用的 npm mirror；
3. 执行固定版本的全局 npm 安装命令；
4. 刷新顶部工具状态。

### 解锁 Codex 模型

点击 **解锁模型** 后，应用执行以下流程：

1. 调用 `codex debug models --bundled` 获取当前安装版本自带的模型目录；
2. 只接受非空 `slug`、`visibility == "list"` 且 `supported_in_api` 不为 `false` 的模型；
3. 读取 Codex Desktop 的 Statsig LevelDB；
4. 只向现有 `available_models` 数组追加缺失项；
5. 保留 `default_model` 与未知字段，不创建空白名单；
6. 仅在确实需要写入时创建 LevelDB 备份。

隐藏模型（例如 catalog 中标记为隐藏的 `codex-auto-review`）不会被加入白名单。

如果 Codex 正在运行，界面会先请求明确确认。数据库写入只会在 Codex 完全退出后进行。成功提示会显示新增模型与备份目录；已经解锁时不会重复写入或重复备份。

### 恢复 Codex 配置

点击 **恢复配置** 后，应用只处理本工具可能影响的配置边界：

1. 检查 `~/.codex/config.toml`、`~/.codex/models.json` 与 Codex Desktop Statsig 缓存；
2. 显示将修改的精确目标，并明确列出保留内容；
3. 如果 Codex 正在运行，先请求确认关闭；
4. 在 `%APPDATA%/lanfeng_code/backups/` 创建带时间戳的完整备份和恢复清单；
5. 移除 `config.toml`、`models.json`，并只失效 Statsig evaluation / 时间戳缓存键；
6. 下次启动 Codex 时重新获取官方模型配置。

应用保留 `~/.codex/auth.json`、登录状态、会话、历史、Skills、插件与其他 LevelDB 数据。任何中途失败都会尝试从备份回滚；回滚不完整时会显示备份位置和手动恢复提示。

### 增强启动 Codex

使用前请完全关闭 Codex Desktop，然后点击 **增强启动 Codex**。

应用只查找 Microsoft Store 包 `OpenAI.Codex`，为新进程分配 loopback CDP 端口，并且只向类型为 `page`、URL 以 `app://` 开头的 renderer 发送脚本。脚本会在当前增强启动会话中扩展插件列表、修复安装请求和绕过已知市场过滤；若 CDP 超时或脚本发送失败，界面会明确区分“Codex 已启动”与“增强已生效”。

插件市场逻辑是独立的行为级实现，仅参考 [BigPizzaV3/CodexPlusPlus](https://github.com/BigPizzaV3/CodexPlusPlus) 的公开行为，不复制其 AGPL 源码、资源或快照。

## 开发

要求 Python 3.12 或更高版本。

```powershell
python -m pip install -e .[dev]
python -m llanfeng_code_assistant
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
```

### Windows 打包

```powershell
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1 -SkipAppBuild
```

完整工具链、缓存修复和故障排查见 [docs/packaging.md](docs/packaging.md)。版本发布步骤见 [CHANGELOG.md](CHANGELOG.md)。

## 主要目录

```text
llanfeng_code/
├── main.py
├── src/llanfeng_code_assistant/
│   ├── app.py                       # 五操作 Flet 协调器
│   ├── installer.py                 # Codex / Claude CLI 与前置安装
│   ├── codex_config_restorer.py     # 安全配置恢复、备份与回滚
│   ├── codex_statsig_unlocker.py    # bundled catalog 与持久模型白名单
│   ├── codex_desktop_launcher.py    # Store Codex、CDP 与 renderer 验证
│   ├── codex_plugin_marketplace.py  # 插件市场兼容脚本
│   ├── updater.py                   # 软件内更新
│   └── update_banner.py             # 项目级更新横幅
├── scripts/                         # Windows 应用与安装包构建脚本
├── tests/                           # 聚焦单元与回归测试
├── Codex.md                         # 用户提供的 Codex 技术参考
└── pyproject.toml
```

## 关于

- 创作者：岚风科技
- 技术支持 QQ：2235359588
- 项目地址：[github.com/McXiao1/llanfeng_code](https://github.com/McXiao1/llanfeng_code)

---

<div align="center">
<sub>© 2026 岚风科技 · 用心做工具</sub>
</div>
