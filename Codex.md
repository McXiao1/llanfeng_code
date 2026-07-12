# Codex 模型选择器解锁 gpt-5.6-sol 指南

## 问题

Codex 模型选择器中看不到 `gpt-5.6-sol`，只能看到 GPT-5.5、GPT-5.4、GPT-5.4 Mini、GPT-5.2。

## 根因

Codex 的模型列表由 **Statsig 动态配置 `107580212`** 控制，该配置包含三个关键字段：

| 字段 | 作用 | 旧值 |
|------|------|------|
| `available_models` | 白名单，只有其中的模型才在 UI 显示 | `["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5.2"]` |
| `use_hidden_models` | 是否启用白名单过滤 | `true` |
| `default_model` | 默认选中模型 | `"gpt-5.4"` |

`available_models` 缺少 `gpt-5.6-sol` 和 `gpt-5.6`，前端 JS 在渲染选择器前按白名单过滤掉了它们。

后端（`codex-code-mode-host`）本身返回全部 8 个模型（含 gpt-5.6-sol，`hidden=false`），但前端不展示。

## 方案选择

有两种方式可以绕过白名单：

| 方案 | 做法 | 可行性 |
|------|------|--------|
| 修改 `app.asar` 中 JS | 改 `model-list-filter-C2SM1X_9.js`，绕过 `availableModels` 检查 | **不可行** — `app.asar` 在 `C:\Program Files\WindowsApps\...`，受强制完整性控制 (MIC) 保护，无法写入 |
| 修改 webview localStorage | 直接改 Statsig 缓存中 `available_models` 的值 | **可行** — LevelDB 在用户 AppData 目录，无权限问题 |

## 原理

Statsig SDK 将配置缓存在 Chromium 的 LevelDB localStorage 中：

```
%LOCALAPPDATA%\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Roaming\Codex\web\Codex\Default\Local Storage\leveldb\
```

缓存结构：

- **Key**：`_app://-\x00\x01statsig.cached.evaluations.{hash}`
- **Value**：`0x00` 类型前缀 + UTF-16LE 编码的 JSON
- **JSON 路径**：`dynamic_configs["107580212"].value`

修改目标：在 `available_models` 数组中追加 `"gpt-5.6-sol"` 和 `"gpt-5.6"`，同时可把 `default_model` 改为 `"gpt-5.6-sol"`。

## 操作步骤

### 1. 关闭 Codex

LevelDB 在 Codex 运行期间被锁定，必须完全退出。

### 2. 安装依赖

```bash
mkdir leveldb-tool && cd leveldb-tool
npm init -y
npm install classic-level
```

### 3. 运行修改脚本

将以下内容保存为 `modify-eval.js`：

```javascript
const { ClassicLevel } = require('classic-level');

const dbPath = process.env.LOCALAPPDATA +
  '/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Roaming/Codex/web/Codex/Default/Local Storage/leveldb';

// 要添加到白名单的模型
const MODELS_TO_ADD = ['gpt-5.6-sol', 'gpt-5.6'];
const NEW_DEFAULT = 'gpt-5.6-sol';

async function main() {
  const db = new ClassicLevel(dbPath, { keyEncoding: 'utf8', valueEncoding: 'buffer' });
  await db.open();

  // 找到 evaluations 缓存 key
  const lmtKey = '_app://-\x00\x01statsig.last_modified_time.evaluations';
  const lmtRaw = await db.get(lmtKey);
  const lmtData = JSON.parse(lmtRaw.slice(1).toString('utf8'));
  const evalHashes = Object.keys(lmtData).filter(k => k.startsWith('statsig.cached.evaluations.'));

  for (const hash of evalHashes) {
    const evalKey = '_app://-\x00\x01' + hash;
    console.log(`Processing: ${hash}`);

    // 读取并解码
    const raw = await db.get(evalKey);
    const jsonStr = raw.slice(1).toString('utf16le');
    const outer = JSON.parse(jsonStr);
    const data = JSON.parse(outer.data);

    // 修改 config 107580212
    const cfg = data.dynamic_configs['107580212'];
    if (!cfg || !cfg.value) {
      console.log('  Config 107580212 not found, skipping');
      continue;
    }

    const val = cfg.value;
    let changed = false;
    for (const m of MODELS_TO_ADD) {
      if (!val.available_models.includes(m)) {
        val.available_models.push(m);
        changed = true;
        console.log(`  Added: ${m}`);
      }
    }
    if (val.default_model !== NEW_DEFAULT) {
      val.default_model = NEW_DEFAULT;
      changed = true;
      console.log(`  Changed default_model to: ${NEW_DEFAULT}`);
    }

    if (changed) {
      // 重新编码
      cfg.value = val;
      outer.data = JSON.stringify(data);
      const newJsonStr = JSON.stringify(outer);
      const prefix = Buffer.from([0x00]);
      const utf16le = Buffer.from(newJsonStr, 'utf16le');
      await db.put(evalKey, Buffer.concat([prefix, utf16le]));

      // 更新时间戳
      lmtData[hash] = Date.now();
      await db.put(lmtKey, Buffer.from('\x01' + JSON.stringify(lmtData), 'utf8'));
      console.log('  Written OK');
    } else {
      console.log('  Already correct, skipping');
    }
  }

  await db.close();
  console.log('\nDone! Start Codex and gpt-5.6-sol should appear.');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
```

然后运行：

```bash
node modify-eval.js
```

### 4. 启动 Codex 验证

重启 Codex，点开模型选择器，应能看到 gpt-5.6-sol。

## 注意事项

- 操作前必须完全关闭 Codex，否则 LevelDB 锁定报错 `LEVEL_LOCKED`
- Codex 大版本更新或重装后，LevelDB 会被重置，需要重新运行脚本
- 备份建议：操作前复制整个 `leveldb` 目录作为备份
- 路径中的 `OpenAI.Codex_2p2nqsd0c76g0` 可能因版本不同而变化，请根据实际路径调整
