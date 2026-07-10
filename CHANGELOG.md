# 更新日志 (Changelog)

版本格式遵循 [语义化版本](https://semver.org/lang/zh-CN/)：`主版本.次版本.补丁号`

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
