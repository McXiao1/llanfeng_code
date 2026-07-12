# 安装与 Codex 增强全面重构 - Evidence

## 验收映射

### 1. 移除配置列表及相关功能

- `src/llanfeng_code_assistant/config/`、`storage.py`、`secrets.py`、
  `models.py`、`model_fetcher.py`、配置写入器与对应测试均已删除。
- `app.py` 不再持有 profile repository、secret store、model fetcher 或
  provider CRUD；UI 只编排四个主操作与状态/更新支持。
- 运行时依赖不再包含 `tomlkit`、`pydantic`、`keyring`。
- live-runtime identifier scan 结果：`NO_LIVE_RUNTIME_MATCHES`。

### 2. 只保留 Codex / Claude 一键安装

- `InstallerService` 只构造固定版本 Codex 与 Claude CLI 安装命令及 Node/Git
  前置安装流程。
- `tests/test_installer.py` 与 UI 回归测试覆盖目标命令、busy 状态和错误恢复。
- 主界面保留 `安装/更新 Codex` 与 `安装/更新 Claude`，无 provider 配置入口。

### 3. 移除协议文档、解析与注册

- `docs/protocol.md`、`deeplink.py`、`protocol_document.py`、协议入口参数与旧
  Inno Setup `[Registry]` block 已删除。
- `scripts/installer.iss` scan 结果：`INSTALLER_PROTOCOL_FREE`。
- 旧静默注入入口 `assets/codex-plugin.vbs` 也已删除，不再携带
  `LLANFENG_INJECT_MODE`。

### 4. 移除“新增”按钮

- 四操作 UI 的结构测试证明不再创建新增、编辑、删除、启用或协议文档控件。
- `tests/test_entrypoint_and_ui.py` 覆盖四个主按钮、状态刷新、确认流程和更新横幅。

### 5. 解锁未渲染模型并加入白名单

- 候选模型唯一来源为 `codex debug models --bundled`。
- 只接收非空 `slug`、显式 `visibility == "list"` 且
  `supported_in_api is not False` 的模型；缺少 `visibility` 不再默认可见。
- Statsig mutation 只追加缺失模型，保留 `default_model`、原顺序与未知字段，
  仅在真实写入前创建备份。
- strict visibility 回归：先复现缺失字段被误解锁的失败，再修复；
  `tests/test_codex_statsig_unlocker.py` 共 19 项通过。

### 6. 解锁插件市场

- `codex_desktop_launcher.py` 只负责 Microsoft Store Codex、loopback CDP、
  `app://` renderer 验证和脚本投递。
- `codex_plugin_marketplace.py` 独立负责插件列表、安装请求与过滤兼容行为。
- 行为级实现仅参考 CodexPlusPlus 的公开行为，没有复制 AGPL 源码、资源、
  插件快照或设置界面。
- launcher 与 marketplace 聚焦测试覆盖正常、超时、部分启动、错误响应和脚本行为。

## Fresh 自动化验证

```text
python -m pytest -q
94 passed in 2.13s

python -m ruff check src tests
All checks passed!

python -m compileall -q src
exit 0

python -m llanfeng_code_assistant --version
1.2.0

git diff --check
exit 0
```

PowerShell parser 对 `scripts/build_windows.ps1` 返回 `POWERSHELL_PARSE_OK`。

## 退役与复杂度证据

```text
HEAD:    39 Python files / 9,549 physical lines
Current: 25 Python files / 5,305 physical lines
Delta:   -4,244 lines
Limit:   every maintained Python file < 2,000 lines
```

- source/test 范围仍是 19 个 legacy Python 文件删除、5 个聚焦 owner/test 文件新增；
  此外删除了 `assets/codex-plugin.vbs`。
- 最大文件：`codex_statsig_unlocker.py` 660 行、`app.py` 645 行、
  `codex_plugin_marketplace.py` 395 行、`codex_desktop_launcher.py` 387 行。
- `app.py`、launcher 与 unlocker 略高于计划中的近似软目标，但都远低于 2,000 行
  硬限制，且没有重新混入 profile/protocol owner。
- 所有批准退役路径检查结果：`ALL_RETIRED_PATHS_ABSENT`。

## Windows 构建与 archive 证据

普通沙箱无法写入 Flutter 用户缓存/锁，初始化命令超时；在批准的沙箱外构建中，
相同源码与脚本成功完成：

```text
Successfully built your Windows app!
build\windows

Inno Setup 6.7.3
Successful compile
```

构建前的最终审计发现旧 `app.zip` 会把整个工作区复制进去。根因是 Flet 0.85.3
默认只排除 `build`，项目未声明 app excludes/cleanup。修复后：

```text
app.zip entries: 16
roots: assets, main.py, src
required runtime files missing: 0
retired paths: 0
.pyc / __pycache__: 0
.egg-info: 0
.git / docs / scripts / tests: 0
strict raw_model.get("visibility"): present
legacy raw_model.get("visibility", "list"): absent
```

`pyproject.toml` 现在声明开发根排除与 app cleanup；`build_windows.ps1` 在每次构建后
执行运行时 allowlist/退役 denylist 审计，污染 archive 会直接构建失败。

### 最终 app archive

```text
Path: H:\Python\llanfeng_code\build\windows\data\flutter_assets\app\app.zip
Size: 40,700 bytes
SHA-256: A03147093E4A98DE709A7DB6342192F5020493B289FE1D4DB0C6CF1A185910E4
LastWriteTime: 2026-07-11 21:52:56
```

### 最终安装包

```text
Path: H:\Python\llanfeng_code\build\installer\Llanfeng-Code-Assistant-Setup-1.2.0.exe
Size: 28,765,830 bytes
SHA-256: AE9917C572C6A59052F741F04FFB5F4B6738F1227A75002E0C95F88846AC9223
LastWriteTime: 2026-07-11 22:00:12
```

`build/` 仍由 Git ignore，不进入源码提交。

## Windows npm.CMD 回归修复

- 本机 `shutil.which("npm")` 返回 `E:\nodejs\npm.CMD`。
- `subprocess.run(["npm", "--version"])` 可稳定复现 `FileNotFoundError` /
  `WinError 2`，而执行解析后的 `.CMD` 路径返回 `11.12.1`。
- `InstallerService` 的 registry/install 命令和 `ToolDetector` 的版本探针均改为
  执行已解析路径；继续保持 `shell=False`，未增加命令字符串拼接或 UI fallback。
- `app.zip` 中两个修复文件与工作区源码逐字节一致，新增 shim 回归测试后全量
  验证为 `94 passed`。
- 上述 22:00:12 安装包取代本文件较早 checkpoint/evidence snapshot 中的旧哈希；
  交付时不得复用旧产物。

## 打包 CLI 边界

Flet Windows runner 将任意非空参数解释为 developer-mode 连接参数，因此打包后的
`.exe --version` 不是受支持的 Python CLI 探针。版本证据使用
`python -m llanfeng_code_assistant --version`；打包证据使用构建结果、archive 审计、
文件存在性、大小和 SHA-256。没有为此平台边界增加运行时兼容分支。

## 架构与基线

- `docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md`
  记录四 owner、delete-first 退役和数据保护边界。
- `docs/aegis/baseline/2026-07-11-post-refactor-baseline.md` 已同步当前产品与
  runtime 边界。
- Alignment result: `aligned`; scope: `both`。

## 未覆盖范围

自动化与本机构建未执行：

- 对真实用户 Codex Statsig LevelDB 的写入；
- 真实账号/实时 Codex renderer 下的插件市场响应与安装；
- 完整交互式安装、卸载和 GUI walkthrough。

这些是明确的 release/manual-validation 风险，不是隐藏兼容 owner。真实用户
SQLite、Credential Manager、Codex/Claude 数据没有被读取、迁移或删除。

## EvidenceBundleDraft

- Artifact key: final-python-verification
- Type: test-output
- Source: python -m pytest -q; python -m ruff check src tests; python -m compileall -q src; python -m llanfeng_code_assistant --version; git diff --check
- Summary: Fresh closeout verification passed: 91 pytest tests, Ruff clean, compileall exit 0, version 1.2.0, diff check clean, and PowerShell build script parses.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: clean-flet-app-archive
- Type: artifact-audit
- Source: build/windows/data/flutter_assets/app/app.zip
- Summary: Final app.zip has 16 entries and only assets/main.py/src roots; required runtime owners are present; retired modules, old VBS, development roots, pyc, __pycache__, and egg-info have zero hits. Size 40,427 bytes; SHA-256 32ADE74C6814A6CE12C0E0BEEBC58286CCDF411271833756060D5F628AA3A781.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: final-windows-installer
- Type: build-output
- Source: scripts/build_windows.ps1; scripts/build_installer.ps1 -SkipAppBuild
- Summary: Flet Windows build and Inno Setup 6.7.3 compile succeeded. Installer is 28,764,892 bytes with SHA-256 2D3833CBB940724424592E9D4BD445E675C6C927F569D163126967E5E6AA3DC2.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: retirement-and-package-guard
- Type: repository-audit
- Source: runtime identifier scan; retired-path scan; installer scan; build archive allowlist
- Summary: No live runtime legacy identifiers remain, every approved retired path including assets/codex-plugin.vbs is absent, installer protocol registration is absent, removed dependencies are absent, and future contaminated app archives fail the build.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: complexity-closure
- Type: repository-audit
- Source: HEAD/current Python line-count comparison and maintained-file limit scan
- Summary: Current src/tests contain 25 Python files and 5,243 physical lines versus 39 files and 9,549 lines at HEAD: 19 legacy Python files deleted, 5 focused source/test files added, net -4,306 lines. Every maintained Python file is below 2,000 lines.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: windows-npm-cmd-root-cause
- Type: diagnostic-output
- Source: shutil.which + subprocess reproduction on Windows
- Summary: On this host shutil.which("npm") resolves E:\nodejs\npm.CMD; subprocess.run(["npm", "--version"]) raises FileNotFoundError WinError 2 while subprocess.run([resolved_path, "--version"]) succeeds with npm 11.12.1. Root cause is executing the bare npm name instead of the resolved Windows command shim.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: windows-npm-cmd-regression
- Type: test-output
- Source: python -m pytest -q; python -m ruff check src tests; python -m compileall -q src; ToolDetector and InstallerService host probes
- Summary: Fresh verification passed: 94 pytest tests in 2.13s, Ruff clean, compileall exit 0, version 1.2.0, ToolDetector reports npm.CMD version 11.12.1, and InstallerService resolved-shim owner probe returns rc 0.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: windows-npm-cmd-refreshed-artifacts
- Type: artifact-audit
- Source: build/windows/data/flutter_assets/app/app.zip; build/installer/Llanfeng-Code-Assistant-Setup-1.2.0.exe
- Summary: Refreshed app.zip has 16 entries, packaged installer.py/environment.py exactly match workspace sources, required npm.CMD fix tokens are present, forbidden retired entries are zero, app.zip SHA-256 A03147093E4A98DE709A7DB6342192F5020493B289FE1D4DB0C6CF1A185910E4, and installer SHA-256 AE9917C572C6A59052F741F04FFB5F4B6738F1227A75002E0C95F88846AC9223.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: complexity-closure-after-npm-cmd-repair
- Type: repository-audit
- Source: current src/tests physical-line scan versus git HEAD
- Summary: Current src/tests contain 25 Python files and 5,305 physical lines versus 39 files and 9,549 lines at HEAD, a net reduction of 4,244 lines. The repair keeps installer.py at 207 lines and environment.py at 156 lines, adds no fallback owner, and every maintained Python file remains below 2,000 lines.
- Verifier: main-agent
