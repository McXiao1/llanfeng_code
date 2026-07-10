<div align="center">

# Llanfeng Code Assistant

**Codex / Claude 一键配置工具**

Windows 桌面助手，帮助开发者快速安装、配置并切换 Codex 与 Claude Code 的 API 上游。

[![Version](https://img.shields.io/github/v/release/McXiao1/llanfeng_code?label=版本&color=4A90E2)](https://github.com/McXiao1/llanfeng_code/releases/latest)
[![Platform](https://img.shields.io/badge/平台-Windows-0078D4)](https://github.com/McXiao1/llanfeng_code/releases/latest)
[![License](https://img.shields.io/badge/许可-MIT-green)](#)

</div>

---

## 简介

**Llanfeng Code Assistant** 是一款专为 Windows 开发者设计的桌面工具，旨在解决 Codex 与 Claude Code 在国内使用中配置繁琐、API 上游难以切换的问题。

通过图形界面即可完成以下全部操作，无需手动编辑配置文件：

- 配置并管理多个 API 上游（代理 / 自定义端点）
- 一键切换 Codex 或 Claude Code 的激活配置
- 安装 Codex CLI / Claude Code CLI
- 以 CDP 增强模式启动 Codex Desktop（解锁插件市场 + 注入模型白名单）
- 通过 `llanfeng-code://` 协议链接快速导入他人分享的配置

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 多配置管理 | 为 Codex 和 Claude Code 各自维护多套 API 配置，随时切换 |
| 模型选择 | 自动获取上游支持的模型列表，下拉选择 |
| 一键安装 | 检测 Node.js / Git 环境，引导安装 Codex CLI 或 Claude Code CLI |
| 注入启动 | CDP 模式启动 ChatGPT Desktop，解锁插件市场并注入模型白名单 |
| 深链接导入 | 通过 `llanfeng-code://` 链接一键导入配置，方便团队共享 |
| 自动更新 | 启动时静默检测新版本，发现更新后横幅提示并支持一键下载安装 |
| API Key 安全存储 | 密钥通过 Windows Credential Manager 加密存储，不明文写入文件 |

---

## 安装

### 直接安装（推荐）

1. 前往 [Releases 页面](https://github.com/McXiao1/llanfeng_code/releases/latest) 下载最新版
2. 运行 `Llanfeng-Code-Assistant-Setup-x.y.z.exe`
3. 按向导完成安装，桌面可选创建快捷方式

> 安装器不需要管理员权限，默认安装到当前用户目录。

### 系统要求

- Windows 10 / 11（64 位）
- 无需额外运行时，安装包已内置 Python 环境

---

## 使用说明

### 基本配置流程

1. 启动应用，顶部可查看 Node.js / npm / Git / Codex / Claude 的安装状态
2. 选择上方 **Codex** 或 **Claude** 标签页
3. 点击「**新增**」按钮，填写以下信息：
   - **名称**：便于识别的备注名
   - **URL**：API 端点地址（如 `https://api.openai.com/v1` 或代理地址）
   - **Key**：对应的 API Key
   - **模型**：手动填写或点击「获取模型」从上游自动拉取
4. 保存后点击「**启用**」，将该配置写入 Codex / Claude Code 的配置文件
5. 打开终端执行 `codex` 或 `claude` 即可使用

### Claude Code 多模型配置

Claude Code 支持为不同角色（Haiku / Sonnet / Fable / Opus）分别指定模型，编辑配置时展开对应字段填写即可。

### Codex Desktop 注入启动

1. 确保已从微软商店安装 **ChatGPT (OpenAI.Codex)**
2. 启用一个 Codex 配置
3. 点击顶部「**注入启动**」按钮
4. 应用将自动以 CDP 远程调试模式启动 Codex Desktop 并注入增强脚本

### 深链接导入

分享方在应用中复制导入链接（格式 `llanfeng-code://import?...`），接收方直接在浏览器或文件管理器中打开该链接即可触发应用导入对话框。

> 完整协议文档：点击应用内「协议文档」按钮查看，或参阅 [docs/protocol.md](docs/protocol.md)

---

## 开发

### 环境准备

```powershell
# 安装依赖（含开发工具）
python -m pip install -e .[dev]

# 运行应用
python -m llanfeng_code_assistant

# 运行测试
python -m pytest -q

# 代码检查
ruff check src tests
```

要求：Python 3.12+

### 打包发布

```powershell
# 构建 Windows 应用 + 安装包（需要 Inno Setup 6.7.3）
.\scripts\build_installer.ps1
```

输出：`build\installer\Llanfeng-Code-Assistant-Setup-{version}.exe`

详细打包说明参阅 [docs/packaging.md](docs/packaging.md)。

### 版本发布流程

参阅 [CHANGELOG.md](CHANGELOG.md) 中的发布流程章节。

---

## 目录结构

```
llanfeng_code/
├── src/llanfeng_code_assistant/   # 主程序源码
│   ├── app.py                     # UI 主控制器
│   ├── constants.py               # 全局常量
│   ├── updater.py                 # 自动更新检测
│   ├── installer.py               # CLI 安装逻辑
│   ├── config/                    # Codex / Claude 配置写入
│   └── ...
├── scripts/
│   ├── build_installer.ps1        # 打包脚本
│   └── installer.iss              # Inno Setup 配置
├── docs/                          # 补充文档
├── tests/                         # 单元测试
├── CHANGELOG.md                   # 版本更新日志
└── pyproject.toml                 # 项目元信息与依赖
```

---

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

---

## 关于

<table>
<tr>
<td><b>创作者</b></td>
<td>岚风科技</td>
</tr>
<tr>
<td><b>技术支持 QQ</b></td>
<td>2235359588</td>
</tr>
<tr>
<td><b>项目地址</b></td>
<td><a href="https://github.com/McXiao1/llanfeng_code">github.com/McXiao1/llanfeng_code</a></td>
</tr>
</table>

> 如遇问题或有功能建议，欢迎通过 QQ 联系或在 GitHub 提交 Issue。

---

<div align="center">
<sub>© 2026 岚风科技 · 用心做工具</sub>
</div>
