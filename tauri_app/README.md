# Tauri Migration Shell

This folder contains the Tauri-based desktop shell for the project.

Current status:
- Reuses the existing `web/` frontend through Tauri's static asset loading.
- Adds a Rust command bridge that can invoke Python helper code.
- Includes a compatibility layer so the current frontend can still talk to a desktop host using a `pywebview`-like API shape.
- Migrates lightweight startup/status actions first: init, WeChat detection, DB path lookup, upload environment check, and opening the output directory.

Not migrated yet:
- Long-running extract/upload progress streaming
- Native Tauri file/folder picker integration for all actions
- Bundling the Python runtime and scripts as a production sidecar

Prerequisites before `npm run tauri dev` will work on Windows:
- Rust toolchain
- Visual Studio C++ build tools / MSVC toolchain

Recommended next steps:
1. Install Rust + MSVC prerequisites.
2. Run `npm install` inside `tauri_app`.
3. Run `npm run tauri:check` to validate the Rust shell quickly.
4. Start replacing the remaining legacy PyWebView actions with Tauri-native commands and events.
