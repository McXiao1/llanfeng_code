# 打包说明

本文档记录 Windows 桌面端 APP 的本地打包指令。Flet 官方当前推荐使用 `flet build windows` 生成 Windows 应用；该命令只能在 Windows 上执行。

## 准备环境

建议使用 Python 3.12，并在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

首次执行 Flet 打包时可能需要下载 Flutter/构建缓存，机器需要可访问网络。

Windows 桌面打包还必须安装 Visual Studio 2022 或 Build Tools，并勾选：

```text
Desktop development with C++
```

`flutter doctor` 里的 Android toolchain 报警只影响 Android APK/AAB 构建；本项目只打 Windows 桌面端时可以忽略 Android SDK 和 Android license。`Visual Studio - develop Windows apps` 不能忽略，缺少它会导致 Windows app 构建失败。

## 打包前验证

```powershell
ruff check . --no-cache
python -m pytest -q -p no:cacheprovider
python -m compileall src
python -m llanfeng_code_assistant --version
```

## 软件图标

Flet 0.85 会从项目的 `assets` 目录自动扫描图标资源。Windows 构建会优先使用 `assets/icon_windows.*`，没有平台专用图标时会回退到 `assets/icon.*`。

本项目已经把根目录的 `LOGO.png` 复制为：

```text
assets/icon.png
```

因此正常执行 `flet build windows` 时会把该图片作为应用图标生成到 Windows 产物里。如果后续替换品牌图标，请同时更新 `LOGO.png` 和 `assets/icon.png`，保持两个文件内容一致。

## Flet Windows 打包

推荐使用项目内置脚本，它会先检查 `main.py`、`assets/icon.png`、Flet Flutter PATH 和 Visual Studio C++ 桌面工具链：

```powershell
.\scripts\build_windows.ps1
```

脚本还会自动修补 `serious_python_windows` 1.0.1 的 Windows CMake 配置：

- 设置 PowerShell/子进程为 UTF-8，避免 Flet CLI 或 Flutter 插件在中文 GBK 控制台输出 Unicode 字符时抛出 `UnicodeEncodeError`。
- 使用 Visual Studio Build Tools 的 x64 VC runtime redist 目录，避免 32 位 CMake 从 `System32` 解析到 x86 runtime。
- 跳过插件中基于 `DEL H:/... /Q` 的可选清理命令，避免 Windows `cmd` 把路径里的 `/Python` 当成参数开关。
- 让 `serious_python_windows` 优先复用 Flet 依赖打包阶段已下载的 `build_python_3.12.9\python`，避免 `python-windows-for-dart.zip` 被下载成 0 字节后继续构建。
- 清理 `build\flutter\build\windows` 后重新生成 CMake 缓存。
- 删除缺少 `python\python.exe` 的 `build\flutter\build\build_python_3.12.9` 坏缓存，避免 serious_python 跳过重新下载/解压 Python 后又无法执行 pip。
- 检查 `build\site-packages` 运行时依赖缓存，缺少 `certifi`、`flet`、`httpx` 等关键包时删除 `build\.hash\package`，强制 Flet 重新安装 Python 依赖。
- 构建完成后检查 `build\windows\site-packages\certifi` 是否存在，避免输出启动即崩溃的 exe。

如果需要指定 Flet 使用的 Flutter 目录，可以执行：

```powershell
.\scripts\build_windows.ps1 -FlutterBin "C:\Users\22353\flutter\3.41.7\bin"
```

脚本内部最终执行的 Flet 命令是：

```powershell
flet build windows -v --no-rich-output
```

项目已经在 `pyproject.toml` 中声明 Flet 入口：

```toml
[tool.flet.app]
module = "main.py"
```

根目录也提供了 `main.py`，因此不需要额外传 `--module-name`。如果要显式指定，也可以执行：

```powershell
flet build windows -v --no-rich-output --module-name main.py
```

构建完成后，产物通常位于：

```text
build\windows\
```

如果需要清理旧产物后重新打包，可以手动删除 `build\windows\` 后再执行 `flet build windows -v`。

## 常见打包问题

### `app/app.zip was not created`

如果日志里出现类似内容：

```text
Downloading Python distributive from
https://github.com/astral-sh/python-build-standalone/releases/download/...
Error: ClientException: 信号灯超时时间已到
Flet app package app/app.zip was not created.
```

说明当前失败点是 `serious_python` 从 GitHub 下载 Windows Python 运行时超时，不是 `main.py` 入口问题。处理方式：

1. 确认网络、代理或 VPN 能访问 GitHub。
2. 重新执行 `flet build windows -v --no-rich-output`。
3. 如果需要在当前 PowerShell 会话里指定代理，可以先设置：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
flet build windows -v --no-rich-output
```

其中端口请按本机代理实际配置调整。

### Flutter PATH 不一致

如果 `flutter doctor` 提示：

```text
flutter on your path resolves to C:\flutter\bin\flutter
current Flutter SDK checkout at C:\Users\22353\flutter\3.41.7
```

把当前 Flet 下载的 Flutter 放到 PATH 前面，至少在当前 PowerShell 会话中执行：

```powershell
$env:Path = "C:\Users\22353\flutter\3.41.7\bin;$env:Path"
```

要永久生效，请在 Windows 环境变量里把 `C:\Users\22353\flutter\3.41.7\bin` 移到 `C:\flutter\bin` 前面。

### Visual Studio 缺失

如果 `flutter doctor` 仍显示：

```text
[X] Visual Studio - develop Windows apps
```

需要安装 Visual Studio 2022 或 Build Tools，并勾选 `Desktop development with C++`。这个问题不能忽略，否则即使 Python 运行时下载成功，Windows 桌面产物也会在后续 Flutter 构建阶段失败。

可以通过 Visual Studio Installer 安装，也可以下载 Visual Studio Build Tools 后安装以下 workload：

```text
Microsoft.VisualStudio.Workload.VCTools
```

脚本会用 `Microsoft.VisualStudio.Component.VC.Tools.x86.x64` 组件检测 C++ 工具链是否安装成功。

安装完成后重新打开 PowerShell，再执行：

```powershell
.\scripts\build_windows.ps1
```

### `ModuleNotFoundError: No module named 'certifi'`

Flet 生成的 Python 启动代码会在进入本项目应用前先 `import certifi`，用于设置 HTTPS CA 证书路径。如果打包后的 exe 启动时报：

```text
ModuleNotFoundError: No module named 'certifi'
```

说明 `build\site-packages` 依赖缓存不完整，或者构建时复用了旧的 package hash。确认 `pyproject.toml` 里包含：

```toml
"certifi==2026.2.25"
```

然后重新执行：

```powershell
.\scripts\build_windows.ps1
```

## 生成安装包 EXE

项目使用 Inno Setup 6.7.3 把 `build\windows` 下的完整 Flet 产物封装为单一安装包 EXE。请先从 Inno Setup 官方网站安装 6.7.3；项目脚本不会自动下载或安装外部工具。

默认同时构建 Windows 应用和安装器：

```powershell
.\scripts\build_installer.ps1
```

如果 `build\windows` 已经通过验证，可跳过 Flet 构建：

```powershell
.\scripts\build_installer.ps1 -SkipAppBuild
```

也可以显式指定编译器：

```powershell
.\scripts\build_installer.ps1 `
  -SkipAppBuild `
  -InnoSetupCompiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

脚本从 `pyproject.toml` 读取版本号，安装包输出到：

```text
build\installer\Llanfeng-Code-Assistant-Setup-<版本>.exe
```

安装器固定采用当前用户范围，不需要管理员权限，默认安装到 Local AppData，并创建开始菜单快捷方式；桌面快捷方式为可选项。

## 本次实际打包记录（2026-07-10）

本机已经安装并验证：

```text
Inno Setup version 6.7.3
C:\Program Files (x86)\Inno Setup 6\ISCC.exe
```

本次先使用最新源码重新构建 Flet Windows 应用：

```powershell
.\scripts\build_windows.ps1
```

构建成功后，再复用 `build\windows` 产物编译安装包：

```powershell
.\scripts\build_installer.ps1 -SkipAppBuild
```

最终产物：

```text
build\installer\Llanfeng-Code-Assistant-Setup-0.1.0.exe
```

产物校验信息：

```text
文件大小：30,694,413 bytes（29.27 MB）
SHA-256：CD6A8EFE342DC734DA1C685B5CADFD7AEAA06FFD0BDEB8ECABEF11609E3F8501
构建时间：2026-07-10 18:24:37（Asia/Shanghai）
```

同时确认最新 Windows 应用包内包含：

```text
src/llanfeng_code_assistant/app.py
src/llanfeng_code_assistant/protocol_document.py
```

这表示最终安装包已经包含“协议文档”按钮及 Web 对接文档改造，而不是复用改造前的旧应用代码。

### 本次遇到的问题

首次重新构建时，已运行的 `llanfeng-code-assistant.exe` 占用了
`build\windows` 中的 DLL，导致 Flet 在覆盖旧产物时出现 `WinError 5`。关闭正在运行的应用后重新执行构建即可。

Inno Setup 6.7.3 默认安装不包含 `ChineseSimplified.isl`，因此当前安装器使用 Inno Setup 内置英文安装界面；应用本身的中文界面不受影响。如后续需要中文安装向导，需要额外提供并维护兼容 6.7.3 的简体中文语言文件。

## 协议自动注册

安装器会在当前用户的 `HKCU\Software\Classes` 下自动注册：

```text
llanfeng-code://
```

协议启动命令直接指向安装目录中的 `llanfeng-code-assistant.exe`，并通过 `--import-url "%1"` 传递完整链接。卸载时会删除安装器创建的协议注册表项。

直接运行开发源码不会注册协议。Web 端可以按 [protocol.md](protocol.md) 的格式唤起已安装应用并导入配置；桌面应用顶部的“协议文档”按钮也会显示完整对接说明。

## 注意事项

- 当前项目只面向 Windows 桌面端。
- 打包前确认 `pyproject.toml` 中版本号已经更新。
- 如果再次看到 `main.py not found in the root of Flet app directory`，确认命令是在项目根目录 `H:\Python\llanfeng_code` 下执行。
- 若需要自定义公司名称或安装包元数据，应优先查 Flet 当前发布文档后再添加对应参数。

