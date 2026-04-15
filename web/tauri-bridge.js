/**
 * Tauri compatibility layer for the existing PyWebView frontend.
 *
 * Architecture:
 * - Native file/folder dialogs via Tauri dialog plugin (direct invoke, no npm import)
 * - Python commands via invoke("bridge_call") with line-delimited streaming
 * - Events are emitted in real-time via Tauri event system (bridge_event)
 */
(() => {
  const tauri = window.__TAURI__;
  const invoke = tauri?.core?.invoke;
  const listen = tauri?.event?.listen;

  if (typeof invoke !== "function") {
    return; // Not running inside Tauri — PyWebView will provide window.pywebview
  }

  /**
   * Call a Python bridge command. Events are streamed via Tauri event system
   * and applied in real-time. The returned promise resolves with the final payload.
   */
  async function call(method, payload = null) {
    const unlisten = await listen("bridge_event", (evt) => {
      const event = evt.payload;
      if (window.onPythonEvent && event?.name) {
        window.onPythonEvent(event.name, event.data);
      }
    });

    try {
      const envelope = await invoke("bridge_call", { method, payload });
      if (envelope?.error) {
        throw new Error(envelope.error);
      }
      return envelope?.payload;
    } finally {
      unlisten();
    }
  }

  /**
   * Open a native folder picker using Tauri dialog plugin (direct invoke).
   * Returns the selected folder path, or null if cancelled.
   */
  async function dialogOpenFolder(defaultPath) {
    return invoke("plugin:dialog|open", {
      options: {
        defaultPath: defaultPath || "",
        directory: true,
        multiple: false,
      },
    });
  }

  /**
   * Open a native file picker using Tauri dialog plugin (direct invoke).
   * Returns an array of selected file paths, or null if cancelled.
   */
  async function dialogOpenFiles(defaultPath, filters) {
    return invoke("plugin:dialog|open", {
      options: {
        defaultPath: defaultPath || "",
        directory: false,
        multiple: true,
        filters: filters || [
          { name: "Image files", extensions: ["png", "gif", "jpg", "jpeg", "webp"] },
        ],
      },
    });
  }

  /**
   * Open a native folder picker, then call Python with the selected path.
   */
  async function folderPicker(defaultPath, pythonMethod) {
    try {
      const selected = await dialogOpenFolder(defaultPath);
      if (!selected) return null;
      return call(pythonMethod, { path: selected });
    } catch (err) {
      console.error(`folderPicker(${pythonMethod}) failed:`, err);
      return null;
    }
  }

  /**
   * Open a native file picker, then call Python with the selected paths.
   */
  async function filePicker(defaultPath, pythonMethod, filters) {
    try {
      const selected = await dialogOpenFiles(defaultPath, filters);
      if (!selected) return null;
      return call(pythonMethod, { paths: selected });
    } catch (err) {
      console.error(`filePicker(${pythonMethod}) failed:`, err);
      return null;
    }
  }

  function parsePayload(rawPayload) {
    if (!rawPayload || typeof rawPayload !== "string") {
      return {};
    }
    try {
      const payload = JSON.parse(rawPayload);
      return payload && typeof payload === "object" ? payload : {};
    } catch {
      return {};
    }
  }

  // ── Build the pywebview-compatible API surface ──
  window.pywebview = {
    api: {
      // ── Simple invoke commands ──
      init: () => call("init"),
      detectWechat: () => call("detectWechat"),
      onUserChanged: (value) => call("onUserChanged", { value }),
      openOutputDir: () => call("openOutputDir"),
      checkUploadEnv: () => call("checkUploadEnv"),

      // ── Native dialog + Python processing ──
      browseWechatDir: () => folderPicker(
        document.getElementById("outputDir")?.value || "",
        "setWechatDir"
      ),
      browseOutputDir: () => folderPicker(
        document.getElementById("outputDir")?.value || "",
        "setOutputDir"
      ),
      loadFromFolder: () => folderPicker(
        document.getElementById("outputDir")?.value || "",
        "loadFromFolder"
      ),
      loadEmojiFiles: () => filePicker(
        document.getElementById("outputDir")?.value || "",
        "loadEmojiFiles"
      ),

      // ── Long-running operations (streaming events) ──
      startExtract: (rawPayload) => {
        const payload = parsePayload(rawPayload);
        const userData = payload.selectedUser || {};
        const wxid = userData.wxid || "";
        if (!wxid) {
          window.onPythonEvent("log", {
            time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
            message: "请先选择一个微信账号",
            level: "error",
          });
          return;
        }
        return call("startExtract", {
          wxid,
          output_dir: payload.outputDir || document.getElementById("outputDir")?.value || "",
        });
      },
      pauseExtract: () => call("pauseExtract"),
      runAudit: () => call("runAudit"),
      startUpload: (rawPayload) => {
        const payload = parsePayload(rawPayload);
        const selectedFiles = Array.isArray(payload.selectedFiles) ? payload.selectedFiles : [];
        return call("startUpload", {
          files: selectedFiles.length > 0 ? selectedFiles : undefined,
          mode: payload.mode || "personal",
          pack_name: payload.packName || "wechat_emoji_pack",
        });
      },
      stopUpload: () => call("stopUpload"),
    },
  };

  // Dispatch the ready event so the main script initializes
  window.dispatchEvent(new Event("pywebviewready"));
})();
