export type EngineInfo = {
  key: string;
  label: string;
  homeEnv: string;
  profilesRootEnv: string;
  sharedHomeEnv: string;
  profilesDirName: string;
  defaultHomeName: string;
  primaryFile: string;
  secondaryFile: string;
  primaryLabel: string;
  secondaryLabel: string;
  commandNames: string[];
  sessionDirs: string[];
  sessionFiles: string[];
  resumeCmd: string;
  resumeAllCmd: string;
};

export type ProfileSummary = {
  name: string;
  path: string;
  model: string;
  provider: string;
  providerName: string;
  baseUrl: string;
  hasConfig: boolean;
  hasAuth: boolean;
  hasCatalog: boolean;
  isActive: boolean;
  sessionsShared: boolean;
  sessionsShareTarget: string;
};

export type CacheEntry = {
  name: string;
  path: string;
  bytes: number;
  isJunction: boolean;
  target?: string | null;
};

export type ProfileCacheInfo = {
  profile: string;
  profilePath: string;
  localBytes: number;
  entries: CacheEntry[];
};

export type CacheReport = {
  engine: string;
  profilesRoot: string;
  sandboxCacheRoot?: string | null;
  totalLocalBytes: number;
  profiles: ProfileCacheInfo[];
};

export type IsolatorSettings = {
  profilesRoot?: string | null;
  sandboxCacheRoot?: string | null;
};

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke: inv } = await import("@tauri-apps/api/core");
  return inv<T>(cmd, args);
}

export const api = {
  engines: () => invoke<EngineInfo[]>("cmd_engines"),
  listProfiles: (engine: string) => invoke<ProfileSummary[]>("cmd_list_profiles", { engine }),
  ensureRoot: (engine: string) => invoke<string>("cmd_ensure_root", { engine }),
  profilesRoot: (engine: string) => invoke<string>("cmd_profiles_root", { engine }),
  sharedHome: (engine: string) => invoke<string>("cmd_shared_home", { engine }),
  createProfile: (engine: string, name: string, fromCurrent: boolean, force: boolean) =>
    invoke<string>("cmd_create_profile", { engine, name, fromCurrent, force }),
  deleteProfile: (engine: string, name: string) =>
    invoke<void>("cmd_delete_profile", { engine, name }),
  renameProfile: (engine: string, oldName: string, newName: string) =>
    invoke<string>("cmd_rename_profile", { engine, oldName, newName }),
  setProfileOrder: (engine: string, names: string[]) =>
    invoke<void>("cmd_set_profile_order", { engine, names }),
  readFile: (engine: string, name: string, which: "config" | "auth") =>
    invoke<string>("cmd_read_file", { engine, name, which }),
  saveFile: (engine: string, name: string, which: "config" | "auth", content: string) =>
    invoke<string>("cmd_save_file", { engine, name, which, content }),
  maskSecret: (engine: string, text: string) =>
    invoke<string>("cmd_mask_secret", { engine, text }),
  shareSessions: (engine: string, name: string) =>
    invoke<Record<string, unknown>>("cmd_share_sessions", { engine, name }),
  shareAll: (engine: string) =>
    invoke<Record<string, unknown>[]>("cmd_share_all", { engine }),
  shareStatus: (engine: string, name?: string | null) =>
    invoke<string>("cmd_share_status", { engine, name: name ?? null }),
  doctor: (engine: string, name?: string | null) =>
    invoke<string>("cmd_doctor", { engine, name: name ?? null }),
  launch: (
    engine: string,
    name: string,
    workDir: string | null,
    runCli: boolean,
    cliArgs: string[]
  ) => invoke<void>("cmd_launch", { engine, name, workDir, runCli, cliArgs }),
  openPath: (path: string) => invoke<void>("cmd_open_path", { path }),
  /** Prefer native dialog; falls back only if plugin fails. */
  pickFolder: async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        multiple: false,
        title: "Select folder",
      });
      if (selected == null) return null;
      return typeof selected === "string" ? selected : String(selected);
    } catch {
      return invoke<string | null>("cmd_pick_folder");
    }
  },
  cacheReport: (engine: string) => invoke<CacheReport>("cmd_cache_report", { engine }),
  cleanProfileCache: (engine: string, name: string, alsoClearRelocated = false) =>
    invoke<Record<string, unknown>>("cmd_clean_profile_cache", {
      engine,
      name,
      alsoClearRelocated,
    }),
  cleanAllCaches: (engine: string, alsoClearRelocated = false) =>
    invoke<Record<string, unknown>>("cmd_clean_all_caches", {
      engine,
      alsoClearRelocated,
    }),
  getSettings: (engine: string) => invoke<IsolatorSettings>("cmd_get_settings", { engine }),
  getProfilesBase: () => invoke<string | null>("cmd_get_profiles_base"),
  setSandboxCacheRoot: (engine: string, root: string | null, applyToExisting: boolean) =>
    invoke<Record<string, unknown>>("cmd_set_sandbox_cache_root", {
      engine,
      root,
      applyToExisting,
    }),
  setProfilesRoot: (
    engine: string,
    newRoot: string,
    leaveJunctionAtOld: boolean
  ) =>
    invoke<Record<string, unknown>>("cmd_set_profiles_root", {
      engine,
      newRoot,
      leaveJunctionAtOld,
    }),
  /** Move BOTH CodexProfiles + ClaudeProfiles under one parent folder. */
  setProfilesBase: (base: string, leaveJunctionAtOld: boolean) =>
    invoke<Record<string, unknown>>("cmd_set_profiles_base", {
      base,
      leaveJunctionAtOld,
    }),
};

export function formatBytes(n: number): string {
  if (!n || n < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}
