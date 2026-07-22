mod core;

use core::*;
use tauri::Manager;

#[tauri::command]
fn cmd_engines() -> Vec<EngineInfo> {
    engines()
}

#[tauri::command]
fn cmd_list_profiles(engine: String) -> Result<Vec<ProfileSummary>, String> {
    list_profiles(&engine)
}

#[tauri::command]
fn cmd_ensure_root(engine: String) -> Result<String, String> {
    let e = get_engine(&engine)?;
    Ok(ensure_root(&e)?.display().to_string())
}

#[tauri::command]
fn cmd_profiles_root(engine: String) -> Result<String, String> {
    let e = get_engine(&engine)?;
    Ok(profiles_root(&e).display().to_string())
}

#[tauri::command]
fn cmd_shared_home(engine: String) -> Result<String, String> {
    let e = get_engine(&engine)?;
    Ok(shared_session_home(&e).display().to_string())
}

#[tauri::command]
fn cmd_create_profile(
    engine: String,
    name: String,
    from_current: bool,
    force: bool,
) -> Result<String, String> {
    create_profile(&engine, &name, from_current, force)
}

#[tauri::command]
fn cmd_delete_profile(engine: String, name: String) -> Result<(), String> {
    delete_profile(&engine, &name)
}

#[tauri::command]
fn cmd_read_file(engine: String, name: String, which: String) -> Result<String, String> {
    read_profile_file(&engine, &name, &which)
}

#[tauri::command]
fn cmd_save_file(
    engine: String,
    name: String,
    which: String,
    content: String,
) -> Result<String, String> {
    save_profile_file(&engine, &name, &which, &content)
}

#[tauri::command]
fn cmd_mask_secret(engine: String, text: String) -> String {
    mask_secret(&engine, &text)
}

#[tauri::command]
fn cmd_share_sessions(engine: String, name: String) -> Result<serde_json::Value, String> {
    enable_shared_sessions(&engine, &name)
}

#[tauri::command]
fn cmd_share_all(engine: String) -> Result<Vec<serde_json::Value>, String> {
    enable_shared_sessions_all(&engine)
}

#[tauri::command]
fn cmd_share_status(engine: String, name: Option<String>) -> Result<String, String> {
    session_share_status(&engine, name)
}

#[tauri::command]
fn cmd_doctor(engine: String, name: Option<String>) -> Result<String, String> {
    doctor_report(&engine, name)
}

#[tauri::command]
fn cmd_launch(
    engine: String,
    name: String,
    work_dir: Option<String>,
    run_cli: bool,
    cli_args: Vec<String>,
) -> Result<(), String> {
    launch_profile(&engine, &name, work_dir, run_cli, cli_args)
}

#[tauri::command]
fn cmd_open_path(path: String) -> Result<(), String> {
    open_path(&path)
}

#[tauri::command]
fn cmd_pick_folder() -> Result<Option<String>, String> {
    // Deprecated path: frontend should use @tauri-apps/plugin-dialog.
    // Keep for compatibility — but avoid PowerShell popup if possible.
    pick_folder()
}

#[tauri::command]
fn cmd_cache_report(engine: String) -> Result<CacheReport, String> {
    cache_report(&engine)
}

#[tauri::command]
fn cmd_clean_profile_cache(
    engine: String,
    name: String,
    also_clear_relocated: bool,
) -> Result<serde_json::Value, String> {
    clean_profile_cache(&engine, &name, also_clear_relocated)
}

#[tauri::command]
fn cmd_clean_all_caches(
    engine: String,
    also_clear_relocated: bool,
) -> Result<serde_json::Value, String> {
    clean_all_profile_caches(&engine, also_clear_relocated)
}

#[tauri::command]
fn cmd_get_settings(engine: String) -> Result<IsolatorSettings, String> {
    load_settings(&engine)
}

#[tauri::command]
fn cmd_get_profiles_base() -> Result<Option<String>, String> {
    get_profiles_base()
}

#[tauri::command]
fn cmd_set_sandbox_cache_root(
    engine: String,
    root: Option<String>,
    apply_to_existing: bool,
) -> Result<serde_json::Value, String> {
    set_sandbox_cache_root(&engine, root, apply_to_existing)
}

#[tauri::command]
fn cmd_set_profiles_root(
    engine: String,
    new_root: String,
    leave_junction_at_old: bool,
) -> Result<serde_json::Value, String> {
    set_profiles_root(&engine, new_root, leave_junction_at_old)
}

#[tauri::command]
fn cmd_set_profiles_base(
    base: String,
    leave_junction_at_old: bool,
) -> Result<serde_json::Value, String> {
    set_profiles_base(base, leave_junction_at_old)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();
            // Inject custom scrollbar styles on startup
            window.eval(include_str!("webview_init.js"))?;
            // Resolve codex/claude paths once so Launch does not wait on where.exe
            std::thread::spawn(|| {
                warm_cli_cache();
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            cmd_engines,
            cmd_list_profiles,
            cmd_ensure_root,
            cmd_profiles_root,
            cmd_shared_home,
            cmd_create_profile,
            cmd_delete_profile,
            cmd_read_file,
            cmd_save_file,
            cmd_mask_secret,
            cmd_share_sessions,
            cmd_share_all,
            cmd_share_status,
            cmd_doctor,
            cmd_launch,
            cmd_open_path,
            cmd_pick_folder,
            cmd_cache_report,
            cmd_clean_profile_cache,
            cmd_clean_all_caches,
            cmd_get_settings,
            cmd_get_profiles_base,
            cmd_set_sandbox_cache_root,
            cmd_set_profiles_root,
            cmd_set_profiles_base
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_title("Profile Isolator");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
