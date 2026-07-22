//! Engine definitions + profile isolation core for Codex / Claude Code.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use walkdir::WalkDir;

/// Cache resolved CLI paths — `where.exe` is the main Launch lag on Windows.
static CLI_CACHE: Mutex<Option<HashMap<String, String>>> = Mutex::new(None);

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineInfo {
    pub key: String,
    pub label: String,
    pub home_env: String,
    pub profiles_root_env: String,
    pub shared_home_env: String,
    pub profiles_dir_name: String,
    pub default_home_name: String,
    pub primary_file: String,
    pub secondary_file: String,
    pub primary_label: String,
    pub secondary_label: String,
    pub command_names: Vec<String>,
    pub session_dirs: Vec<String>,
    pub session_files: Vec<String>,
    pub resume_cmd: String,
    pub resume_all_cmd: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileSummary {
    pub name: String,
    pub path: String,
    pub model: String,
    pub provider: String,
    pub provider_name: String,
    pub base_url: String,
    pub has_config: bool,
    pub has_auth: bool,
    pub has_catalog: bool,
    pub is_active: bool,
    pub sessions_shared: bool,
    pub sessions_share_target: String,
}

fn home_dir() -> PathBuf {
    env::var_os("USERPROFILE")
        .or_else(|| env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

pub fn engines() -> Vec<EngineInfo> {
    vec![
        EngineInfo {
            key: "codex".into(),
            label: "Codex".into(),
            home_env: "CODEX_HOME".into(),
            profiles_root_env: "CODEX_PROFILES_ROOT".into(),
            shared_home_env: "CODEX_SHARED_HOME".into(),
            profiles_dir_name: "CodexProfiles".into(),
            default_home_name: ".codex".into(),
            primary_file: "config.toml".into(),
            secondary_file: "auth.json".into(),
            primary_label: "config.toml".into(),
            secondary_label: "auth.json".into(),
            command_names: vec!["codex".into()],
            session_dirs: vec!["sessions".into(), "archived_sessions".into()],
            session_files: vec![
                "session_index.jsonl".into(),
                "state_5.sqlite".into(),
                "state_5.sqlite-shm".into(),
                "state_5.sqlite-wal".into(),
            ],
            resume_cmd: "codex resume".into(),
            resume_all_cmd: "codex resume --all".into(),
        },
        EngineInfo {
            key: "claude".into(),
            label: "Claude Code".into(),
            home_env: "CLAUDE_CONFIG_DIR".into(),
            profiles_root_env: "CLAUDE_PROFILES_ROOT".into(),
            shared_home_env: "CLAUDE_SHARED_HOME".into(),
            profiles_dir_name: "ClaudeProfiles".into(),
            default_home_name: ".claude".into(),
            primary_file: "settings.json".into(),
            secondary_file: ".credentials.json".into(),
            primary_label: "settings.json".into(),
            secondary_label: ".credentials.json".into(),
            command_names: vec!["claude".into()],
            session_dirs: vec!["projects".into(), "todos".into()],
            session_files: vec![],
            resume_cmd: "claude --resume".into(),
            resume_all_cmd: "claude --continue".into(),
        },
    ]
}

pub fn get_engine(key: &str) -> Result<EngineInfo, String> {
    engines()
        .into_iter()
        .find(|e| e.key == key)
        .ok_or_else(|| format!("unknown engine: {key}"))
}

pub fn profiles_root(engine: &EngineInfo) -> PathBuf {
    // 1) process env (highest)
    if let Ok(v) = env::var(&engine.profiles_root_env) {
        let t = v.trim();
        if !t.is_empty() {
            return PathBuf::from(t);
        }
    }
    // 2) shared parent base: {base}/CodexProfiles or {base}/ClaudeProfiles
    if let Ok(g) = load_global_settings() {
        if let Some(base) = g.profiles_base {
            let t = base.trim();
            if !t.is_empty() {
                return PathBuf::from(t).join(&engine.profiles_dir_name);
            }
        }
    }
    // 3) legacy per-engine override
    if let Ok(s) = load_settings(&engine.key) {
        if let Some(r) = s.profiles_root {
            let t = r.trim();
            if !t.is_empty() {
                return PathBuf::from(t);
            }
        }
    }
    // 4) default under user home
    home_dir().join(&engine.profiles_dir_name)
}

fn global_settings_path() -> PathBuf {
    home_dir().join(SETTINGS_DIR).join(GLOBAL_SETTINGS_FILE)
}

pub fn load_global_settings() -> Result<GlobalSettings, String> {
    let path = global_settings_path();
    if !path.is_file() {
        return Ok(GlobalSettings::default());
    }
    let raw = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| format!("Invalid global settings: {e}"))
}

pub fn save_global_settings(settings: GlobalSettings) -> Result<(), String> {
    let path = global_settings_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let raw = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    write_text(&path, &(raw + "\n"))
}

pub fn default_home(engine: &EngineInfo) -> PathBuf {
    let p = home_dir().join(&engine.default_home_name);
    fs::canonicalize(&p).unwrap_or(p)
}

pub fn shared_session_home(engine: &EngineInfo) -> PathBuf {
    if let Ok(v) = env::var(&engine.shared_home_env) {
        let t = v.trim();
        if !t.is_empty() {
            let p = PathBuf::from(t);
            return fs::canonicalize(&p).unwrap_or(p);
        }
    }
    default_home(engine)
}

pub fn ensure_root(engine: &EngineInfo) -> Result<PathBuf, String> {
    let root = profiles_root(engine);
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    Ok(root)
}

fn safe_name(name: &str) -> Result<String, String> {
    let n = name.trim();
    if n.is_empty() {
        return Err("Profile name is empty.".into());
    }
    if n == "." || n == ".." || n.chars().any(|c| r#"\/:*?"<>|"#.contains(c)) {
        return Err(format!("Invalid profile name '{n}'"));
    }
    Ok(n.to_string())
}

pub fn profile_path(engine: &EngineInfo, name: &str) -> Result<PathBuf, String> {
    Ok(profiles_root(engine).join(safe_name(name)?))
}

fn re_first<'a>(re: &Regex, text: &'a str) -> String {
    re.captures(text)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .unwrap_or_default()
}

fn summarize_codex(text: &str) -> (String, String, String, String, bool) {
    let model = Regex::new(r#"(?m)^\s*model\s*=\s*"([^"]+)""#).unwrap();
    let provider = Regex::new(r#"(?m)^\s*model_provider\s*=\s*"([^"]+)""#).unwrap();
    let base = Regex::new(r#"(?m)^\s*base_url\s*=\s*"([^"]+)""#).unwrap();
    let name = Regex::new(r#"(?m)^\s*name\s*=\s*"([^"]+)""#).unwrap();
    (
        re_first(&model, text),
        re_first(&provider, text),
        re_first(&name, text),
        re_first(&base, text),
        text.contains("model_catalog_json"),
    )
}

fn summarize_claude(text: &str) -> (String, String, String, String, bool) {
    // Claude Code: API key/URL/model live in settings.json -> env.
    // Prefer ANTHROPIC_MODEL; else show DEFAULT_OPUS/SONNET model (and optional *_NAME for display).
    let mut model = String::new();
    let mut base = String::new();
    if let Ok(v) = serde_json::from_str::<serde_json::Value>(text) {
        if let Some(env) = v.get("env") {
            model = env
                .get("ANTHROPIC_MODEL")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string();
            if model.is_empty() {
                // Prefer human-facing name if present, else model id
                let name = env
                    .get("ANTHROPIC_DEFAULT_OPUS_MODEL_NAME")
                    .or_else(|| env.get("ANTHROPIC_DEFAULT_SONNET_MODEL_NAME"))
                    .or_else(|| env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME"))
                    .and_then(|x| x.as_str())
                    .unwrap_or("");
                let id = env
                    .get("ANTHROPIC_DEFAULT_OPUS_MODEL")
                    .or_else(|| env.get("ANTHROPIC_DEFAULT_SONNET_MODEL"))
                    .or_else(|| env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"))
                    .and_then(|x| x.as_str())
                    .unwrap_or("");
                model = if !name.is_empty() && !id.is_empty() {
                    format!("{name} ({id})")
                } else if !id.is_empty() {
                    id.to_string()
                } else {
                    name.to_string()
                };
            }
            if model.is_empty() {
                model = v
                    .get("model")
                    .and_then(|x| x.as_str())
                    .unwrap_or("")
                    .to_string();
            }
            base = env
                .get("ANTHROPIC_BASE_URL")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string();
        } else {
            model = v
                .get("model")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string();
        }
    }
    let host = url_host(&base);
    (model, host.clone(), host, base, false)
}

fn url_host(url: &str) -> String {
    if url.is_empty() {
        return String::new();
    }
    // crude host parse without full URL crate
    let s = url
        .trim_start_matches("https://")
        .trim_start_matches("http://");
    s.split('/').next().unwrap_or("").to_string()
}

fn is_reparse_point(path: &Path) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        #[link(name = "kernel32")]
        extern "system" {
            fn GetFileAttributesW(lpFileName: *const u16) -> u32;
        }
        const INVALID: u32 = 0xFFFF_FFFF;
        const REPARSE: u32 = 0x400;
        let wide: Vec<u16> = path
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        unsafe {
            let attrs = GetFileAttributesW(wide.as_ptr());
            if attrs == INVALID {
                return false;
            }
            (attrs & REPARSE) != 0
        }
    }
    #[cfg(not(windows))]
    {
        path.is_symlink()
    }
}

fn same_path(a: &Path, b: &Path) -> bool {
    let ca = fs::canonicalize(a).unwrap_or_else(|_| a.to_path_buf());
    let cb = fs::canonicalize(b).unwrap_or_else(|_| b.to_path_buf());
    ca == cb
}

pub fn is_sessions_shared(engine: &EngineInfo, profile_dir: &Path) -> bool {
    let shared = shared_session_home(engine);
    if same_path(profile_dir, &shared) {
        return true;
    }
    let Some(primary) = engine.session_dirs.first() else {
        return false;
    };
    let link = profile_dir.join(primary);
    if !link.exists() {
        return false;
    }
    if !(is_reparse_point(&link) || link.is_symlink()) {
        return false;
    }
    match fs::canonicalize(&link) {
        Ok(target) => same_path(&target, &shared.join(primary)),
        Err(_) => false,
    }
}

fn parse_summary(engine: &EngineInfo, dir: &Path) -> ProfileSummary {
    let primary = dir.join(&engine.primary_file);
    let secondary = dir.join(&engine.secondary_file);
    let text = fs::read_to_string(&primary).unwrap_or_default();
    let (model, provider, provider_name, base_url, has_catalog) = if engine.key == "codex" {
        summarize_codex(&text)
    } else {
        summarize_claude(&text)
    };
    // Cheap active check — avoid canonicalize on every list
    let current = env::var(&engine.home_env).unwrap_or_default();
    let dir_s = dir.display().to_string();
    let is_active = if current.trim().is_empty() {
        false
    } else {
        let c = current.trim().trim_end_matches(['\\', '/']);
        let d = dir_s.trim_end_matches(['\\', '/']);
        c.eq_ignore_ascii_case(d)
            || c.eq_ignore_ascii_case(&format!(r"\\?\{d}"))
            || Path::new(c)
                .file_name()
                .and_then(|n| n.to_str())
                .map(|n| {
                    dir.file_name()
                        .and_then(|x| x.to_str())
                        .map(|x| x.eq_ignore_ascii_case(n))
                        .unwrap_or(false)
                })
                .unwrap_or(false)
    };
    // Sessions shared: primary session dir is a junction/symlink (no canonicalize)
    let shared = engine
        .session_dirs
        .first()
        .map(|primary| {
            let link = dir.join(primary);
            link.exists() && (is_reparse_point(&link) || link.is_symlink())
        })
        .unwrap_or(false);
    ProfileSummary {
        name: dir
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default(),
        path: dir_s,
        model,
        provider,
        provider_name,
        base_url,
        has_config: primary.is_file(),
        has_auth: secondary.is_file(),
        has_catalog,
        is_active,
        sessions_shared: shared,
        sessions_share_target: if shared {
            // Display only — no canonicalize
            if let Ok(v) = env::var(&engine.shared_home_env) {
                let t = v.trim();
                if !t.is_empty() {
                    t.to_string()
                } else {
                    default_home(engine).display().to_string()
                }
            } else {
                default_home(engine).display().to_string()
            }
        } else {
            String::new()
        },
    }
}

fn order_file(root: &Path) -> PathBuf {
    root.join(".profile-order.json")
}

fn load_profile_order(root: &Path) -> Vec<String> {
    let p = order_file(root);
    if !p.is_file() {
        return vec![];
    }
    let Ok(raw) = fs::read_to_string(&p) else {
        return vec![];
    };
    serde_json::from_str::<Vec<String>>(&raw).unwrap_or_default()
}

/// Persist sidebar order (folder names). Missing names are ignored on next load.
pub fn set_profile_order(engine_key: &str, names: Vec<String>) -> Result<(), String> {
    let engine = get_engine(engine_key)?;
    let root = ensure_root(&engine)?;
    let mut cleaned = Vec::new();
    let mut seen = HashSet::new();
    for n in names {
        let Ok(s) = safe_name(&n) else { continue };
        if seen.insert(s.clone()) {
            cleaned.push(s);
        }
    }
    let text = serde_json::to_string_pretty(&cleaned).map_err(|e| e.to_string())?;
    write_text(&order_file(&root), &format!("{text}\n"))?;
    Ok(())
}

pub fn list_profiles(engine_key: &str) -> Result<Vec<ProfileSummary>, String> {
    let engine = get_engine(engine_key)?;
    let root = profiles_root(&engine);
    if !root.is_dir() {
        return Ok(vec![]);
    }
    let mut items = Vec::new();
    let mut dirs: Vec<PathBuf> = fs::read_dir(&root)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| {
            p.is_dir()
                && !p
                    .file_name()
                    .map(|n| {
                        let s = n.to_string_lossy();
                        s.starts_with('.') || s.starts_with('_')
                    })
                    .unwrap_or(true)
        })
        .collect();

    let order = load_profile_order(&root);
    let mut rank: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    for (i, n) in order.iter().enumerate() {
        rank.insert(n.to_ascii_lowercase(), i);
    }
    dirs.sort_by(|a, b| {
        let na = a
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let nb = b
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let ra = rank.get(&na.to_ascii_lowercase()).copied().unwrap_or(usize::MAX);
        let rb = rank.get(&nb.to_ascii_lowercase()).copied().unwrap_or(usize::MAX);
        ra.cmp(&rb)
            .then_with(|| na.to_ascii_lowercase().cmp(&nb.to_ascii_lowercase()))
    });
    for d in dirs {
        items.push(parse_summary(&engine, &d));
    }
    Ok(items)
}

/// Rename a profile folder. Does not touch shared session junctions under the default home.
pub fn rename_profile(engine_key: &str, old_name: &str, new_name: &str) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let old_safe = safe_name(old_name)?;
    let new_safe = safe_name(new_name)?;
    if old_safe.eq_ignore_ascii_case(&new_safe) && old_safe != new_safe {
        // case-only rename on Windows needs a two-step move
    } else if old_safe == new_safe {
        return Ok(profile_path(&engine, &old_safe)?.display().to_string());
    }
    let root = profiles_root(&engine);
    let from = root.join(&old_safe);
    let to = root.join(&new_safe);
    if !from.is_dir() {
        return Err(format!("Profile '{old_safe}' not found"));
    }
    if to.exists() && !from
        .canonicalize()
        .ok()
        .zip(to.canonicalize().ok())
        .map(|(a, b)| a == b)
        .unwrap_or(false)
    {
        return Err(format!("Profile already exists: {new_safe}"));
    }

    // Windows case-only rename: temp hop
    if old_safe.eq_ignore_ascii_case(&new_safe) && old_safe != new_safe {
        let tmp = root.join(format!(".__rename_{}_{}", std::process::id(), old_safe));
        fs::rename(&from, &tmp).map_err(|e| format!("Rename failed: {e}"))?;
        fs::rename(&tmp, &to).map_err(|e| format!("Rename failed: {e}"))?;
    } else {
        fs::rename(&from, &to).map_err(|e| format!("Rename failed: {e}"))?;
    }

    // Keep sidebar order in sync
    let mut order = load_profile_order(&root);
    if !order.is_empty() {
        for n in order.iter_mut() {
            if n == &old_safe {
                *n = new_safe.clone();
            }
        }
        let _ = set_profile_order(engine_key, order);
    }

    Ok(to.display().to_string())
}

fn sanitize_codex(text: &str) -> String {
    text.lines()
        .filter(|l| !Regex::new(r"^\s*model_catalog_json\s*=").unwrap().is_match(l))
        .collect::<Vec<_>>()
        .join("\n")
        + if text.ends_with('\n') { "\n" } else { "" }
}

fn stub_primary(engine: &EngineInfo) -> String {
    if engine.key == "codex" {
        r#"# Codex profile config - edit me
# model_provider = "custom"
# model = "gpt-5.5"
# model_reasoning_effort = "high"
#
# [model_providers.custom]
# name = "MyProvider"
# wire_api = "responses"
# base_url = "https://api.example.com/v1"
# requires_openai_auth = true
"#
        .into()
    } else {
        r#"{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.example.com",
    "ANTHROPIC_AUTH_TOKEN": "sk-REPLACE_ME",
    "ANTHROPIC_MODEL": "claude-opus-4-8"
  }
}
"#
        .into()
    }
}

fn stub_secondary(engine: &EngineInfo) -> String {
    if engine.key == "codex" {
        "{\n  \"OPENAI_API_KEY\": \"sk-REPLACE_ME\"\n}\n".into()
    } else {
        "{}\n".into()
    }
}

fn write_text(path: &Path, content: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, content).map_err(|e| e.to_string())
}

fn copy_profile_files(engine: &EngineInfo, src: &Path, dst: &Path, force: bool) -> Result<(), String> {
    if !src.is_dir() {
        return Err(format!("Source directory not found: {}", src.display()));
    }
    fs::create_dir_all(dst).map_err(|e| e.to_string())?;
    let prim_src = src.join(&engine.primary_file);
    let sec_src = src.join(&engine.secondary_file);
    let prim_dst = dst.join(&engine.primary_file);
    let sec_dst = dst.join(&engine.secondary_file);
    if !force {
        if prim_dst.exists() {
            return Err(format!("{} already exists", engine.primary_file));
        }
        if sec_dst.exists() {
            return Err(format!("{} already exists", engine.secondary_file));
        }
    }
    if prim_src.is_file() {
        let raw = fs::read_to_string(&prim_src).map_err(|e| e.to_string())?;
        let clean = if engine.key == "codex" {
            sanitize_codex(&raw)
        } else {
            raw
        };
        write_text(&prim_dst, &clean)?;
    } else if engine.key == "claude" {
        // Some setups only have env in process; still create a usable settings.json stub
        // if missing, so the profile is editable.
        write_text(&prim_dst, &stub_primary(engine))?;
    }
    if sec_src.is_file() {
        fs::copy(&sec_src, &sec_dst).map_err(|e| e.to_string())?;
    } else if engine.key == "claude" {
        // .credentials.json is optional (MCP OAuth). Create empty object if absent.
        write_text(&sec_dst, "{}\n")?;
    }

    // Claude Code may also use settings.local.json (permissions) — copy if present.
    if engine.key == "claude" {
        let local_src = src.join("settings.local.json");
        let local_dst = dst.join("settings.local.json");
        if local_src.is_file() {
            fs::copy(&local_src, &local_dst).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

pub fn create_profile(
    engine_key: &str,
    name: &str,
    from_current: bool,
    force: bool,
) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let safe = safe_name(name)?;
    let path = profiles_root(&engine).join(&safe);
    ensure_root(&engine)?;
    if path.exists() && !force {
        return Err(format!("Profile already exists: {}", path.display()));
    }
    if path.exists() && force {
        fs::remove_dir_all(&path).map_err(|e| e.to_string())?;
    }
    if from_current {
        copy_profile_files(&engine, &default_home(&engine), &path, true)?;
    } else {
        fs::create_dir_all(&path).map_err(|e| e.to_string())?;
        write_text(&path.join(&engine.primary_file), &stub_primary(&engine))?;
        write_text(&path.join(&engine.secondary_file), &stub_secondary(&engine))?;
    }
    let _ = enable_shared_sessions(engine_key, &safe);
    let _ = apply_sandbox_cache_if_configured(engine_key, &safe);
    Ok(path.display().to_string())
}

pub fn delete_profile(engine_key: &str, name: &str) -> Result<(), String> {
    let engine = get_engine(engine_key)?;
    let path = profile_path(&engine, name)?;
    if !path.is_dir() {
        return Err(format!("Profile '{name}' not found"));
    }
    fs::remove_dir_all(path).map_err(|e| e.to_string())?;
    // Drop from order file if present
    let root = profiles_root(&engine);
    let mut order = load_profile_order(&root);
    if !order.is_empty() {
        let before = order.len();
        order.retain(|n| n != name);
        if order.len() != before {
            let _ = set_profile_order(engine_key, order);
        }
    }
    Ok(())
}

/// Duplicate a profile folder (config/auth only; sessions re-shared to default home).
/// `new_name` optional — defaults to "{name}-copy", "{name}-copy-2", ...
pub fn copy_profile(
    engine_key: &str,
    source_name: &str,
    new_name: Option<String>,
) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let src_safe = safe_name(source_name)?;
    let src = profile_path(&engine, &src_safe)?;
    if !src.is_dir() {
        return Err(format!("Profile '{src_safe}' not found"));
    }
    ensure_root(&engine)?;
    let root = profiles_root(&engine);

    let dest_safe = if let Some(n) = new_name {
        let s = safe_name(&n)?;
        if root.join(&s).exists() {
            return Err(format!("Profile already exists: {s}"));
        }
        s
    } else {
        unique_copy_name(&root, &src_safe)
    };

    let dst = root.join(&dest_safe);
    // Config/auth only — do not deep-copy session trees or sandbox cache
    copy_profile_files(&engine, &src, &dst, true)?;
    // New folder has no local sessions; just junction to shared (skip merge/rmdir walks)
    let _ = link_shared_sessions_fast(&engine, &dst);
    // Sandbox cache relocate is optional and can be slow — skip on copy; apply on next launch/create if needed

    // Insert new name after source in order list without re-scanning all profiles
    let mut order = load_profile_order(&root);
    if order.is_empty() {
        // Seed names from directory listing only (no parse/canonicalize)
        order = fs::read_dir(&root)
            .map(|rd| {
                rd.filter_map(|e| e.ok())
                    .filter(|e| e.path().is_dir())
                    .filter_map(|e| e.file_name().into_string().ok())
                    .filter(|s| !s.starts_with('.') && !s.starts_with('_') && s != &dest_safe)
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        order.sort_by(|a, b| a.to_ascii_lowercase().cmp(&b.to_ascii_lowercase()));
    }
    order.retain(|n| n != &dest_safe);
    if let Some(pos) = order.iter().position(|n| n == &src_safe) {
        order.insert(pos + 1, dest_safe.clone());
    } else {
        order.push(dest_safe.clone());
    }
    let _ = set_profile_order(engine_key, order);

    Ok(dest_safe)
}

/// Fast session linking for a brand-new profile folder (no local session data to merge).
fn link_shared_sessions_fast(engine: &EngineInfo, profile: &Path) -> Result<(), String> {
    let shared = {
        // Avoid canonicalize when possible — env override or default home path
        if let Ok(v) = env::var(&engine.shared_home_env) {
            let t = v.trim();
            if !t.is_empty() {
                PathBuf::from(t)
            } else {
                default_home(engine)
            }
        } else {
            default_home(engine)
        }
    };
    if same_path_fast(profile, &shared) {
        return Ok(());
    }
    let _ = fs::create_dir_all(&shared);
    for dirname in &engine.session_dirs {
        let local = profile.join(dirname);
        let target = shared.join(dirname);
        let _ = fs::create_dir_all(&target);
        // Only create junction if nothing is there yet
        if !local.exists() && !is_reparse_point(&local) {
            let _ = create_junction_quiet(&local, &target);
        }
    }
    for fname in &engine.session_files {
        let local = profile.join(fname);
        let target = shared.join(fname);
        if local.exists() || local.is_symlink() {
            continue;
        }
        if target.is_file() {
            // Optional link/copy for session files — ignore errors to stay fast
            if fs::hard_link(&target, &local).is_err() {
                let _ = fs::copy(&target, &local);
            }
        }
    }
    Ok(())
}

fn same_path_fast(a: &Path, b: &Path) -> bool {
    // Cheap compare first; canonicalize only if both exist and strings differ
    if a == b {
        return true;
    }
    let sa = a.to_string_lossy();
    let sb = b.to_string_lossy();
    if sa.eq_ignore_ascii_case(&sb) {
        return true;
    }
    same_path(a, b)
}

fn create_junction_quiet(link: &Path, target: &Path) -> Result<(), String> {
    let _ = fs::create_dir_all(target);
    if link.exists() || is_reparse_point(link) {
        return Ok(());
    }
    let out = Command::new("cmd")
        .args([
            "/C",
            "mklink",
            "/J",
            &link.display().to_string(),
            &target.display().to_string(),
        ])
        .output()
        .map_err(|e| e.to_string())?;
    if out.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&out.stderr).trim().to_string())
    }
}

fn unique_copy_name(root: &Path, base: &str) -> String {
    let candidate = format!("{base}-copy");
    if !root.join(&candidate).exists() {
        return candidate;
    }
    for i in 2..1000 {
        let c = format!("{base}-copy-{i}");
        if !root.join(&c).exists() {
            return c;
        }
    }
    format!("{base}-copy-{}", std::process::id())
}

pub fn read_profile_file(engine_key: &str, name: &str, which: &str) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let path = profile_path(&engine, name)?;
    if !path.is_dir() {
        return Err(format!("Profile '{name}' not found"));
    }
    let file = path.join(if which == "config" {
        &engine.primary_file
    } else {
        &engine.secondary_file
    });
    if !file.is_file() {
        return Ok(String::new());
    }
    fs::read_to_string(file).map_err(|e| e.to_string())
}

pub fn save_profile_file(
    engine_key: &str,
    name: &str,
    which: &str,
    content: &str,
) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let path = profile_path(&engine, name)?;
    if !path.is_dir() {
        return Err(format!("Profile '{name}' not found"));
    }
    let file = path.join(if which == "config" {
        &engine.primary_file
    } else {
        &engine.secondary_file
    });
    let data = if which == "config" && engine.key == "codex" {
        sanitize_codex(content)
    } else {
        content.to_string()
    };
    write_text(&file, &data)?;
    Ok(file.display().to_string())
}

pub fn mask_secret(engine_key: &str, text: &str) -> String {
    if text.is_empty() {
        return text.to_string();
    }
    // Codex: auth.json OPENAI_API_KEY
    // Claude: settings.json env ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY,
    //         and .credentials.json accessToken fields
    let mut out = text.to_string();
    if engine_key == "codex" {
        let re = Regex::new(r#"("OPENAI_API_KEY"\s*:\s*")([^"]{4})[^"]*(")"#).unwrap();
        out = re.replace_all(&out, r#"$1$2...$3"#).to_string();
    }
    let re2 = Regex::new(
        r#"(?i)("(?:ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|OPENAI_API_KEY|accessToken|refreshToken|apiKey|token)"\s*:\s*")([^"]{4})[^"]*(")"#,
    )
    .unwrap();
    out = re2.replace_all(&out, r#"$1$2...$3"#).to_string();
    // PROXY_MANAGED is not a secret but leave as-is
    out
}

fn merge_tree(src: &Path, dst: &Path) -> io::Result<u32> {
    if !src.is_dir() {
        return Ok(0);
    }
    fs::create_dir_all(dst)?;
    let mut copied = 0u32;
    for entry in WalkDir::new(src).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.is_file() {
            let rel = path.strip_prefix(src).unwrap();
            let target = dst.join(rel);
            if target.exists() {
                continue;
            }
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent)?;
            }
            if fs::copy(path, &target).is_ok() {
                copied += 1;
            }
        }
    }
    Ok(copied)
}

fn create_junction(link: &Path, target: &Path) -> Result<(), String> {
    fs::create_dir_all(target).map_err(|e| e.to_string())?;
    if link.exists() || is_reparse_point(link) {
        if link.is_dir() && !is_reparse_point(link) && !link.is_symlink() {
            return Err(format!(
                "Cannot create junction; real directory exists: {}",
                link.display()
            ));
        }
        // remove existing junction/symlink
        let _ = fs::remove_dir(link);
        let _ = fs::remove_file(link);
        let status = Command::new("cmd")
            .args(["/C", "rmdir", &link.display().to_string()])
            .status();
        let _ = status;
    }
    let out = Command::new("cmd")
        .args([
            "/C",
            "mklink",
            "/J",
            &link.display().to_string(),
            &target.display().to_string(),
        ])
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(format!(
            "mklink failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    Ok(())
}

fn merge_jsonl(src: &Path, dst: &Path) -> Result<(), String> {
    if !src.is_file() {
        return Ok(());
    }
    let mut seen = HashSet::new();
    let mut lines_out = Vec::new();
    if dst.is_file() {
        for line in fs::read_to_string(dst).unwrap_or_default().lines() {
            if line.trim().is_empty() {
                continue;
            }
            lines_out.push(line.to_string());
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(line) {
                if let Some(id) = v.get("id").and_then(|x| x.as_str()) {
                    seen.insert(id.to_string());
                } else {
                    seen.insert(line.to_string());
                }
            } else {
                seen.insert(line.to_string());
            }
        }
    }
    for line in fs::read_to_string(src).map_err(|e| e.to_string())?.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let key = if let Ok(v) = serde_json::from_str::<serde_json::Value>(line) {
            v.get("id")
                .and_then(|x| x.as_str())
                .map(|s| s.to_string())
                .unwrap_or_else(|| line.to_string())
        } else {
            line.to_string()
        };
        if seen.contains(&key) {
            continue;
        }
        seen.insert(key);
        lines_out.push(line.to_string());
    }
    if !lines_out.is_empty() {
        write_text(dst, &(lines_out.join("\n") + "\n"))?;
    }
    Ok(())
}

fn link_or_copy_file(link: &Path, target: &Path, merge_json: bool) -> Result<String, String> {
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    if link.exists() || link.is_symlink() {
        if merge_json && link.is_file() && target.exists() {
            merge_jsonl(link, target)?;
        } else if merge_json && link.is_file() && !target.exists() {
            fs::copy(link, target).map_err(|e| e.to_string())?;
        } else if !target.exists() && link.is_file() {
            fs::copy(link, target).map_err(|e| e.to_string())?;
        }
        fs::remove_file(link).map_err(|e| {
            format!(
                "Cannot replace {} (in use?). Close CLI windows. ({e})",
                link.file_name().unwrap().to_string_lossy()
            )
        })?;
    }
    if !target.exists() {
        if merge_json {
            write_text(target, "")?;
        } else {
            return Ok("skipped-missing-shared".into());
        }
    }
    // hardlink attempt
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        #[link(name = "kernel32")]
        extern "system" {
            fn CreateHardLinkW(
                lpFileName: *const u16,
                lpExistingFileName: *const u16,
                lpSecurityAttributes: *mut core::ffi::c_void,
            ) -> i32;
        }
        let new: Vec<u16> = link
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        let existing: Vec<u16> = target
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        let ok = unsafe { CreateHardLinkW(new.as_ptr(), existing.as_ptr(), std::ptr::null_mut()) };
        if ok != 0 {
            return Ok("hardlink".into());
        }
    }
    fs::copy(target, link).map_err(|e| e.to_string())?;
    Ok("copy".into())
}

pub fn enable_shared_sessions(engine_key: &str, name: &str) -> Result<serde_json::Value, String> {
    let engine = get_engine(engine_key)?;
    let profile = profile_path(&engine, name)?;
    if !profile.is_dir() {
        return Err(format!("Profile '{name}' not found at {}", profile.display()));
    }
    let shared = shared_session_home(&engine);
    if same_path(&profile, &shared) {
        return Ok(serde_json::json!({
            "profile": name,
            "status": "already-shared-home",
            "shared": shared.display().to_string(),
            "ok": true
        }));
    }
    fs::create_dir_all(&shared).map_err(|e| e.to_string())?;
    let mut dirs = serde_json::Map::new();
    for dirname in &engine.session_dirs {
        let local = profile.join(dirname);
        let target = shared.join(dirname);
        fs::create_dir_all(&target).map_err(|e| e.to_string())?;
        if local.exists() && !is_reparse_point(&local) && !local.is_symlink() {
            if local.is_dir() {
                let n = merge_tree(&local, &target).map_err(|e| e.to_string())?;
                fs::remove_dir_all(&local).map_err(|e| e.to_string())?;
                dirs.insert(dirname.clone(), serde_json::json!(format!("merged-{n}-files")));
            } else {
                fs::remove_file(&local).map_err(|e| e.to_string())?;
                dirs.insert(dirname.clone(), serde_json::json!("removed-non-dir"));
            }
        } else if local.exists() && (is_reparse_point(&local) || local.is_symlink()) {
            let _ = fs::remove_dir(&local);
            let _ = Command::new("cmd")
                .args(["/C", "rmdir", &local.display().to_string()])
                .status();
            dirs.insert(dirname.clone(), serde_json::json!("relinked"));
        } else {
            dirs.insert(dirname.clone(), serde_json::json!("created"));
        }
        create_junction(&local, &target)?;
    }

    let mut files = serde_json::Map::new();
    for fname in &engine.session_files {
        let local = profile.join(fname);
        let target = shared.join(fname);
        let res = if fname.ends_with(".jsonl") {
            link_or_copy_file(&local, &target, true)
        } else {
            if local.is_file() && !target.exists() {
                let _ = fs::copy(&local, &target);
            }
            link_or_copy_file(&local, &target, false)
        };
        match res {
            Ok(mode) => {
                files.insert(fname.clone(), serde_json::json!(mode));
            }
            Err(e) => {
                files.insert(fname.clone(), serde_json::json!(format!("error: {e}")));
            }
        }
    }

    let ok = is_sessions_shared(&engine, &profile);
    Ok(serde_json::json!({
        "profile": name,
        "shared": shared.display().to_string(),
        "dirs": dirs,
        "files": files,
        "ok": ok
    }))
}

pub fn enable_shared_sessions_all(engine_key: &str) -> Result<Vec<serde_json::Value>, String> {
    let mut out = Vec::new();
    for p in list_profiles(engine_key)? {
        match enable_shared_sessions(engine_key, &p.name) {
            Ok(v) => out.push(v),
            Err(e) => out.push(serde_json::json!({
                "profile": p.name,
                "ok": false,
                "error": e
            })),
        }
    }
    Ok(out)
}

pub fn session_share_status(engine_key: &str, name: Option<String>) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let shared = shared_session_home(&engine);
    let primary = engine
        .session_dirs
        .first()
        .cloned()
        .unwrap_or_else(|| "sessions".into());
    let sess = shared.join(&primary);
    let mut lines = vec![
        format!("Shared session home : {}", shared.display()),
        format!(
            "{primary} dir       : {} ({})",
            sess.display(),
            if sess.exists() { "exists" } else { "missing" }
        ),
        String::new(),
        format!(
            "Tip: `{}` filters by project folder (cwd).",
            engine.resume_cmd
        ),
        format!(
            "     Same Working directory, or `{}`.",
            engine.resume_all_cmd
        ),
        String::new(),
    ];
    let profiles = if let Some(n) = name {
        list_profiles(engine_key)?
            .into_iter()
            .filter(|p| p.name == n)
            .collect::<Vec<_>>()
    } else {
        list_profiles(engine_key)?
    };
    for p in profiles {
        lines.push(format!(
            "{}: {}",
            p.name,
            if p.sessions_shared {
                "SHARED"
            } else {
                "ISOLATED"
            }
        ));
    }
    Ok(lines.join("\n"))
}

pub fn doctor_report(engine_key: &str, name: Option<String>) -> Result<String, String> {
    let engine = get_engine(engine_key)?;
    let root = profiles_root(&engine);
    let home = default_home(&engine);
    let mut lines = vec![
        format!("Engine        : {}", engine.label),
        format!("Profiles root : {}", root.display()),
        format!("Default home  : {}", home.display()),
        format!(
            "{} : {}",
            engine.home_env,
            env::var(&engine.home_env).unwrap_or_else(|_| "(unset)".into())
        ),
        String::new(),
    ];
    let cli = find_cli(&engine);
    lines.push(if let Some(c) = cli {
        format!("[ok] {} found: {c}", engine.command_names[0])
    } else {
        format!("[!!] {} not found in PATH", engine.command_names[0])
    });
    lines.push(if root.is_dir() {
        "[ok] profiles root exists".into()
    } else {
        "[!!] profiles root missing".into()
    });
    if let Some(n) = name {
        let path = profile_path(&engine, &n)?;
        if !path.is_dir() {
            lines.push(format!("[!!] profile '{n}' not found"));
        } else {
            let s = parse_summary(&engine, &path);
            lines.push(String::new());
            lines.push(format!("--- profile: {n} ---"));
            lines.push(if s.has_config {
                format!("[ok] {}", engine.primary_file)
            } else {
                format!("[!!] missing {}", engine.primary_file)
            });
            lines.push(if s.has_auth {
                format!("[ok] {}", engine.secondary_file)
            } else {
                format!("[!!] missing {}", engine.secondary_file)
            });
            if !s.model.is_empty() {
                lines.push(format!("[ok] model = {}", s.model));
            }
            if !s.base_url.is_empty() {
                lines.push(format!("[ok] base_url = {}", s.base_url));
            }
        }
    }
    Ok(lines.join("\n"))
}

fn find_cli(engine: &EngineInfo) -> Option<String> {
    // Fast path: cached from a previous launch / warm-up
    if let Ok(guard) = CLI_CACHE.lock() {
        if let Some(map) = guard.as_ref() {
            if let Some(p) = map.get(&engine.key) {
                if Path::new(p).is_file() {
                    return Some(p.clone());
                }
            }
        }
    }

    // Prefer known install locations first (no process spawn) — much faster than where.exe
    let appdata = env::var("APPDATA").unwrap_or_default();
    let localbin = home_dir().join(".local").join("bin");
    let mut candidates: Vec<PathBuf> = Vec::new();
    for cmd in &engine.command_names {
        candidates.push(PathBuf::from(r"F:\nodejs").join(format!("{cmd}.cmd")));
        candidates.push(PathBuf::from(r"F:\nodejs").join(format!("{cmd}.exe")));
        candidates.push(PathBuf::from(&appdata).join("npm").join(format!("{cmd}.cmd")));
        candidates.push(PathBuf::from(&appdata).join("npm").join(format!("{cmd}.exe")));
        candidates.push(localbin.join(format!("{cmd}.exe")));
        candidates.push(PathBuf::from(r"F:\nodejs").join(cmd));
        candidates.push(PathBuf::from(&appdata).join("npm").join(cmd));
    }

    // Only call where.exe if nothing found above (slow)
    let mut need_where = true;
    for c in &candidates {
        if c.is_file() {
            need_where = false;
            break;
        }
    }
    if need_where {
        for cmd in &engine.command_names {
            if let Ok(out) = Command::new("where.exe").arg(cmd).output() {
                if out.status.success() {
                    for line in String::from_utf8_lossy(&out.stdout).lines() {
                        let t = line.trim();
                        if !t.is_empty() {
                            candidates.push(PathBuf::from(t));
                        }
                    }
                }
            }
        }
    }

    fn rank(p: &Path) -> u8 {
        match p
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_ascii_lowercase()
            .as_str()
        {
            "cmd" | "bat" => 0,
            "exe" => 1,
            "ps1" => 3,
            "" => 4,
            _ => 2,
        }
    }

    candidates.sort_by_key(|p| rank(p));
    for c in candidates {
        if c.is_file() {
            let s = c.display().to_string();
            if let Ok(mut guard) = CLI_CACHE.lock() {
                let map = guard.get_or_insert_with(HashMap::new);
                map.insert(engine.key.clone(), s.clone());
            }
            return Some(s);
        }
    }
    None
}

/// Warm CLI cache in background so first Launch is instant.
pub fn warm_cli_cache() {
    for eng in engines() {
        let _ = find_cli(&eng);
    }
}

fn strip_verbatim_prefix(s: &str) -> String {
    // Windows canonicalize() yields \\?\C:\... which some tools mishandle
    s.strip_prefix(r"\\?\")
        .or_else(|| s.strip_prefix("//?/"))
        .unwrap_or(s)
        .to_string()
}

fn ps_quote(s: &str) -> String {
    s.replace('\'', "''")
}

pub fn launch_profile(
    engine_key: &str,
    name: &str,
    work_dir: Option<String>,
    run_cli: bool,
    cli_args: Vec<String>,
) -> Result<(), String> {
    let engine = get_engine(engine_key)?;
    let path = profile_path(&engine, name)?;
    if !path.is_dir() {
        return Err(format!("Profile '{name}' not found"));
    }
    let wd = strip_verbatim_prefix(&resolve_work_dir(work_dir));
    // Skip canonicalize on Launch — it can stall on junctions/network; absolute path is enough
    let home = strip_verbatim_prefix(&path.display().to_string());
    let env_var = &engine.home_env;

    if run_cli {
        let cli = find_cli(&engine).ok_or_else(|| {
            format!(
                "{} not found. Install it or add it to PATH.",
                engine.command_names[0]
            )
        })?;
        return spawn_cli_single_console(&cli, &cli_args, env_var, &home, &wd, &engine.key, name);
    }

    // Terminal-only: interactive PowerShell with env pre-set
    let header = format!(
        "$env:{env_var} = '{}'\nSet-Location -LiteralPath '{}'\nWrite-Host ('[{}] profile = {}') -ForegroundColor Green\nWrite-Host ('[{}] {env_var} = ' + $env:{env_var}) -ForegroundColor DarkGray\nWrite-Host 'Type: {}' -ForegroundColor DarkGray\n",
        ps_quote(&home),
        ps_quote(&wd),
        engine.key,
        ps_quote(name),
        engine.key,
        engine.command_names[0]
    );
    Command::new("powershell.exe")
        .args(["-NoLogo", "-NoExit", "-Command", &header])
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

/// One console window: env + cwd via process APIs; CLI args as separate argv (no nested-quote breakage).
fn spawn_cli_single_console(
    cli: &str,
    cli_args: &[String],
    env_var: &str,
    home: &str,
    wd: &str,
    engine_key: &str,
    profile_name: &str,
) -> Result<(), String> {
    // Prefer .cmd sibling when where returned extensionless npm shim (e.g. F:\nodejs\codex)
    let mut launch_path = PathBuf::from(cli);
    let ext = launch_path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if ext.is_empty() || ext == "ps1" {
        let sibling = launch_path.with_extension("cmd");
        if sibling.is_file() {
            launch_path = sibling;
        }
    }
    let launch = launch_path.display().to_string();
    if !launch_path.is_file() {
        return Err(format!("CLI not found: {launch}"));
    }

    // Sanitize title (cmd title cannot contain & | < > ^)
    let safe_title: String = format!("{engine_key} - {profile_name}")
        .chars()
        .map(|c| match c {
            '&' | '|' | '<' | '>' | '^' | '"' => ' ',
            _ => c,
        })
        .collect();

    // CRITICAL: do NOT put quoted paths inside a single /k string.
    // Nested quotes break cmd parsing → "文件名、目录名或卷标语法不正确".
    // Pass each token as its own argv; set env/cwd on the process instead.
    let mut cmd = Command::new("cmd.exe");
    cmd.arg("/k");
    // title then call — both as one leading fragment without path quotes
    cmd.arg(format!("title {safe_title} && call"));
    cmd.arg(&launch);
    for a in cli_args {
        cmd.arg(a);
    }

    cmd.env(env_var, home);

    let work = if Path::new(wd).is_dir() {
        wd.to_string()
    } else {
        home_dir().display().to_string()
    };
    cmd.current_dir(&work);

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NEW_CONSOLE: u32 = 0x0000_0010;
        cmd.creation_flags(CREATE_NEW_CONSOLE);
    }

    cmd.spawn()
        .map_err(|e| format!("Failed to launch: {e}"))?;
    Ok(())
}

fn resolve_work_dir(preferred: Option<String>) -> String {
    if let Some(p) = preferred {
        let t = p.trim();
        if !t.is_empty() && Path::new(t).is_dir() {
            return fs::canonicalize(t)
                .map(|x| strip_verbatim_prefix(&x.display().to_string()))
                .unwrap_or_else(|_| t.to_string());
        }
    }
    // Do NOT use process cwd (often the install/dist folder or System32 for GUI)
    home_dir().display().to_string()
}

pub fn open_path(path: &str) -> Result<(), String> {
    let p = PathBuf::from(path);

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;

        if p.is_file() {
            Command::new("explorer.exe")
                .args(["/select,", path])
                .creation_flags(CREATE_NO_WINDOW)
                .spawn()
                .map_err(|e| e.to_string())?;
        } else {
            fs::create_dir_all(&p).map_err(|e| e.to_string())?;
            Command::new("explorer.exe")
                .arg(path)
                .creation_flags(CREATE_NO_WINDOW)
                .spawn()
                .map_err(|e| e.to_string())?;
        }
    }

    #[cfg(not(windows))]
    {
        if p.is_file() {
            Command::new("explorer.exe")
                .args(["/select,", path])
                .spawn()
                .map_err(|e| e.to_string())?;
        } else {
            fs::create_dir_all(&p).map_err(|e| e.to_string())?;
            Command::new("explorer.exe")
                .arg(path)
                .spawn()
                .map_err(|e| e.to_string())?;
        }
    }

    Ok(())
}

pub fn pick_folder() -> Result<Option<String>, String> {
    // Simple PowerShell folder browser fallback for reliability
    let script = r#"
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Select working directory'
if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }
"#;

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let out = Command::new("powershell.exe")
            .args(["-NoProfile", "-Command", script])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map_err(|e| e.to_string())?;
        let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
        Ok(if s.is_empty() { None } else { Some(s) })
    }

    #[cfg(not(windows))]
    {
        let out = Command::new("powershell.exe")
            .args(["-NoProfile", "-Command", script])
            .output()
            .map_err(|e| e.to_string())?;
        let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
        Ok(if s.is_empty() { None } else { Some(s) })
    }
}

// ---------------------------------------------------------------------------
// Cache management (sandbox-bin / tmp) — does not touch sessions or configs
// ---------------------------------------------------------------------------

const CACHE_DIR_NAMES: &[&str] = &[".sandbox-bin", ".tmp", "tmp"];
/// Settings live OUTSIDE profiles root so relocating profiles doesn't lose settings.
const SETTINGS_DIR: &str = ".profile-isolator";
const GLOBAL_SETTINGS_FILE: &str = "global.json";

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct IsolatorSettings {
    /// Override for this engine's profiles root (legacy / per-engine override).
    pub profiles_root: Option<String>,
    /// If set, each profile's `.sandbox-bin` junctions to
    /// `{sandboxCacheRoot}/{profileName}/.sandbox-bin`.
    pub sandbox_cache_root: Option<String>,
}

/// Shared parent for both engines: `{profilesBase}/CodexProfiles` and `{profilesBase}/ClaudeProfiles`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct GlobalSettings {
    pub profiles_base: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CacheEntry {
    pub name: String,
    pub path: String,
    pub bytes: u64,
    pub is_junction: bool,
    pub target: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileCacheInfo {
    pub profile: String,
    pub profile_path: String,
    pub local_bytes: u64,
    pub entries: Vec<CacheEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CacheReport {
    pub engine: String,
    pub profiles_root: String,
    pub sandbox_cache_root: Option<String>,
    pub total_local_bytes: u64,
    pub profiles: Vec<ProfileCacheInfo>,
}

fn settings_path(engine: &EngineInfo) -> PathBuf {
    home_dir()
        .join(SETTINGS_DIR)
        .join(format!("{}.json", engine.key))
}

pub fn load_settings(engine_key: &str) -> Result<IsolatorSettings, String> {
    let engine = get_engine(engine_key)?;
    let path = settings_path(&engine);
    if !path.is_file() {
        // migrate legacy settings that lived under profiles root
        let legacy = home_dir()
            .join(&engine.profiles_dir_name)
            .join(".isolator-settings.json");
        if legacy.is_file() {
            if let Ok(raw) = fs::read_to_string(&legacy) {
                if let Ok(s) = serde_json::from_str::<IsolatorSettings>(&raw) {
                    let _ = save_settings(engine_key, s.clone());
                    return Ok(s);
                }
            }
        }
        return Ok(IsolatorSettings::default());
    }
    let raw = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| format!("Invalid settings: {e}"))
}

pub fn save_settings(engine_key: &str, settings: IsolatorSettings) -> Result<(), String> {
    let engine = get_engine(engine_key)?;
    let path = settings_path(&engine);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let raw = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    write_text(&path, &(raw + "\n"))
}

/// Directory size without following junctions/symlinks (local data only).
fn local_dir_size(path: &Path) -> u64 {
    if !path.exists() {
        return 0;
    }
    if is_reparse_point(path) || path.is_symlink() {
        return 0;
    }
    if path.is_file() {
        return fs::metadata(path).map(|m| m.len()).unwrap_or(0);
    }
    let mut total = 0u64;
    let Ok(rd) = fs::read_dir(path) else {
        return 0;
    };
    for ent in rd.flatten() {
        let p = ent.path();
        if is_reparse_point(&p) || p.is_symlink() {
            continue;
        }
        if p.is_dir() {
            total = total.saturating_add(local_dir_size(&p));
        } else if let Ok(m) = ent.metadata() {
            total = total.saturating_add(m.len());
        }
    }
    total
}

fn junction_target_display(path: &Path) -> Option<String> {
    if !(is_reparse_point(path) || path.is_symlink()) {
        return None;
    }
    fs::canonicalize(path)
        .ok()
        .map(|p| p.display().to_string())
}

fn profile_cache_entries(profile_dir: &Path) -> (u64, Vec<CacheEntry>) {
    let mut entries = Vec::new();
    let mut local_total = 0u64;

    // Always count full local profile size (skip reparse children)
    let Ok(rd) = fs::read_dir(profile_dir) else {
        return (0, entries);
    };
    for ent in rd.flatten() {
        let p = ent.path();
        let name = ent.file_name().to_string_lossy().to_string();
        let is_j = is_reparse_point(&p) || p.is_symlink();
        let bytes = if is_j { 0 } else { local_dir_size(&p) };
        local_total = local_total.saturating_add(bytes);

        // Only surface known cache folders + large dirs in the report list
        let interesting = CACHE_DIR_NAMES.contains(&name.as_str())
            || name == ".sandbox"
            || name.starts_with("logs_")
            || bytes >= 5 * 1024 * 1024;
        if interesting {
            entries.push(CacheEntry {
                name,
                path: p.display().to_string(),
                bytes,
                is_junction: is_j,
                target: junction_target_display(&p),
            });
        }
    }
    entries.sort_by(|a, b| b.bytes.cmp(&a.bytes));
    (local_total, entries)
}

pub fn cache_report(engine_key: &str) -> Result<CacheReport, String> {
    let engine = get_engine(engine_key)?;
    let root = profiles_root(&engine);
    let settings = load_settings(engine_key).unwrap_or_default();
    let mut profiles = Vec::new();
    let mut total = 0u64;
    if root.is_dir() {
        let mut dirs: Vec<PathBuf> = fs::read_dir(&root)
            .map_err(|e| e.to_string())?
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|p| {
                p.is_dir()
                    && !p
                        .file_name()
                        .map(|n| {
                            let s = n.to_string_lossy();
                            s.starts_with('.') || s.starts_with('_')
                        })
                        .unwrap_or(true)
            })
            .collect();
        dirs.sort_by(|a, b| {
            a.file_name()
                .unwrap()
                .to_ascii_lowercase()
                .cmp(&b.file_name().unwrap().to_ascii_lowercase())
        });
        for d in dirs {
            let (local, entries) = profile_cache_entries(&d);
            total = total.saturating_add(local);
            profiles.push(ProfileCacheInfo {
                profile: d
                    .file_name()
                    .map(|s| s.to_string_lossy().to_string())
                    .unwrap_or_default(),
                profile_path: d.display().to_string(),
                local_bytes: local,
                entries,
            });
        }
    }
    Ok(CacheReport {
        engine: engine.key.clone(),
        profiles_root: root.display().to_string(),
        sandbox_cache_root: settings.sandbox_cache_root,
        total_local_bytes: total,
        profiles,
    })
}

/// Remove safe cache dirs: .sandbox-bin, .tmp, tmp (never junctions, never sessions/config).
pub fn clean_profile_cache(
    engine_key: &str,
    name: &str,
    also_clear_relocated: bool,
) -> Result<serde_json::Value, String> {
    let engine = get_engine(engine_key)?;
    let profile = profile_path(&engine, name)?;
    if !profile.is_dir() {
        return Err(format!("Profile '{name}' not found"));
    }
    let mut removed = Vec::new();
    let mut freed = 0u64;
    let mut skipped = Vec::new();

    for dir_name in CACHE_DIR_NAMES {
        let p = profile.join(dir_name);
        if !p.exists() {
            continue;
        }
        if is_reparse_point(&p) || p.is_symlink() {
            // Junction: remove link only, optionally clear target if under sandbox_cache_root
            let target = junction_target_display(&p);
            if also_clear_relocated {
                if let Some(ref t) = target {
                    let tp = PathBuf::from(t);
                    if tp.is_dir() && !is_reparse_point(&tp) {
                        let b = local_dir_size(&tp);
                        let _ = fs::remove_dir_all(&tp);
                        freed = freed.saturating_add(b);
                        removed.push(format!("{dir_name} (target cleared)"));
                    }
                }
            }
            // remove junction itself
            let _ = fs::remove_dir(&p);
            let _ = Command::new("cmd")
                .args(["/C", "rmdir", &p.display().to_string()])
                .status();
            if !also_clear_relocated {
                removed.push(format!("{dir_name} (junction removed, target kept)"));
            }
            skipped.push(format!("{dir_name}: was junction"));
            continue;
        }
        let b = local_dir_size(&p);
        match fs::remove_dir_all(&p) {
            Ok(()) => {
                freed = freed.saturating_add(b);
                removed.push(dir_name.to_string());
            }
            Err(e) => skipped.push(format!("{dir_name}: {e}")),
        }
    }

    Ok(serde_json::json!({
        "profile": name,
        "freedBytes": freed,
        "removed": removed,
        "notes": skipped,
        "ok": true
    }))
}

pub fn clean_all_profile_caches(
    engine_key: &str,
    also_clear_relocated: bool,
) -> Result<serde_json::Value, String> {
    let list = list_profiles(engine_key)?;
    let mut results = Vec::new();
    let mut total_freed = 0u64;
    for p in list {
        match clean_profile_cache(engine_key, &p.name, also_clear_relocated) {
            Ok(v) => {
                if let Some(b) = v.get("freedBytes").and_then(|x| x.as_u64()) {
                    total_freed = total_freed.saturating_add(b);
                }
                results.push(v);
            }
            Err(e) => results.push(serde_json::json!({
                "profile": p.name,
                "ok": false,
                "error": e
            })),
        }
    }
    Ok(serde_json::json!({
        "ok": true,
        "totalFreedBytes": total_freed,
        "results": results
    }))
}

/// Point each profile's `.sandbox-bin` at `{root}/{profile}/.sandbox-bin`.
/// Moves existing real folders into the new location when possible.
pub fn set_sandbox_cache_root(
    engine_key: &str,
    root: Option<String>,
    apply_to_existing: bool,
) -> Result<serde_json::Value, String> {
    let engine = get_engine(engine_key)?;
    // Codex primarily benefits; still allow setting for any engine.
    let mut settings = load_settings(engine_key)?;
    let root_clean = root
        .as_ref()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty());

    if let Some(ref r) = root_clean {
        let rp = PathBuf::from(r);
        fs::create_dir_all(&rp).map_err(|e| format!("Cannot create cache root: {e}"))?;
        settings.sandbox_cache_root = Some(rp.display().to_string());
    } else {
        settings.sandbox_cache_root = None;
    }
    save_settings(engine_key, settings.clone())?;

    let mut applied = Vec::new();
    if apply_to_existing {
        if let Some(ref r) = settings.sandbox_cache_root {
            let cache_root = PathBuf::from(r);
            for p in list_profiles(engine_key)? {
                match relocate_sandbox_bin(&engine, &p.name, &cache_root) {
                    Ok(msg) => applied.push(serde_json::json!({"profile": p.name, "ok": true, "detail": msg})),
                    Err(e) => applied.push(serde_json::json!({"profile": p.name, "ok": false, "error": e})),
                }
            }
        } else if apply_to_existing {
            // Clearing root: materialize nothing; leave junctions as-is (user can Clean to drop them)
            applied.push(serde_json::json!({
                "ok": true,
                "detail": "sandboxCacheRoot cleared; existing junctions left intact. Use Clean cache to remove .sandbox-bin links."
            }));
        }
    }

    Ok(serde_json::json!({
        "ok": true,
        "sandboxCacheRoot": settings.sandbox_cache_root,
        "applied": applied
    }))
}

fn relocate_sandbox_bin(
    engine: &EngineInfo,
    name: &str,
    cache_root: &Path,
) -> Result<String, String> {
    let profile = profile_path(engine, name)?;
    let local = profile.join(".sandbox-bin");
    let target = cache_root.join(name).join(".sandbox-bin");
    fs::create_dir_all(target.parent().unwrap()).map_err(|e| e.to_string())?;

    if local.exists() && !is_reparse_point(&local) && !local.is_symlink() {
        // Move real folder into cache root
        if target.exists() {
            // merge then remove local
            let _ = merge_tree(&local, &target);
            fs::remove_dir_all(&local).map_err(|e| e.to_string())?;
        } else {
            fs::rename(&local, &target).or_else(|_| {
                // cross-volume: copy then remove
                let _n = merge_tree(&local, &target).map_err(|e| e.to_string())?;
                fs::remove_dir_all(&local).map_err(|e| e.to_string())?;
                Ok::<(), String>(())
            })?;
        }
        create_junction(&local, &target)?;
        return Ok(format!("moved + junction → {}", target.display()));
    }

    if local.exists() && (is_reparse_point(&local) || local.is_symlink()) {
        // repoint junction
        let _ = fs::remove_dir(&local);
        let _ = Command::new("cmd")
            .args(["/C", "rmdir", &local.display().to_string()])
            .status();
        if !target.exists() {
            fs::create_dir_all(&target).map_err(|e| e.to_string())?;
        }
        create_junction(&local, &target)?;
        return Ok(format!("repointed junction → {}", target.display()));
    }

    // no local sandbox yet — pre-create junction so first sandbox write goes to cache root
    if !target.exists() {
        fs::create_dir_all(&target).map_err(|e| e.to_string())?;
    }
    create_junction(&local, &target)?;
    Ok(format!("created junction → {}", target.display()))
}

/// Move BOTH engines' profile trees under a shared parent:
/// `{base}/CodexProfiles` and `{base}/ClaudeProfiles`.
pub fn set_profiles_base(
    base: String,
    leave_junction_at_old: bool,
) -> Result<serde_json::Value, String> {
    let base_path = PathBuf::from(base.trim());
    if base_path.as_os_str().is_empty() {
        return Err("Base folder is empty.".into());
    }
    fs::create_dir_all(&base_path).map_err(|e| format!("Cannot create base: {e}"))?;

    let mut engines_result = Vec::new();
    for eng in engines() {
        let new_root = base_path.join(&eng.profiles_dir_name);
        match set_profiles_root(&eng.key, new_root.display().to_string(), leave_junction_at_old)
        {
            Ok(v) => engines_result.push(serde_json::json!({
                "engine": eng.key,
                "ok": true,
                "result": v
            })),
            Err(e) => engines_result.push(serde_json::json!({
                "engine": eng.key,
                "ok": false,
                "error": e
            })),
        }
    }

    // Clear per-engine profiles_root so shared base is authoritative
    for eng in engines() {
        if let Ok(mut s) = load_settings(&eng.key) {
            s.profiles_root = None;
            let _ = save_settings(&eng.key, s);
        }
    }

    let mut g = load_global_settings().unwrap_or_default();
    g.profiles_base = Some(base_path.display().to_string());
    save_global_settings(g)?;

    Ok(serde_json::json!({
        "ok": true,
        "profilesBase": base_path.display().to_string(),
        "engines": engines_result
    }))
}

pub fn get_profiles_base() -> Result<Option<String>, String> {
    Ok(load_global_settings()?.profiles_base)
}

/// Move entire profiles root (e.g. CodexProfiles) to a new folder and persist it.
///
/// - Copies/moves all profile directories to `new_root`
/// - Saves `profilesRoot` in `~\.profile-isolator\{engine}.json`
/// - Optionally leaves a junction at the old path → new path (so old shortcuts still work)
pub fn set_profiles_root(
    engine_key: &str,
    new_root: String,
    leave_junction_at_old: bool,
) -> Result<serde_json::Value, String> {
    let engine = get_engine(engine_key)?;
    let new_path = PathBuf::from(new_root.trim());
    if new_path.as_os_str().is_empty() {
        return Err("New profiles root is empty.".into());
    }

    let old_path = profiles_root(&engine);
    if same_path(&old_path, &new_path) {
        return Ok(serde_json::json!({
            "ok": true,
            "detail": "already-at-target",
            "profilesRoot": old_path.display().to_string(),
        }));
    }

    // Refuse nesting (new inside old or old inside new)
    let old_s = old_path.to_string_lossy().to_lowercase();
    let new_s = new_path.to_string_lossy().to_lowercase();
    if new_s.starts_with(&(old_s.clone() + "\\")) || old_s.starts_with(&(new_s.clone() + "\\")) {
        return Err("New root cannot be inside the current root (or vice versa).".into());
    }

    fs::create_dir_all(&new_path).map_err(|e| format!("Cannot create new root: {e}"))?;

    let mut moved = Vec::new();
    let mut notes = Vec::new();

    if old_path.is_dir() {
        // If old root itself is a junction, just retarget settings (data already elsewhere)
        if is_reparse_point(&old_path) || old_path.is_symlink() {
            notes.push("old root is a junction; only settings updated".to_string());
        } else {
            let rd = fs::read_dir(&old_path).map_err(|e| e.to_string())?;
            for ent in rd.flatten() {
                let src = ent.path();
                let name = ent.file_name();
                let name_s = name.to_string_lossy();
                // skip settings legacy file
                if name_s == ".isolator-settings.json" {
                    continue;
                }
                let dst = new_path.join(&name);
                if dst.exists() {
                    notes.push(format!("skip existing: {name_s}"));
                    continue;
                }
                // Prefer rename (same volume); fallback copy tree
                match fs::rename(&src, &dst) {
                    Ok(()) => moved.push(name_s.to_string()),
                    Err(_) => {
                        if src.is_dir() {
                            // copytree then remove (handles cross-volume; junctions copied as reparse when possible via cmd)
                            copy_dir_preserving_reparse(&src, &dst)?;
                            // only remove if not reparse that might still be needed — after successful copy
                            remove_path_force(&src)?;
                            moved.push(format!("{name_s} (copied)"));
                        } else if src.is_file() {
                            fs::copy(&src, &dst).map_err(|e| e.to_string())?;
                            let _ = fs::remove_file(&src);
                            moved.push(format!("{name_s} (file)"));
                        }
                    }
                }
            }

            if leave_junction_at_old {
                // old root must be empty (or nearly) before replace with junction
                // remove leftover empty dirs/files we can
                let _ = fs::remove_dir_all(&old_path);
                // recreate as junction to new
                if let Some(parent) = old_path.parent() {
                    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                // if path still exists as empty dir, remove it
                if old_path.exists() {
                    remove_path_force(&old_path)?;
                }
                create_junction(&old_path, &new_path)?;
                notes.push(format!(
                    "left junction: {} → {}",
                    old_path.display(),
                    new_path.display()
                ));
            } else {
                // try remove old root if empty
                let _ = fs::remove_dir(&old_path);
                notes.push("old root left without junction (removed if empty)".into());
            }
        }
    } else {
        notes.push("old root did not exist; created new empty root".into());
    }

    // Persist setting LAST so subsequent profiles_root() uses new path
    let mut settings = load_settings(engine_key).unwrap_or_default();
    settings.profiles_root = Some(new_path.display().to_string());
    save_settings(engine_key, settings)?;

    Ok(serde_json::json!({
        "ok": true,
        "oldRoot": old_path.display().to_string(),
        "profilesRoot": new_path.display().to_string(),
        "moved": moved,
        "notes": notes,
    }))
}

fn remove_path_force(path: &Path) -> Result<(), String> {
    if !path.exists() && !is_reparse_point(path) {
        return Ok(());
    }
    if is_reparse_point(path) || path.is_symlink() {
        let _ = fs::remove_dir(path);
        let _ = fs::remove_file(path);
        let _ = Command::new("cmd")
            .args(["/C", "rmdir", &path.display().to_string()])
            .status();
        return Ok(());
    }
    if path.is_file() {
        fs::remove_file(path).map_err(|e| e.to_string())
    } else {
        fs::remove_dir_all(path).map_err(|e| e.to_string())
    }
}

/// Copy directory tree. Junctions/symlinks are recreated as junctions to the same target when possible.
fn copy_dir_preserving_reparse(src: &Path, dst: &Path) -> Result<(), String> {
    if is_reparse_point(src) || src.is_symlink() {
        if let Ok(target) = fs::canonicalize(src) {
            if let Some(parent) = dst.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            create_junction(dst, &target)?;
            return Ok(());
        }
    }
    fs::create_dir_all(dst).map_err(|e| e.to_string())?;
    let rd = fs::read_dir(src).map_err(|e| e.to_string())?;
    for ent in rd.flatten() {
        let s = ent.path();
        let d = dst.join(ent.file_name());
        if is_reparse_point(&s) || s.is_symlink() {
            if let Ok(target) = fs::canonicalize(&s) {
                create_junction(&d, &target)?;
            }
        } else if s.is_dir() {
            copy_dir_preserving_reparse(&s, &d)?;
        } else {
            fs::copy(&s, &d).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// After creating a profile, if sandbox cache root is set, wire .sandbox-bin.
pub fn apply_sandbox_cache_if_configured(engine_key: &str, name: &str) -> Result<(), String> {
    let settings = load_settings(engine_key)?;
    if let Some(root) = settings.sandbox_cache_root {
        let engine = get_engine(engine_key)?;
        let _ = relocate_sandbox_bin(&engine, name, Path::new(&root))?;
    }
    Ok(())
}

