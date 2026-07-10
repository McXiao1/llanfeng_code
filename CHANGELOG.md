# 更新日志 (Changelog)

版本格式遵循 [语义化版本](https://semver.org/lang/zh-CN/)：`主版本.次版本.补丁号`

---

## [1.1.0] - 2026-07-10

### 新增
- **注入启动按钮**：移至顶栏最右侧，与「新增」同层；点击后自动写入配置并以 CDP 增强模式启动 ChatGPT Desktop
- **推理强度新增 xhigh / ultra 两档**：模型选择器现支持完整 5 档 — `low / medium / high / xhigh / ultra`
- **微软商店路径自动发现**：`find_chatgpt_exe()` 通过 `Get-AppxPackage -Name "OpenAI.Codex"` 动态查找安装位置（`app\ChatGPT.exe`），不再依赖固定路径；npm 安装版本保留为兜底

### 修复
- **CDP 注入崩溃**（三处关键 Bug）：
  - `Array.prototype.filter` 补丁在检测阶段调用了原始回调 `!cb(p)`，导致 React 渲染期间抛出异常、App 白屏；改为仅检查回调源码文本和数组元素结构，绝不执行回调
  - `patchModelArray` 向任意非空数组 push 模型描述符，破坏 React fiber 内部状态；新增 `modelArrayLooksPatchable` 守卫，仅对全部元素含 `model: string` 的数组执行注入
  - `walkFiber` + MutationObserver 遍历整个 React 对象图并调用 `patchModelPayload`，必然损坏 React 内部；已完全移除，改由 Statsig 内存补丁 + `Response.prototype.json` 两层覆盖
- **模型下拉显示"自定义"**：`config.toml` 中 `model` 字段写入的是显示名而非 catalog slug，导致 Codex 匹配不到；启用时自动将 `model` 对齐到第一个匹配的 catalog slug
- **内置最新模型列表消失**：错误地在 `codex_models` 为空时自动合成单条 catalog，替换了 Codex 内置模型列表；改为仅在用户显式配置了模型列表时才写入 `model_catalog_json`
- **catalog 字段名错误**：`default_reasoning_level` / `supported_reasoning_levels` 被误改为 `default_reasoning_effort` / `reasoning_effort`；已恢复为 Codex 规范字段名
- **catalog 缺少必填字段**：补齐 `apply_patch_tool_type`、`supports_search_tool`、`default_verbosity`、`input_modalities`、`service_tiers`、`availability_nux`、`upgrade`、`max_context_window`，防止 Codex 静默丢弃整个 catalog
- **`truncation_policy.limit` 硬编码**：移出共享常量，改为按每个模型的 `context_window` 动态生成
- **Statsig 模型白名单修复**：之前错误地删除 `available_models` 字段；正确做法是把自定义模型名**加进**白名单（参考 CodexPlusPlus `patchStatsigModelDynamicConfig`）
- **打包后注入启动按钮消失**：`import websockets` 位于模块顶层，打包工具无法通过静态分析识别，导致模块加载失败、按钮不渲染；改为在 `inject_scripts()` 内部懒加载；`pyproject.toml` 同步新增 `packages = ["websockets"]` 确保打包工具强制纳入

### 变更
- CDP 注入脚本重构（对齐 [CodexPlusPlus renderer-inject.js](https://github.com/BigPizzaV3/CodexPlusPlus/blob/main/assets/inject/renderer-inject.js)）：
  - 新增 Statsig in-memory 补丁（拦截 `getDynamicConfig("107580212")`，含 `window.__STATSIG__` setter 监听）
  - 新增 `Response.prototype.json` 全局补丁（带 `modelArrayLooksPatchable` 守卫）
  - 新增 MCP dispatchEvent 补丁（model/list 请求加 `includeHidden: true`）
  - 新增 Statsig 快速启动补丁（800 ms 超时防止 App 卡顿）
  - 插件市场解锁改为基于 `electronBridge.sendMessageFromView` + `Array.prototype.filter` 源码检测

---

## [1.0.0] - 2026-07-10

### 新增
- 首次正式发布
- 支持 Codex 和 Claude 多配置管理（新增、编辑、删除、启用）
- Windows 一键安装程序（Inno Setup 打包）
- `llanfeng-code://` URL 协议深链接导入配置
- Codex Desktop CDP 注入增强启动（插件市场解锁 + 模型白名单）
- 应用顶部标题展示当前版本号
- 启动时自动检测新版本，发现更新后展示横幅并支持一键下载安装

---

## 版本号规则

| 变更类型 | 版本递进 | 示例 |
|----------|----------|------|
| 重大功能更新 / 不兼容变更 | MAJOR + 1 | `1.0.0` → `2.0.0` |
| 新功能（向后兼容） | MINOR + 1 | `1.0.0` → `1.1.0` |
| Bug 修复 / 小调整 | PATCH + 1 | `1.0.0` → `1.0.1` |

---

## 发布流程

### 1. 修改版本号（两处需保持一致）

```
pyproject.toml                              → version = "X.Y.Z"
src/llanfeng_code_assistant/__init__.py     → __version__ = "X.Y.Z"
```

### 2. 在本文件顶部添加新版本日志

```markdown
## [X.Y.Z] - YYYY-MM-DD

### 新增
- ...

### 修复
- ...

### 变更
- ...
```

### 3. 提交并推送到 GitHub

```powershell
git add pyproject.toml src/llanfeng_code_assistant/__init__.py CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

### 4. 构建安装包

```powershell
.\scripts\build_installer.ps1
# 输出：build\installer\Llanfeng-Code-Assistant-Setup-X.Y.Z.exe
```

### 5. 在 GitHub 创建 Release

1. 打开 `https://github.com/McXiao1/llanfeng_code/releases/new`
2. Tag 填写 `vX.Y.Z`（与步骤 3 的 tag 一致）
3. Title 填写 `Llanfeng Code Assistant vX.Y.Z`
4. 将 `build\installer\Llanfeng-Code-Assistant-Setup-X.Y.Z.exe` 上传为 Release Asset
5. 将本文件对应版本的更新内容粘贴到 Release Notes
6. 点击 **Publish release**

> 发布完成后，已在运行的 APP 会在下次启动时通过 GitHub Releases API 检测到新版本，
> 并在顶部展示「发现新版本」横幅，用户点击「下载安装」即可跳转到安装包下载。
