use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::BufRead;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use tauri::Emitter;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct BridgeEvent {
    name: String,
    data: Value,
}

#[derive(Debug, Serialize, Deserialize)]
struct BridgeEnvelope {
    payload: Option<Value>,
    error: Option<String>,
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
        })
}

fn python_candidates() -> Vec<(String, Vec<String>)> {
    vec![
        (
            std::env::var("WECHATEMOJI_PYTHON").unwrap_or_else(|_| "python".into()),
            Vec::new(),
        ),
        ("py".into(), vec!["-3".into()]),
    ]
}

/// Run the Python bridge and stream events to the frontend.
///
/// Protocol (line-delimited JSON on stdout):
/// - Event lines:   {"name":"...","data":...}
/// - Result line:   {"payload":...,"error":...}   (exactly one, last line)
fn run_python_bridge(
    app: Option<tauri::AppHandle>,
    method: &str,
    payload: Option<Value>,
) -> Result<BridgeEnvelope, String> {
    let root = workspace_root();
    let script = root.join("tauri_bridge.py");
    if !script.exists() {
        return Err(format!("bridge script not found: {}", script.display()));
    }
    let payload_json = payload.unwrap_or_else(|| json!({})).to_string();
    let script_str = script.to_string_lossy().to_string();

    let mut last_error = String::new();
    for (program, extra_args) in python_candidates() {
        let mut cmd = Command::new(&program);
        cmd.current_dir(&root);
        for arg in &extra_args {
            cmd.arg(arg);
        }
        cmd.arg(&script_str).arg(method).arg(&payload_json);
        cmd.stdout(Stdio::piped()).stderr(Stdio::piped());

        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(err) => {
                last_error = format!("failed to launch {program}: {err}");
                continue;
            }
        };

        let stdout = match child.stdout.take() {
            Some(s) => s,
            None => {
                let _ = child.kill();
                last_error = "no stdout from subprocess".into();
                continue;
            }
        };

        let (tx, rx) = mpsc::channel::<(Vec<BridgeEvent>, Option<BridgeEnvelope>)>();

        let app_clone = app.clone();
        thread::spawn(move || {
            let reader = std::io::BufReader::new(stdout);
            let mut events = Vec::new();
            let mut final_result: Option<BridgeEnvelope> = None;

            for line in reader.lines() {
                let line = match line {
                    Ok(l) => l,
                    Err(_) => continue,
                };
                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }
                let val: Value = match serde_json::from_str(trimmed) {
                    Ok(v) => v,
                    Err(_) => continue,
                };

                // Distinguish events from result by checking for "name" key
                if val.get("name").is_some() && val.get("data").is_some() {
                    // It's an event — emit to frontend in real-time
                    if let Some(ref app_handle) = app_clone {
                        let _ = app_handle.emit("bridge_event", &val);
                    }
                    if let Ok(event) = serde_json::from_value::<BridgeEvent>(val.clone()) {
                        events.push(event);
                    }
                } else if val.get("payload").is_some() || val.get("error").is_some() {
                    // It's the final result line
                    final_result = Some(BridgeEnvelope {
                        payload: val.get("payload").cloned(),
                        error: val.get("error").and_then(|e| e.as_str()).map(String::from),
                    });
                }
            }
            let _ = tx.send((events, final_result));
        });

        // Wait for the subprocess to finish
        let status = match child.wait() {
            Ok(s) => s,
            Err(err) => {
                last_error = format!("failed to wait for subprocess: {err}");
                continue;
            }
        };

        // Collect events and final result from the reader thread
        let (_events, final_result) = match rx.recv() {
            Ok(r) => r,
            Err(_) => {
                last_error = "reader thread panicked".into();
                continue;
            }
        };

        // Check for non-zero exit and propagate as error if no result was produced
        if !status.success() {
            if let Some(ref result) = final_result {
                if result.error.is_some() {
                    return Ok(final_result.unwrap());
                }
            }
            // Process exited with error but no structured result — surface exit code
            return Ok(final_result.unwrap_or(BridgeEnvelope {
                payload: None,
                error: Some(format!(
                    "python exited with code {}",
                    status.code().unwrap_or(-1)
                )),
            }));
        }

        return Ok(final_result.unwrap_or(BridgeEnvelope {
            payload: None,
            error: Some("no result from python".into()),
        }));
    }

    Err(last_error)
}

#[tauri::command]
async fn bridge_call(
    app: tauri::AppHandle,
    method: String,
    payload: Option<Value>,
) -> Result<BridgeEnvelope, String> {
    // MUST run on a blocking thread — child.wait() would freeze the WebView2 UI thread
    tokio::task::spawn_blocking(move || run_python_bridge(Some(app), &method, payload))
        .await
        .map_err(|e| format!("blocking task failed: {e}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![bridge_call])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
