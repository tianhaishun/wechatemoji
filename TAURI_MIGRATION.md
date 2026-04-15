# Tauri Migration Notes

## Why migrate

The current `PyWebView + Python main process + PyInstaller onefile` stack has structural performance problems:

1. The GUI host and Python bridge share the same responsiveness bottleneck — `evaluate_js` calls from worker threads block the UI thread.
2. `onefile` adds extraction latency before the app becomes interactive.
3. Progress events from long-running operations (extraction, upload) cause UI freezes.

Tauri improves this by:
- Letting WebView2 host the UI with a lighter native Rust shell
- Moving desktop orchestration into Rust (native dialogs, window management)
- Keeping Python as a task worker subprocess instead of the GUI host
- Streaming events via Tauri's event system (no `evaluate_js` bottleneck)

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Tauri (Rust)                                    │
│  ┌──────────┐    ┌──────────┐    ┌───────────┐ │
│  │ WebView2 │◄───│  Event   │◄───│  Python   │ │
│  │ (index   │    │  Emitter │    │ subprocess│ │
│  │  .html)  │    │          │    │ (bridge)  │ │
│  └──────────┘    └──────────┘    └───────────┘ │
│       │                                  ▲     │
│       │ native dialogs                  │     │
│       ▼                                  │     │
│  ┌──────────┐                     invoke │     │
│  │ Dialog   │                             │     │
│  │ Plugin   │                             │     │
│  └──────────┘                             │     │
└─────────────────────────────────────────────────┘
```

**Data flow:**
1. Frontend calls `invoke("bridge_call", { method, payload })`
2. Rust spawns Python subprocess with method + payload
3. Python outputs events as line-delimited JSON to stdout
4. Rust reads each line and emits to frontend via `app.emit("bridge_event", ...)`
5. Frontend listener applies events in real-time
6. Python outputs final result line → Rust returns via invoke

## Files

| File | Role |
|------|------|
| `tauri_app/` | Tauri v2 project |
| `tauri_app/src-tauri/src/lib.rs` | Rust bridge (line-delimited protocol + event streaming) |
| `web/tauri-bridge.js` | Frontend compatibility layer (native dialogs + async bridge) |
| `tauri_bridge.py` | Python worker bridge (all commands + event streaming) |
| `web/index.html` | Shared frontend UI (works with both PyWebView and Tauri) |

## Protocol (Python stdout → Rust)

Line-delimited JSON:
- **Event lines**: `{"name":"emojiListAppend","data":[...]}`  — emitted immediately, forwarded to frontend
- **Result line**: `{"payload":{...},"error":null}`  — exactly one, last line

## Migration status

### Fully migrated (13 commands)
- `init` — returns initial state payload
- `detectWechat` — scans WeChat accounts, streams user list + DB path events
- `onUserChanged` — refreshes DB path for selected user
- `setWechatDir` — native folder picker → set config → re-detect
- `setOutputDir` — native folder picker → set config
- `openOutputDir` — open output folder in Explorer
- `checkUploadEnv` — verify Playwright + Chromium
- `loadFromFolder` — native folder picker → collect emoji files → stream thumbnails
- `loadEmojiFiles` — native file picker → collect emoji files → stream thumbnails
- `startExtract` — WeChat emoji extraction with streaming progress + file-based pause
- `pauseExtract` — toggle pause via file signal
- `runAudit` — pipeline verification with streaming events
- `startUpload` — Feishu upload with streaming progress (env check in subprocess, no UI freeze)

### Not yet done
- Python sidecar packaging for production builds (currently requires system Python)
- Replacing legacy PyWebView exe as the primary distribution

## Build prerequisites

1. Install Rust: https://rustup.rs/
2. Install MSVC build tools (Visual Studio Build Tools)
3. `cd tauri_app && npm install`
4. `npm run tauri:dev` to run in development mode

## Pause/resume implementation

Since each Python command runs as a separate subprocess, pause/resume uses a **file-based signal**:
- Extraction process checks for `.pause_extract` file in output dir
- `pauseExtract` command creates/removes the file
- No shared memory or IPC needed — works across process boundaries
