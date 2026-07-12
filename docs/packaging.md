# Windows 打包说明

本文档描述 Llanfeng Code Assistant 的 Windows 应用与 Inno Setup 安装包构建流程。当前产品只包含 Codex / Claude CLI 安装、Codex 模型白名单、安全配置恢复和插件市场增强，不包含 provider profile 或 URL scheme 集成。

## 构建输出

```text
build\windows\
build\installer\Llanfeng-Code-Assistant-Setup-<版本>.exe
```

Flet Windows 构建只能在 Windows 上执行。安装器使用 Inno Setup 6.7.3。

## 准备环境

### Python

建议使用 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### Flutter / Flet

首次构建可能下载 Flutter、Python runtime 与 Dart/Windows 构建缓存，因此需要可访问对应下载源的网络。

如果已有 Flet 管理的 Flutter，可通过参数或环境变量指定：

```powershell
$env:FLET_FLUTTER_BIN = "C:\Users\<用户>\flutter\3.41.7\bin"
```

### Visual Studio

安装 Visual Studio 2022 或 Build Tools，并勾选：

```text
Desktop development with C++
```

构建脚本通过 `vswhere.exe` 和组件
`Microsoft.VisualStudio.Component.VC.Tools.x86.x64` 检查工具链。Android SDK
相关 warning 不影响本项目，但 `Visual Studio - develop Windows apps` 缺失会阻断构建。

### Inno Setup

安装 Inno Setup **6.7.3**。默认编译器路径通常为：

```text
C:\Program Files (x86)\Inno Setup 6\ISCC.exe
```

项目会校验已安装版本，其他版本不会被静默接受。

## 打包前验证

```powershell
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
```

还应确认以下退役契约没有重新出现：

- provider profile / secret storage 模块；
- Codex / Claude settings writer；
- deep-link parser 与 installer registry block；
- 仅服务于已退役 profile 系统的运行时依赖。

## 运行时依赖

`pyproject.toml` 当前声明：

```text
certifi==2026.2.25
flet==0.85.3
httpx==0.28.1
websockets==16.0
chromium-reader==0.1.1
```

`websockets` 与 `chromium_reader` 还列在 `[tool.flet.app].packages` 中，避免
Flet 静态分析遗漏懒加载模块。`[tool.flet.app].exclude` 排除版本库、测试、文档、
构建脚本和开发缓存，`[tool.flet.cleanup]` 会清理 app archive 中的
`__pycache__`、`.pyc` 与 `.egg-info`。`scripts\build_windows.ps1` 会检查
`build\site-packages` 中的运行时目录；缓存不完整时删除
`build\.hash\package`，强制重新安装依赖。

## 软件图标

根目录 `LOGO.png` 与 `assets/icon.png` 必须保持一致。Flet 会从 `assets`
目录生成 Windows 图标资源：

```text
LOGO.png
assets/icon.png
```

替换品牌图标时同时更新两个文件，并运行 `tests/test_packaging_config.py`。

## 构建 Windows 应用

推荐命令：

```powershell
.\scripts\build_windows.ps1
```

指定 Flutter 目录：

```powershell
.\scripts\build_windows.ps1 `
  -FlutterBin "C:\Users\<用户>\flutter\3.41.7\bin"
```

脚本会：

1. 设置 PowerShell 与子进程 UTF-8 输出；
2. 检查 `main.py` 与 `assets\icon.png`；
3. 检查 Visual Studio C++ 工具链与 x64 VC runtime；
4. 运行 `scripts\patch_serious_python_windows.py`；
5. 清理 stale Windows CMake cache；
6. 清理缺少 `python.exe` 的 Flet Python runtime cache；
7. 检查运行时依赖缓存并按需强制重新安装；
8. 执行 `flet build windows -v --no-rich-output`；
9. 审计最终 `app.zip`，要求包含 `codex_config_restorer.py`，只允许 `main.py`、
   `assets/` 与 `src/llanfeng_code_assistant/`，并拒绝退役模块、旧 VBS、`.pyc` 和开发目录；
10. 检查最终包内 `certifi` 是否存在。

`serious_python_windows` patch 负责：

- 使用 Visual Studio 的 x64 runtime，而不是可能被 32 位进程重定向的
  `System32` 路径；
- 跳过会把 Windows 路径误解析成命令参数的可选 `DEL` 清理步骤；
- 优先复用 Flet 已下载的 `build_python_3.12.9\python`；
- 对 Python runtime 下载失败给出明确错误。

Flet 入口由以下配置声明：

```toml
[tool.flet.app]
module = "main.py"
packages = ["websockets", "chromium_reader"]
exclude = [".git", "docs", "scripts", "tests"] # 完整列表见 pyproject.toml

[tool.flet.cleanup]
app = true
app_files = ["**.egg-info", "**.pyc"]
```

## 构建安装包

同时构建应用和安装器：

```powershell
.\scripts\build_installer.ps1
```

复用已经验证的 `build\windows`：

```powershell
.\scripts\build_installer.ps1 -SkipAppBuild
```

显式指定 Inno Setup：

```powershell
.\scripts\build_installer.ps1 `
  -SkipAppBuild `
  -InnoSetupCompiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

脚本从 `pyproject.toml` 读取版本，确认应用 exe、图标、Inno script 与输出
文件均存在。安装器采用当前用户范围，默认安装到：

```text
%LOCALAPPDATA%\Programs\Llanfeng Code Assistant
```

它只创建开始菜单快捷方式和可选桌面快捷方式，不写入 scheme 或其他
shell integration registry keys。

## 常见问题

### `app/app.zip was not created`

如果日志显示从 GitHub 下载 Python runtime 超时，失败点位于 Flet /
`serious_python` 的外部下载，不是 `main.py`。检查网络或代理后重试：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
.\scripts\build_windows.ps1
```

端口按本机代理调整。

### Flutter PATH 不一致

确保 Flet 使用的 Flutter `bin` 位于 PATH 前部，或直接传 `-FlutterBin`。
不要混用多个 Flutter checkout 的 cache。

### Visual Studio 缺失

若 `flutter doctor` 显示：

```text
[X] Visual Studio - develop Windows apps
```

安装 `Microsoft.VisualStudio.Workload.VCTools`，重新打开 PowerShell 后再构建。

### `ModuleNotFoundError: No module named 'certifi'`

说明 Flet dependency cache 不完整。确认 `pyproject.toml` 仍声明固定版本的
`certifi`，然后运行：

```powershell
.\scripts\build_windows.ps1
```

脚本会在检测到缺包时清理 dependency hash。

### `WinError 5`

关闭正在运行的 `llanfeng-code-assistant.exe`。应用或 DLL 被占用时，Flet
无法覆盖 `build\windows` 中的旧文件。

## 产物验证

构建后至少执行：

```powershell
python -m llanfeng_code_assistant --version
Test-Path .\build\windows\llanfeng-code-assistant.exe
Get-FileHash .\build\installer\Llanfeng-Code-Assistant-Setup-<版本>.exe -Algorithm SHA256
```

Flet 生成的 Windows runner 会将非空启动参数解释为开发模式连接参数，不能用
打包后的 `.exe --version` 验证 Python 入口；该命令不会把 `--version` 透传给
应用模块。版本检查应使用上面的源码入口，打包产物则通过构建结果、文件存在性、
应用归档内容和手动 GUI 启动检查验证。构建脚本会自动拒绝 app archive
中的开发目录、退役实现和派生缓存；发布时仍应记录 archive 的条目数与 hash。

然后手动检查：

1. 主界面显示五个主要操作；
2. Codex / Claude 安装按钮能恢复 busy 状态；
3. 模型解锁在 Codex 运行时先请求确认；
4. 恢复配置明确保留 `auth.json`，并在 Codex 运行时先请求确认；
5. 增强启动能区分“进程已启动”和“市场增强已生效”；
6. 安装与卸载后没有新增 scheme registry key。

不要把历史产物的文件大小、hash 或内含文件列表当作当前 release 证据；每次
发布都应从本次构建产物重新采集。

## 发布检查清单

- `pyproject.toml` 与 `src/llanfeng_code_assistant/__init__.py` 版本一致；
- 全量 pytest、Ruff、compileall 和源码入口 `--version` 通过；
- Windows 应用构建成功；
- Inno Setup 6.7.3 安装包构建成功；
- 对当前安装包重新计算 SHA-256；
- GitHub Release 上传的文件名与版本一致；
- 更新日志准确描述 breaking changes 与残余限制。
