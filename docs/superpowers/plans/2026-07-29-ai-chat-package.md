# 微信 AI 资料包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CLI 和 Web 增加可递归解析合并转发、离线转写微信 4.1 语音并用相对路径打包图片/表情/音频的 AI 资料包。

**Architecture:** 消息层只负责把微信数据库记录规范化为结构化消息；`forwarded.py`、`voice.py`、`asr.py` 分别隔离转发 XML、语音数据库/解码、模型下载/识别。`ai_package.py` 组合这些能力并生成稳定的 ZIP 与清单；CLI 命令和 localhost Web API 共用该服务，不各自复制业务逻辑。

**Tech Stack:** Python 3.10、Click、SQLite、ElementTree、urllib、zipfile、PyInstaller、原生 JavaScript、sherpa-onnx、SILK V3 decoder、unittest。

---

## 文件结构

- 新建 `wechat_cli/core/forwarded.py`：安全递归解析 `appmsg/type=19`。
- 新建 `wechat_cli/core/voice.py`：定位 `media_N.db`、读取 SILK、解码 WAV。
- 新建 `wechat_cli/core/asr.py`：固定来源下载、SHA-256 校验、安全解压、离线识别与缓存。
- 新建 `wechat_cli/core/image_keys.py`：提取并交叉验证微信 4.1 V2 图片 AES/XOR 密钥。
- 新建 `wechat_cli/core/ai_package.py`：素材收集、去重、文本/清单渲染、ZIP 生成。
- 新建 `wechat_cli/commands/ai_package.py`：公开 `ai-package` CLI。
- 修改 `wechat_cli/core/messages.py`：接入合并转发、语音元数据和精确图片匹配。
- 修改 `wechat_cli/main.py`、`pyproject.toml`：注册命令并发布 0.4.0。
- 修改 `wechat_cli/web/server.py`：白名单资料包创建与一次性下载 API。
- 修改 `wechat_cli/web/static/index.html`、`app.js`、`app.css`：媒体引用复制、资料包按钮和进度。
- 新建 `wechat_cli/bin/silk_v3_decoder.exe`、`THIRD_PARTY_NOTICES.md`：Windows 解码器与许可说明。
- 修改 `npm/scripts/build.py`、`packaging/windows/README-APP.md`：Windows 交付与首次模型下载说明。
- 新建 `tests/test_forwarded.py`、`tests/test_voice.py`、`tests/test_ai_package.py`，修改现有消息、Web、主入口和打包测试。

### Task 1: 合并转发结构化解析

**Files:**
- Create: `tests/test_forwarded.py`
- Create: `wechat_cli/core/forwarded.py`
- Modify: `wechat_cli/core/messages.py`

- [ ] **Step 1: 写入最外层、嵌套层、未知类型和限制测试**

```python
from wechat_cli.core.forwarded import parse_forwarded_message

def test_parses_nested_record_items():
    xml = make_appmsg_type_19([
        record_item(1, "小陶", "2026-07-29 10:00", "第一条"),
        record_item(17, "小陶", "2026-07-29 10:01", "内层",
                    recordxml=record_xml([record_item(8, "陈子明", "2026-07-29 10:02", "名单.xlsx")])),
    ])
    parsed = parse_forwarded_message(xml)
    assert parsed["title"] == "群聊的聊天记录"
    assert parsed["items"][0]["text"] == "第一条"
    assert parsed["items"][1]["children"][0]["kind"] == "file"

def test_stops_at_depth_and_item_limits():
    parsed = parse_forwarded_message(deep_forward_xml(8), max_depth=2, max_items=3)
    assert parsed["truncated"] is True
    assert count_items(parsed["items"]) <= 3

def test_rejects_dtd():
    assert parse_forwarded_message("<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///x'>]><msg/>") is None
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `python -m unittest tests.test_forwarded -v`

Expected: `ModuleNotFoundError: No module named 'wechat_cli.core.forwarded'`

- [ ] **Step 3: 实现安全、限深、限量的递归解析器**

```python
TYPE_NAMES = {1: "text", 2: "image", 3: "image", 4: "voice", 5: "link",
              8: "file", 17: "forwarded", 19: "link"}

def parse_forwarded_message(content, max_depth=6, max_items=1000):
    root = safe_xml_root(content)
    appmsg = root.find(".//appmsg") if root is not None else None
    if appmsg is None or parse_int(appmsg.findtext("type")) != 19:
        return None
    budget = {"remaining": max_items, "truncated": False}
    record_text = appmsg.findtext("recorditem") or ""
    record_root = safe_xml_root(record_text)
    items = parse_datalist(record_root, 0, max_depth, budget)
    return {
        "title": collapse(appmsg.findtext("title") or "合并转发"),
        "items": items,
        "truncated": budget["truncated"],
    }
```

每个条目固定输出 `kind`、`datatype`、`sender`、`time`、`text`、`title`、`children`；CDATA 中的 `recordxml` 再进入同一安全解析器。

- [ ] **Step 4: 在消息规范化层公开 `forwarded` 和可读文本**

```python
forwarded = parse_forwarded_message(text) if base_type == 49 else None
if forwarded:
    item["type"] = "forwarded"
    item["forwarded"] = forwarded
    item["text"] = format_forwarded_text(forwarded)
```

同时让 `_message_kind()` 把 subtype 19 标为 `forwarded`，不再显示为普通链接。

- [ ] **Step 5: 运行相关测试**

Run: `python -m unittest tests.test_forwarded tests.test_messages -v`

Expected: all tests pass.

- [ ] **Step 6: 提交**

```bash
git add tests/test_forwarded.py wechat_cli/core/forwarded.py wechat_cli/core/messages.py
git commit -m "feat: parse merged forward messages"
```

### Task 2: 最新微信语音数据库与无 FFmpeg 解码

**Files:**
- Create: `tests/test_voice.py`
- Create: `wechat_cli/core/voice.py`
- Add: `wechat_cli/bin/silk_v3_decoder.exe`
- Create: `THIRD_PARTY_NOTICES.md`
- Modify: `wechat_cli/core/messages.py`

- [ ] **Step 1: 写入 media 分库定位、精确语音查询和 WAV 封装测试**

```python
def test_reads_voice_by_chat_and_local_id(tmp_path):
    db_dir = build_media_db(tmp_path, username="wxid_demo", local_id=116,
                            create_time=1785294352, voice_data=b"#!SILK_V3demo")
    record = find_voice_record(db_dir, "wxid_demo", 116, 1785294352)
    assert record.data == b"#!SILK_V3demo"
    assert record.media_db.endswith("media_1.db")

def test_write_pcm_wav_has_16khz_mono_header(tmp_path):
    target = tmp_path / "voice.wav"
    write_pcm_wav(target, b"\x00\x00" * 16000)
    with wave.open(str(target), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2

def test_voice_query_does_not_return_other_chat(tmp_path):
    db_dir = build_media_db(tmp_path, username="wxid_other", local_id=116,
                            create_time=1785294352, voice_data=b"wrong")
    assert find_voice_record(db_dir, "wxid_demo", 116, 1785294352) is None
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_voice -v`

Expected: import failure for `wechat_cli.core.voice`.

- [ ] **Step 3: 实现只读 VoiceInfo 查询与 WAV 写入**

```python
@dataclass(frozen=True)
class VoiceRecord:
    data: bytes
    local_id: int
    create_time: int
    media_db: str

def find_voice_record(db_dir, chat_username, local_id, create_time):
    for path in sorted(Path(db_dir, "message").glob("media_*.db")):
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                """SELECT v.voice_data, v.local_id, v.create_time
                   FROM VoiceInfo v JOIN Name2Id n ON n.rowid=v.chat_name_id
                   WHERE n.user_name=? AND v.local_id=?
                   ORDER BY ABS(v.create_time-?) LIMIT 1""",
                (chat_username, local_id, create_time),
            ).fetchone()
        if row:
            return VoiceRecord(bytes(row[0]), int(row[1]), int(row[2]), str(path))
    return None
```

数据库损坏或缺表只记录失败并继续搜索其他分库；连接必须 `mode=ro`。

- [ ] **Step 4: 接入随包 SILK 解码器**

```python
def decode_silk_to_wav(silk_bytes, output_path, decoder_path=None):
    decoder = decoder_path or bundled_binary("silk_v3_decoder.exe")
    with TemporaryDirectory(prefix="wechat-cli-voice-") as folder:
        silk = Path(folder, "input.silk")
        pcm = Path(folder, "output.pcm")
        silk.write_bytes(silk_bytes)
        subprocess.run([str(decoder), str(silk), str(pcm), "-Fs_API", "16000", "-quiet"],
                       check=True, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        write_pcm_wav(output_path, pcm.read_bytes())
```

用 `resource_path()` 同时兼容源码运行和 PyInstaller `_MEIPASS`。复制已验证的官方发布二进制，并在 `THIRD_PARTY_NOTICES.md` 记录 MIT 许可、上游地址、版本和 SHA-256。

- [ ] **Step 5: 让历史消息返回语音时长和可选语音来源**

```python
if base_type == 34:
    seconds = voice_duration_seconds(text)
    item["text"] = f"[语音 {seconds:.1f}秒]" if seconds else "[语音]"
    if resolve_media:
        item["voice"] = voice_record_payload(find_voice_record(
            db_dir, chat_username, local_id, create_time_ts
        ))
```

不得再把整段语音 XML 放进 `text`。

- [ ] **Step 6: 运行测试与真实样本解码**

Run: `python -m unittest tests.test_voice tests.test_messages -v`

Expected: all tests pass.

Run: `python -m wechat_cli.main history "佳佳姐" --start-time "2026-07-29" --end-time "2026-07-29" --type voice --limit 1 --media`

Expected: JSON 包含干净的 `[语音 …秒]` 和来自 `media_N.db` 的语音元数据，不包含原始 XML。

- [ ] **Step 7: 提交**

```bash
git add tests/test_voice.py wechat_cli/core/voice.py wechat_cli/core/messages.py wechat_cli/bin/silk_v3_decoder.exe THIRD_PARTY_NOTICES.md
git commit -m "feat: read and decode WeChat 4.1 voice data"
```

### Task 3: 同秒图片精确匹配

**Files:**
- Modify: `tests/test_messages.py`
- Modify: `wechat_cli/core/messages.py`

- [ ] **Step 1: 写入四张同秒图片的长度匹配测试**

```python
def test_selects_same_second_image_by_cdn_thumbnail_length(self):
    sizes = [4525, 6961, 5320, 6596]
    paths = make_same_timestamp_dat_files(self.attach_img_dir, sizes)
    content = '<msg><img cdnthumblength="5289" /></msg>'
    path, exists = _resolve_media_path(
        self.db_dir, content, 3, self.timestamp, self.chat_username
    )
    self.assertTrue(exists)
    self.assertEqual(Path(path).stat().st_size, 5320)
```

- [ ] **Step 2: 运行测试并确认当前按时间算法选错**

Run: `python -m unittest tests.test_messages.HistoryItemTests.test_selects_same_second_image_by_cdn_thumbnail_length -v`

Expected: FAIL because the first time-equivalent group is selected.

- [ ] **Step 3: 先按 XML 长度选择图片组，再按时间兜底**

```python
def _image_expected_lengths(content):
    root = _parse_xml_root(content)
    image = root.find(".//img") if root is not None else None
    raw = parse_int(image.attrib.get("cdnthumblength")) if image is not None else 0
    return {raw, raw + 31} if raw else set()

def _select_media_file_by_time(directory, create_time_ts, base_type, expected_sizes=()):
    groups = collect_groups(directory)
    if base_type == 3 and expected_sizes:
        exact = [group for group in groups if any(file_size(path) in expected_sizes for path in group)]
        if exact:
            groups = exact
    return select_closest_group(groups, create_time_ts, base_type)
```

- [ ] **Step 4: 运行消息测试和本机真实四图查询**

Run: `python -m unittest tests.test_messages -v`

Expected: all tests pass.

Run: `python -m wechat_cli.main history "小耄" --start-time "2026-07-29 12:44:00" --end-time "2026-07-29 12:44:59" --media --limit 20`

Expected: local IDs 4、5、6、7 分别对应四个不同文件，其大小依次为 4525、6961、5320、6596。

- [ ] **Step 5: 提交**

```bash
git add tests/test_messages.py wechat_cli/core/messages.py
git commit -m "fix: match same-second images by WeChat metadata"
```

### Task 4: 离线识别组件的安全获取与缓存

**Files:**
- Create: `tests/test_asr.py`
- Create: `wechat_cli/core/asr.py`

- [ ] **Step 1: 写入哈希校验、安全解压、缓存和识别输出测试**

```python
def test_rejects_download_with_wrong_sha256(tmp_path):
    manager = OfflineAsrManager(tmp_path, downloader=lambda *_: b"tampered")
    with pytest.raises(AsrInstallError, match="SHA-256"):
        manager.ensure_archive(RUNTIME_ASSET)

def test_safe_extract_rejects_parent_path(tmp_path):
    archive = tar_with_member("../escape.dll")
    with pytest.raises(AsrInstallError, match="非法路径"):
        safe_extract_tar_bz2(archive, tmp_path / "runtime")

def test_transcribe_parses_first_json_result(tmp_path):
    manager = ready_manager(tmp_path, stdout='{"text":"今天没有困惑"}\n')
    assert manager.transcribe(tmp_path / "voice.wav") == "今天没有困惑"

def test_transcript_cache_uses_audio_sha256(tmp_path):
    manager = ready_manager(tmp_path, stdout='{"text":"缓存内容"}\n')
    assert manager.transcribe(tmp_path / "voice.wav") == "缓存内容"
    assert manager.transcribe(tmp_path / "voice.wav") == "缓存内容"
    assert manager.runner_call_count == 1
```

- [ ] **Step 2: 运行测试并确认模块不存在**

Run: `python -m unittest tests.test_asr -v`

Expected: import failure.

- [ ] **Step 3: 实现固定资产、原子下载、校验和安全解压**

```python
RUNTIME_ASSET = Asset(
    url="https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.4/"
        "sherpa-onnx-v1.13.4-win-x64-shared-MT-Release-no-tts.tar.bz2",
    sha256="e33dc64195d17601879532583233d0d6ed76aa399eb863e5ca0783c5ac82b5aa",
)
MODEL_ASSET = Asset(
    url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2",
    sha256="da92b3db5218c5be53aad53e57d1b6e63e7fc98a0e054fbdd6dbe18e9c6b1450",
)
```

下载写入 `.part`，校验成功后 `os.replace()`；tar 成员解析后的目标必须 `is_relative_to(destination.resolve())`，拒绝符号链接和设备文件。

- [ ] **Step 4: 实现识别和按音频哈希缓存**

```python
def transcribe(self, wav_path):
    audio_hash = sha256_file(wav_path)
    cached = self.cache.get(audio_hash)
    if cached is not None:
        return cached
    runtime, model = self.ensure_ready()
    proc = subprocess.run(
        [runtime / "sherpa-onnx-offline.exe",
         f"--tokens={model / 'tokens.txt'}",
         f"--paraformer={model / 'model.int8.onnx'}",
         "--num-threads=2", str(wav_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=600, check=True,
    )
    text = parse_json_result(proc.stdout)["text"].strip()
    self.cache.put(audio_hash, text)
    return text
```

运行组件只保留识别所需 EXE 与 DLL；状态回调输出 `下载运行组件`、`下载语音模型`、`正在转写`。

- [ ] **Step 5: 运行测试和真实 WAV 识别**

Run: `python -m unittest tests.test_asr -v`

Expected: all tests pass.

Run: `python -c "from wechat_cli.core.asr import OfflineAsrManager; print(OfflineAsrManager().transcribe(r'C:\Users\28276\Documents\Codex\2026-07-28\gei\work\voice-probe\sample16.wav'))"`

Expected: 输出一行非空中文转写；第二次执行不下载且命中缓存。

- [ ] **Step 6: 提交**

```bash
git add tests/test_asr.py wechat_cli/core/asr.py
git commit -m "feat: add verified offline voice transcription"
```

### Task 5: 素材收集与 AI ZIP

**Files:**
- Create: `tests/test_ai_package.py`
- Create: `tests/test_image_v2.py`
- Create: `wechat_cli/core/ai_package.py`
- Create: `wechat_cli/core/image_keys.py`
- Modify: `wechat_cli/core/media.py`
- Modify: `wechat_cli/core/messages.py`

- [ ] **Step 1: 写入 ZIP 结构、素材引用、去重和部分失败测试**

```python
def test_builds_ai_package_with_relative_asset_links(tmp_path):
    result = build_ai_package(
        chat=chat_context(),
        items=[
            image_item(4, b"PNGDATA"),
            sticker_item(5, b"GIFDATA"),
            voice_item(6, b"SILK", transcript="今天完成"),
            forwarded_item(7, nested_text="转发内文字"),
        ],
        output_path=tmp_path / "资料包.zip",
        asset_loader=fake_asset_loader,
    )
    with ZipFile(result.path) as archive:
        names = archive.namelist()
        transcript = archive.read("聊天记录.txt").decode("utf-8")
        manifest = json.loads(archive.read("清单.json"))
    assert all(not name.startswith("/") and ".." not in name for name in names)
    assert "素材/" in transcript
    assert "语音转文字（机器识别）：今天完成" in transcript
    assert "转发内文字" in transcript
    assert manifest["package_version"] == 1

def test_deduplicates_identical_stickers(tmp_path):
    result = build_package_with_two_equal_stickers(tmp_path)
    assert len([a for a in result.assets if a.kind == "sticker"]) == 1

def test_keeps_package_when_one_asset_fails(tmp_path):
    result = build_package_with_one_asset_error(tmp_path)
    assert Path(result.path).exists()
    assert result.failures[0]["message_id"] == 9
```

- [ ] **Step 2: 运行测试并确认模块不存在**

Run: `python -m unittest tests.test_ai_package -v`

Expected: import failure.

- [ ] **Step 3: 实现素材规范化、解码、远程表情限制与去重**

```python
def add_asset(raw, kind, message, extension, manifest):
    digest = hashlib.sha256(raw).hexdigest()
    existing = manifest.asset_by_hash.get(digest)
    if existing:
        return existing["path"]
    filename = safe_asset_name(message, kind, digest, extension)
    relative = f"素材/{filename}"
    manifest.write(relative, raw, digest, kind)
    return relative
```

本地 `.dat` 使用现有 `decode_media_bytes()` 后检测真实 MIME；表情远程请求只允许微信官方域名、最多 5 次重定向、20 MiB、`image/*` 或 `application/octet-stream`，并强制验证图片魔数。

微信 4.1 V2 `.dat` 先解析 15 字节头和 AES/XOR 分段；Windows 仅扫描 `Weixin.exe` 小于 50 MiB 的可读区域，优先可写区域，以多个密文块解出 JPEG/PNG/GIF/WebP/wxgf 魔数才接受候选。官方数据库中的历史表情 URL 可能仍是 HTTP，因此允许精确白名单内的 `*.tc.qq.com` 原始 HTTP，并继续强制响应大小和图片魔数校验。标准图解出 `wxgf` 时改用同组 JPEG 缩略图。

- [ ] **Step 4: 实现确定性文字和 JSON 清单**

```python
def message_text(item):
    prefix = f"[{item['time']}] {item['sender'] or '未知发送者'}（{label(item)}）"
    text = item.get("text", "")
    if item.get("transcript"):
        text += f"\n  语音转文字（机器识别）：{item['transcript']}"
    if item.get("asset_path"):
        text += f"\n  素材：{item['asset_path']}"
    if item.get("forwarded"):
        text += "\n" + indent_forwarded(item["forwarded"])
    return f"{prefix}：{text}"
```

ZIP 统一使用 `/` 分隔和 UTF-8；`清单.json` 不写绝对路径、数据库路径、URL 密钥或临时目录。

- [ ] **Step 5: 运行资料包和消息测试**

Run: `python -m unittest tests.test_ai_package tests.test_messages tests.test_forwarded tests.test_voice -v`

Expected: all tests pass.

- [ ] **Step 6: 提交**

```bash
git add tests/test_ai_package.py wechat_cli/core/ai_package.py wechat_cli/core/messages.py
git commit -m "feat: build AI-ready chat archives"
```

### Task 6: CLI 命令

**Files:**
- Create: `tests/test_ai_package_command.py`
- Create: `wechat_cli/commands/ai_package.py`
- Modify: `wechat_cli/main.py`

- [ ] **Step 1: 写入命令注册、日期范围、输出和关闭转写测试**

```python
def test_ai_package_command_is_registered():
    assert "ai-package" in cli.commands

def test_ai_package_command_builds_selected_range(runner, app):
    result = runner.invoke(cli, [
        "ai-package", "流量潮汐运动🌊",
        "--start-time", "2026-07-29",
        "--end-time", "2026-07-29",
        "--output", "result.zip",
        "--no-transcribe-voice",
    ], obj=app)
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["path"].endswith("result.zip")
    assert payload["transcribe_voice"] is False
```

- [ ] **Step 2: 运行测试并确认命令不存在**

Run: `python -m unittest tests.test_ai_package_command -v`

Expected: FAIL because `ai-package` is not registered.

- [ ] **Step 3: 实现命令并复用历史查询与资料包服务**

```python
@click.command("ai-package")
@click.argument("chat_name")
@click.option("--start-time", default="")
@click.option("--end-time", default="")
@click.option("--output", "output_path", required=True, type=click.Path())
@click.option("--transcribe-voice/--no-transcribe-voice", default=True)
@click.pass_context
def ai_package(ctx, chat_name, start_time, end_time, output_path, transcribe_voice):
    result = create_chat_ai_package(
        app=ctx.obj, chat_name=chat_name, start_time=start_time, end_time=end_time,
        output_path=output_path, transcribe_voice=transcribe_voice,
        progress=lambda message: click.echo(message, err=True),
    )
    output(result.to_dict(), "json")
```

`output` 父目录可创建，但已存在非 ZIP 目录、不可写路径和解析失败要返回清楚的 Click 错误。

- [ ] **Step 4: 运行命令测试和真实聊天打包**

Run: `python -m unittest tests.test_ai_package_command -v`

Expected: all tests pass.

Run: `python -m wechat_cli.main ai-package "陈子明" --start-time 2026-07-29 --end-time 2026-07-29 --output "%TEMP%\chenziming-ai.zip"`

Expected: JSON 显示资料包存在，包含合并转发条目、素材数和语音转写统计。

- [ ] **Step 5: 提交**

```bash
git add tests/test_ai_package_command.py wechat_cli/commands/ai_package.py wechat_cli/main.py
git commit -m "feat: expose AI package CLI command"
```

### Task 7: Web 资料包 API

**Files:**
- Modify: `tests/test_web_server.py`
- Modify: `wechat_cli/web/server.py`

- [ ] **Step 1: 写入白名单参数、临时目录、令牌和下载测试**

```python
def test_builds_ai_package_args_with_safe_output():
    args = build_ai_package_cli_args({
        "chat_name": "陈子明", "start_time": "2026-07-29",
        "end_time": "2026-07-29", "transcribe_voice": True,
    }, output_path=r"C:\safe\random.zip")
    self.assertEqual(args[:2], ["ai-package", "陈子明"])
    self.assertNotIn("output_path", args)

def test_package_token_is_one_time_and_expires(self):
    token = register_download(package_path, now=100)
    self.assertEqual(consume_download(token, now=101), package_path)
    self.assertIsNone(consume_download(token, now=102))

def test_package_download_rejects_path_outside_state_dir(self):
    with self.assertRaises(PermissionError):
        register_download(Path(r"C:\Windows\secret.zip"))
```

- [ ] **Step 2: 运行 Web 测试并确认 API 不存在**

Run: `python -m unittest tests.test_web_server -v`

Expected: new tests fail.

- [ ] **Step 3: 实现专用 POST 和一次性 GET 下载**

```python
if parsed.path == "/api/ai-package":
    payload = self._read_json()
    result = run_ai_package(payload, package_temp_path())
    token = register_download(Path(result["data"]["path"]))
    return self._send_json({**result, "download_url": f"/api/ai-package/{token}"})

if parsed.path.startswith("/api/ai-package/"):
    path = consume_download(parsed.path.rsplit("/", 1)[-1])
    if path is None:
        return self.send_error(HTTPStatus.NOT_FOUND)
    return self._send_file(path, "application/zip", download_name=path.name)
```

令牌使用 `secrets.token_urlsafe(32)`；映射加锁，10 分钟过期；下载后删除 ZIP；应用启动及每次注册时清理过期文件。输出目录由服务端生成，客户端永远不能传绝对路径。

- [ ] **Step 4: 运行 Web 测试**

Run: `python -m unittest tests.test_web_server -v`

Expected: all tests pass.

- [ ] **Step 5: 提交**

```bash
git add tests/test_web_server.py wechat_cli/web/server.py
git commit -m "feat: serve one-time AI package downloads"
```

### Task 8: Web 复制引用、资料包按钮与进度

**Files:**
- Modify: `tests/test_web_server.py`
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`

- [ ] **Step 1: 写入媒体查询、相对素材引用和按钮静态测试**

```python
def test_history_summary_requests_media_and_has_package_button(self):
    html = read_static("index.html")
    js = read_static("app.js")
    self.assertIn('id="download-ai-package"', html)
    self.assertIn("params.media = true", js)
    self.assertIn("function summaryAssetReference", js)
    self.assertIn("/api/ai-package", js)

def test_copy_format_uses_archive_path_not_absolute_path(self):
    js = read_static("app.js")
    self.assertIn('media?.archive_path', js)
    self.assertNotIn('media?.path || media?.archive_path', js)
```

- [ ] **Step 2: 运行测试并确认当前缺少功能**

Run: `python -m unittest tests.test_web_server -v`

Expected: new tests fail.

- [ ] **Step 3: 查询结果启用媒体并渲染可复制相对引用**

```javascript
if (payload.command === "history" && form.dataset.resultMode === "summary") {
  payload.params.media = true;
}

function summaryAssetReference(item) {
  const relative = item?.media?.archive_path || item?.asset_path || "";
  return relative ? `\n  素材：${relative}` : "";
}

function summaryMessageLine(item) {
  const forwarded = formatForwardedCopy(item?.forwarded);
  const transcript = item?.transcript
    ? `\n  语音转文字（机器识别）：${item.transcript}`
    : "";
  return `[${item?.time || "时间未知"}] ${summarySender(item)}（${summaryType(item)}）：`
    + `${summaryText(item)}${transcript}${summaryAssetReference(item)}${forwarded}`;
}
```

没有资料包相对路径时只显示 `[图片]`、`[表情]`、`[语音]`，不得回退复制绝对路径或远程 URL。

- [ ] **Step 4: 增加资料包按钮和状态**

```javascript
downloadAiPackageButton.addEventListener("click", async () => {
  downloadAiPackageButton.disabled = true;
  setPackageStatus("正在准备素材和语音…");
  try {
    const response = await postJson("/api/ai-package", currentSummarySelection());
    setPackageStatus("资料包已生成，正在下载…");
    triggerDownload(response.download_url, response.filename);
    setPackageStatus("资料包下载完成");
  } finally {
    downloadAiPackageButton.disabled = false;
  }
});
```

按钮只在聊天记录结果页可见；切换功能后随结果定档隐藏。首次模型下载说明显示“约 96 MB，仅首次需要，识别全程本机完成”。

- [ ] **Step 5: 运行 Web 测试并在临时端口做浏览器验证**

Run: `python -m unittest tests.test_web_server -v`

Expected: all tests pass.

Run: `python -m wechat_cli.main web --host 127.0.0.1 --port 8792 --no-browser`

Browser checks:

1. 聊天记录选择“陈子明”和 2026-07-29。
2. 结果中的合并转发为分层中文内容。
3. 复制文本不含 `C:\`、`D:\` 或 `https://` 素材地址。
4. 下载 ZIP 后包含 `聊天记录.txt`、`清单.json`、`素材/`。
5. 切换到其他功能后资料包按钮不残留。

- [ ] **Step 6: 提交**

```bash
git add tests/test_web_server.py wechat_cli/web/static/index.html wechat_cli/web/static/app.js wechat_cli/web/static/app.css
git commit -m "feat: add AI package workflow to web UI"
```

### Task 9: 版本、文档、打包、安装和最终验证

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_windows_packaging.py`
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `packaging/windows/README-APP.md`
- Modify: `npm/scripts/build.py`

- [ ] **Step 1: 写入 0.4.0、SILK 二进制和第三方说明打包测试**

```python
def test_release_version_is_0_4_0(self):
    self.assertEqual(_VERSION, "0.4.0")

def test_pyinstaller_bundles_silk_decoder(self):
    cmd = make_pyinstaller_command("win32-x64")
    joined = "\n".join(cmd).replace("\\", "/")
    self.assertIn("wechat_cli/bin/silk_v3_decoder.exe", joined)

def test_package_documents_offline_model_download(self):
    text = (ROOT / "packaging/windows/README-APP.md").read_text("utf-8")
    self.assertIn("首次语音转写", text)
    self.assertIn("约 96 MB", text)
```

- [ ] **Step 2: 运行测试并确认版本/文档测试失败**

Run: `python -m unittest tests.test_main tests.test_windows_packaging -v`

Expected: new tests fail on version and missing documentation.

- [ ] **Step 3: 提升版本并补齐用户文档**

```toml
[project]
version = "0.4.0"
```

主入口 `_VERSION = "0.4.0"`。文档给出 CLI 示例、ZIP 结构、机器转写准确率提示、首次下载/离线缓存说明、隐私边界和 `--no-transcribe-voice` 快速模式。

- [ ] **Step 4: 运行全量测试和代码检查**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 5: 构建 Windows EXE 和可移植 ZIP**

Run: `python scripts/package_windows_app.py`

Expected:

```text
[+] Package directory: ...wechat-cli-web-app-win32-x64-0.4.0
[+] Zip archive: ...wechat-cli-web-app-win32-x64-0.4.0.zip
```

- [ ] **Step 6: 验证冻结 EXE、真实数据和 ZIP**

Run: `npm\platforms\win32-x64\bin\wechat-cli.exe --version`

Expected: `wechat-cli, version 0.4.0`

Run: `npm\platforms\win32-x64\bin\wechat-cli.exe ai-package "陈子明" --start-time 2026-07-29 --end-time 2026-07-29 --output "%TEMP%\wechat-cli-real-ai-package.zip"`

Expected: success JSON；打开 ZIP 检查无绝对路径、合并转发已展开、素材引用均存在、至少一条可用语音有机器转写。

- [ ] **Step 7: 安装到本机并验证 8787**

Run: `powershell -ExecutionPolicy Bypass -File dist\wechat-cli-web-app-win32-x64-0.4.0\install.ps1`

Expected: 旧服务被安全停止，0.4.0 安装并启动 `127.0.0.1:8787`。

检查 `/api/health`、聊天记录页面、AI 资料包下载和 EXE CLI；测试结束后只保留 8787 正式实例。

- [ ] **Step 8: 提交最终发布修改**

```bash
git add tests/test_main.py tests/test_windows_packaging.py pyproject.toml wechat_cli/main.py README.md README_CN.md packaging/windows/README-APP.md npm/scripts/build.py
git commit -m "chore: release WeChat CLI 0.4.0"
```

- [ ] **Step 9: 复核提交和工作树**

Run: `git status --short`

Expected: no output.

Run: `git log --oneline --decorate -12`

Expected: 显示以上小步提交且 `feat/ai-chat-package` 指向 0.4.0 发布提交。
