import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { api, EngineInfo, ProfileSummary, CacheReport, formatBytes } from "./lib/api";

type Tab = "config" | "auth" | "launch" | "sessions";
type Toast = { kind: "ok" | "error" | "info"; text: string } | null;
type ThemeMode = "system" | "light" | "dark";

function systemTheme(): "light" | "dark" {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(mode: ThemeMode) {
  const resolved = mode === "system" ? systemTheme() : mode;
  document.documentElement.setAttribute("data-theme", resolved);
}

export default function App() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [engineKey, setEngineKey] = useState("codex");
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [root, setRoot] = useState("");
  const [sharedHome, setSharedHome] = useState("");
  const [tab, setTab] = useState<Tab>("config");
  const [configText, setConfigText] = useState("");
  const [configRaw, setConfigRaw] = useState("");
  const [authText, setAuthText] = useState("");
  const [authRaw, setAuthRaw] = useState("");
  const [mask, setMask] = useState(true);
  const [workDir, setWorkDir] = useState("");
  const workDirKey = useCallback((eng: string, name: string) => `pi-workdir:${eng}:${name}`, []);
  const loadWorkDir = useCallback(
    (eng: string, name: string) => {
      try {
        return localStorage.getItem(workDirKey(eng, name)) || "";
      } catch {
        return "";
      }
    },
    [workDirKey]
  );
  const saveWorkDir = useCallback(
    (eng: string, name: string, dir: string) => {
      try {
        const k = workDirKey(eng, name);
        const t = dir.trim();
        if (t) localStorage.setItem(k, t);
        else localStorage.removeItem(k);
      } catch {
        /* ignore quota */
      }
    },
    [workDirKey]
  );
  const [args, setArgs] = useState("");
  const [sessionStatus, setSessionStatus] = useState("");
  const [sessionDetail, setSessionDetail] = useState("");
  const [toast, setToast] = useState<Toast>(null);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [fromCurrent, setFromCurrent] = useState(true);
  const [doctorOpen, setDoctorOpen] = useState(false);
  const [doctorText, setDoctorText] = useState("");
  const [busy, setBusy] = useState(false);
  const [cacheOpen, setCacheOpen] = useState(false);
  const [cacheReport, setCacheReport] = useState<CacheReport | null>(null);
  const [cacheBusy, setCacheBusy] = useState(false);
  const [sandboxRootInput, setSandboxRootInput] = useState("");
  const [profilesRootInput, setProfilesRootInput] = useState("");
  const [leaveJunction, setLeaveJunction] = useState(true);
  const [maximized, setMaximized] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem("pi-theme") as ThemeMode | null;
    return saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
  });
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement | null>(null);
  const moreLeaveTimer = useRef<number | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [draggingName, setDraggingName] = useState<string | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const dragFromIndex = useRef<number>(-1);
  const dropIndexRef = useRef<number | null>(null);
  const profilesRef = useRef(profiles);
  profilesRef.current = profiles;
  dropIndexRef.current = dropIndex;

  const engine = useMemo(
    () => engines.find((e) => e.key === engineKey) ?? engines[0],
    [engines, engineKey]
  );
  const selectedProfile = useMemo(
    () => profiles.find((p) => p.name === selected) ?? null,
    [profiles, selected]
  );

  const flash = useCallback((kind: NonNullable<Toast>["kind"], text: string) => {
    setToast({ kind, text });
    window.setTimeout(() => setToast(null), 2500);
  }, []);

  // Remember last selection per engine so Codex/Claude don't share the same name.
  const selectedByEngine = useRef<Record<string, string | null>>({});

  const refresh = useCallback(
    async (keep?: string | null) => {
      if (!engine) return;
      try {
        setBusy(true);
        const [list, r, sh] = await Promise.all([
          api.listProfiles(engine.key),
          api.ensureRoot(engine.key),
          api.sharedHome(engine.key),
        ]);
        setProfiles(list);
        setRoot(r);
        setSharedHome(sh);

        const preferred =
          keep !== undefined ? keep : selectedByEngine.current[engine.key] ?? null;
        const next =
          (preferred && list.some((p) => p.name === preferred) && preferred) ||
          list[0]?.name ||
          null;
        selectedByEngine.current[engine.key] = next;
        setSelected(next);
      } catch (e) {
        flash("error", String(e));
      } finally {
        setBusy(false);
      }
    },
    [engine, flash]
  );

  // Close More menu on outside click / Escape
  useEffect(() => {
    if (!moreOpen) return;
    const onDown = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMoreOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [moreOpen]);

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem("pi-theme", theme);
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => applyTheme("system");
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, [theme]);

  const cycleTheme = () => {
    setTheme((t) => (t === "system" ? "light" : t === "light" ? "dark" : "system"));
  };

  const themeLabel = theme === "system" ? "Auto" : theme === "light" ? "Light" : "Dark";

  const themeIcon =
    theme === "light" ? (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.7" />
        <path
          d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
        />
      </svg>
    ) : theme === "dark" ? (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M20 14.5A8.5 8.5 0 0 1 9.5 4 7 7 0 1 0 20 14.5z"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinejoin="round"
        />
      </svg>
    ) : (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
        <rect x="3" y="4" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.7" />
        <path d="M8 21h8M12 18v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    );

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    (async () => {
      try {
        const win = getCurrentWindow();
        setMaximized(await win.isMaximized());
        unlisten = await win.onResized(async () => {
          setMaximized(await win.isMaximized());
        });
      } catch {}
    })();
    return () => { unlisten?.(); };
  }, []);

  async function winMinimize() {
    try { await getCurrentWindow().minimize(); } catch {}
  }
  async function winToggleMax() {
    try {
      await getCurrentWindow().toggleMaximize();
      setMaximized(await getCurrentWindow().isMaximized());
    } catch {}
  }
  async function winClose() {
    try { await getCurrentWindow().close(); } catch {}
  }


  useEffect(() => {
    (async () => {
      try {
        const es = await api.engines();
        setEngines(es);
        if (es[0]) setEngineKey(es[0].key);
      } catch (e) {
        flash("error", String(e));
      }
    })();
  }, [flash]);

  useEffect(() => {
    if (engine) {
      // Clear selection immediately so we don't read a Codex name under Claude (or vice versa).
      setSelected(null);
      setProfiles([]);
      setConfigText("");
      setConfigRaw("");
      setAuthRaw("");
      setAuthText("");
      void refresh(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engineKey, engines.length]);

  useEffect(() => {
    if (!engine || !selected) {
      setConfigText("");
      setConfigRaw("");
      setAuthRaw("");
      setAuthText("");
      setSessionStatus("No profile selected");
      setSessionDetail("");
      setWorkDir("");
      return;
    }
    // Only load files if this name exists in the *current* engine's list.
    const belongs = profiles.some((p) => p.name === selected);
    if (!belongs) {
      return;
    }
    // Restore remembered working directory for this profile
    setWorkDir(loadWorkDir(engine.key, selected));
    let cancelled = false;
    (async () => {
      try {
        const [cfg, auth] = await Promise.all([
          api.readFile(engine.key, selected, "config"),
          api.readFile(engine.key, selected, "auth"),
        ]);
        if (cancelled) return;
        setConfigRaw(cfg);
        setAuthRaw(auth);
        // Mask only secret-bearing files:
        // - Claude: settings.json (config) may contain ANTHROPIC_AUTH_TOKEN
        // - Codex: auth.json may contain OPENAI_API_KEY
        // Claude .credentials.json is MCP OAuth — never mask in UI.
        if (mask) {
          setConfigText(await api.maskSecret(engine.key, cfg));
          setAuthText(
            engine.key === "codex"
              ? await api.maskSecret(engine.key, auth)
              : auth
          );
        } else {
          setConfigText(cfg);
          setAuthText(auth);
        }
        const p = profiles.find((x) => x.name === selected);
        if (p?.sessionsShared) {
          setSessionStatus("Sessions shared");
          setSessionDetail(
            `Linked to\n${sharedHome}\n\nSame project folder, then:\n${engine.resumeCmd}\n${engine.resumeAllCmd}`
          );
        } else {
          setSessionStatus("Sessions isolated");
          setSessionDetail(
            `Share storage so other providers can resume this project.\n${engine.primaryLabel} / ${engine.secondaryLabel} stay private.`
          );
        }
      } catch (e) {
        if (!cancelled) flash("error", String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [engine, selected, mask, profiles, sharedHome, flash]);

  async function onCreate() {
    if (!engine || !newName.trim()) return;
    try {
      setBusy(true);
      await api.createProfile(engine.key, newName.trim(), fromCurrent, false);
      setShowNew(false);
      const name = newName.trim();
      setNewName("");
      await refresh(name);
      flash("ok", `Created ${name}`);
    } catch (e) {
      const msg = String(e);
      if (msg.toLowerCase().includes("exists")) {
        if (confirm(`${msg}\nOverwrite?`)) {
          try {
            await api.createProfile(engine.key, newName.trim(), fromCurrent, true);
            setShowNew(false);
            await refresh(newName.trim());
            flash("ok", "Re-created");
          } catch (e2) {
            flash("error", String(e2));
          }
        }
      } else flash("error", msg);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(name?: string) {
    if (!engine) return;
    const target = name || selected;
    if (!target) return;
    if (!confirm(`Delete profile "${target}"? This cannot be undone.`)) return;
    try {
      await api.deleteProfile(engine.key, target);
      try {
        localStorage.removeItem(workDirKey(engine.key, target));
      } catch {
        /* ignore */
      }
      if (selectedByEngine.current[engine.key] === target) {
        selectedByEngine.current[engine.key] = null;
      }
      if (selected === target) setSelected(null);
      await refresh(null);
      flash("ok", "Deleted");
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onCopy(name?: string) {
    if (!engine) return;
    const target = name || selected;
    if (!target) return;
    const src = profiles.find((p) => p.name === target);
    flash("info", "Copying…");
    try {
      const created = await api.copyProfile(engine.key, target);
      // Copy remembered workdir too
      const wd = loadWorkDir(engine.key, target);
      if (wd) saveWorkDir(engine.key, created, wd);
      // Optimistic insert — no full list reparse wait
      const optimistic: ProfileSummary = src
        ? {
            ...src,
            name: created,
            path: src.path.replace(/[/\\][^/\\]+$/, `\\${created}`),
            isActive: false,
          }
        : {
            name: created,
            path: `${root}\\${created}`,
            model: "",
            provider: "",
            providerName: "",
            baseUrl: "",
            hasConfig: true,
            hasAuth: true,
            hasCatalog: false,
            isActive: false,
            sessionsShared: true,
            sessionsShareTarget: sharedHome,
          };
      setProfiles((prev) => {
        const without = prev.filter((p) => p.name !== created);
        const idx = without.findIndex((p) => p.name === target);
        if (idx >= 0) {
          const next = [...without];
          next.splice(idx + 1, 0, optimistic);
          return next;
        }
        return [...without, optimistic];
      });
      selectedByEngine.current[engine.key] = created;
      setSelected(created);
      if (wd) setWorkDir(wd);
      flash("ok", `Copied as ${created}`);
      // Soft refresh in background (optional consistency)
      void api.listProfiles(engine.key).then(setProfiles).catch(() => {});
    } catch (e) {
      flash("error", String(e));
    }
  }

  function startRename(name: string) {
    setRenaming(name);
    setRenameValue(name);
    window.setTimeout(() => {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }, 0);
  }

  async function commitRename() {
    if (!engine || !renaming) return;
    const next = renameValue.trim();
    if (!next || next === renaming) {
      setRenaming(null);
      return;
    }
    try {
      await api.renameProfile(engine.key, renaming, next);
      // Migrate remembered workdir key
      const oldWd = loadWorkDir(engine.key, renaming);
      if (oldWd) {
        saveWorkDir(engine.key, next, oldWd);
        try {
          localStorage.removeItem(workDirKey(engine.key, renaming));
        } catch {
          /* ignore */
        }
      }
      selectedByEngine.current[engine.key] = next;
      setSelected(next);
      setRenaming(null);
      await refresh(next);
      flash("ok", `Renamed to ${next}`);
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function persistOrder(next: ProfileSummary[]) {
    if (!engine) return;
    setProfiles(next);
    try {
      await api.setProfileOrder(
        engine.key,
        next.map((p) => p.name)
      );
    } catch (e) {
      flash("error", String(e));
      await refresh(selected);
    }
  }

  /** Pointer-based reorder — HTML5 DnD shows a red "no" cursor in WebView2. */
  function beginReorder(name: string, index: number, e: ReactPointerEvent) {
    if (renaming) return;
    e.preventDefault();
    e.stopPropagation();
    dragFromIndex.current = index;
    dropIndexRef.current = index;
    setDraggingName(name);
    setDropIndex(index);
    if (engine) selectedByEngine.current[engine.key] = name;
    setSelected(name);
  }

  function indexFromPointerY(clientY: number): number {
    const root = listRef.current;
    if (!root) return 0;
    const rows = Array.from(root.querySelectorAll<HTMLElement>(".item[data-name]"));
    if (rows.length === 0) return 0;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i].getBoundingClientRect();
      const mid = r.top + r.height / 2;
      if (clientY < mid) return i;
    }
    return rows.length - 1;
  }

  useEffect(() => {
    if (!draggingName) return;
    const onMove = (e: PointerEvent) => {
      const idx = indexFromPointerY(e.clientY);
      dropIndexRef.current = idx;
      setDropIndex(idx);
    };
    const onUp = () => {
      const from = dragFromIndex.current;
      const to = dropIndexRef.current;
      const list = [...profilesRef.current];
      const eng = engine;
      setDraggingName(null);
      setDropIndex(null);
      dropIndexRef.current = null;
      dragFromIndex.current = -1;
      if (!eng || from < 0 || to == null || from === to || from >= list.length) return;
      const [item] = list.splice(from, 1);
      // When dragging down, after removal the target slot is still `to` (item at old to moves up)
      // When dragging up, insert at `to`
      let insertAt = to;
      if (from < to) {
        // removed earlier index; insertAt already points to desired final index after splice?
        // Example: [0,1,2], from=0 to=2 → after remove [1,2], want [1,2,0] → insertAt=2
        insertAt = to;
      }
      insertAt = Math.max(0, Math.min(insertAt, list.length));
      list.splice(insertAt, 0, item);
      void (async () => {
        setProfiles(list);
        try {
          await api.setProfileOrder(
            eng.key,
            list.map((p) => p.name)
          );
        } catch (err) {
          flash("error", String(err));
          await refresh(selectedByEngine.current[eng.key] ?? null);
        }
      })();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [draggingName, engine, flash, refresh]);

  async function onSaveConfig() {
    if (!engine || !selected) return;
    // Claude key lives in settings.json — don't save while masked.
    if (engine.key === "claude" && mask) {
      flash("error", "Turn off Mask secrets before saving settings.json");
      return;
    }
    try {
      await api.saveFile(engine.key, selected, "config", configText);
      await refresh(selected);
      flash("ok", "Saved");
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onSaveAuth() {
    if (!engine || !selected) return;
    // Only Codex auth.json is masked; Claude MCP credentials are not.
    if (engine.key === "codex" && mask) {
      flash("error", "Turn off Mask secrets before saving");
      return;
    }
    try {
      await api.saveFile(engine.key, selected, "auth", authText);
      setAuthRaw(authText);
      await refresh(selected);
      flash("ok", "Saved");
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onLaunch(runCli: boolean) {
    if (!engine || !selected) return;
    const cliArgs = args.trim() ? args.trim().split(/\s+/) : [];
    // Remember cwd for this profile
    saveWorkDir(engine.key, selected, workDir);
    // Immediate feedback — spawn is fire-and-forget after this returns
    flash("info", runCli ? "Starting…" : "Opening terminal…");
    try {
      await api.launch(engine.key, selected, workDir.trim() || null, runCli, cliArgs);
      flash("ok", runCli ? "Launched" : "Terminal opened");
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onShare(all: boolean) {
    if (!engine) return;
    const msg = all
      ? `Share all ${engine.label} profiles to:\n${sharedHome}\n\nClose running CLI windows first.`
      : `Share “${selected}” to:\n${sharedHome}\n\nClose running CLI windows first.`;
    if (!confirm(msg)) return;
    try {
      setBusy(true);
      if (all) await api.shareAll(engine.key);
      else if (selected) await api.shareSessions(engine.key, selected);
      await refresh(selected);
      flash("ok", "Sessions shared");
    } catch (e) {
      flash("error", String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDoctor() {
    if (!engine) return;
    try {
      const t = await api.doctor(engine.key, selected);
      const s = await api.shareStatus(engine.key, selected);
      setDoctorText(`${t}\n\n${s}`);
      setDoctorOpen(true);
    } catch (e) {
      flash("error", String(e));
    }
  }


  async function openCache() {
    if (!engine) return;
    try {
      setCacheBusy(true);
      const report = await api.cacheReport(engine.key);
      setCacheReport(report);
      setSandboxRootInput(report.sandboxCacheRoot || "");
      try {
        const base = await api.getProfilesBase();
        if (base) setProfilesRootInput(base);
        else {
          // parent of current engine root if ends with CodexProfiles/ClaudeProfiles
          const pr = report.profilesRoot || "";
          const m = pr.replace(/[\\/]+$/, "").match(/^(.*)[\\/](CodexProfiles|ClaudeProfiles)$/i);
          setProfilesRootInput(m ? m[1] : pr);
        }
      } catch {
        setProfilesRootInput(report.profilesRoot || "");
      }
      setCacheOpen(true);
    } catch (e) {
      flash("error", String(e));
    } finally {
      setCacheBusy(false);
    }
  }

  async function onCleanAllCaches() {
    if (!engine) return;
    if (!confirm("Clean sandbox/tmp cache for ALL profiles?\n\nCloses running CLI first.\nDoes NOT delete configs or sessions.")) return;
    try {
      setCacheBusy(true);
      const r = await api.cleanAllCaches(engine.key, true);
      const freed = Number(r.totalFreedBytes || 0);
      flash("ok", `Freed ${formatBytes(freed)}`);
      setCacheReport(await api.cacheReport(engine.key));
    } catch (e) {
      flash("error", String(e));
    } finally {
      setCacheBusy(false);
    }
  }

  async function onCleanOneCache(name: string) {
    if (!engine) return;
    if (!confirm(`Clean cache for "${name}"?\n(.sandbox-bin / .tmp only)`)) return;
    try {
      setCacheBusy(true);
      const r = await api.cleanProfileCache(engine.key, name, true);
      flash("ok", `Freed ${formatBytes(Number(r.freedBytes || 0))}`);
      setCacheReport(await api.cacheReport(engine.key));
    } catch (e) {
      flash("error", String(e));
    } finally {
      setCacheBusy(false);
    }
  }

  async function onApplySandboxRoot() {
    if (!engine) return;
    const root = sandboxRootInput.trim() || null;
    const msg = root
      ? `Move .sandbox-bin for all profiles under:\n${root}\n\nExisting folders will be moved when possible.\nClose Codex first.`
      : "Clear custom sandbox cache location?\n(Existing junctions are left as-is.)";
    if (!confirm(msg)) return;
    try {
      setCacheBusy(true);
      await api.setSandboxCacheRoot(engine.key, root, true);
      flash("ok", root ? "Sandbox cache location applied" : "Sandbox cache location cleared");
      setCacheReport(await api.cacheReport(engine.key));
    } catch (e) {
      flash("error", String(e));
    } finally {
      setCacheBusy(false);
    }
  }


  async function onApplyProfilesRoot() {
    if (!engine) return;
    const dest = profilesRootInput.trim();
    if (!dest) {
      flash("error", "Enter a parent folder (both Codex + Claude go under it)");
      return;
    }
    if (
      !confirm(
        `Move BOTH profile trees under:\n${dest}\n\n` +
          `  ${dest}\\CodexProfiles\n` +
          `  ${dest}\\ClaudeProfiles\n\n` +
          `Close Codex and Claude Code first.\n` +
          (leaveJunction
            ? "Junctions will be left at the old locations."
            : "Old locations will not keep junctions.")
      )
    ) {
      return;
    }
    try {
      setCacheBusy(true);
      const r = await api.setProfilesBase(dest, leaveJunction);
      flash("ok", `Profiles base → ${r.profilesBase || dest}`);
      const report = await api.cacheReport(engine.key);
      setCacheReport(report);
      const base = (await api.getProfilesBase()) || dest;
      setProfilesRootInput(String(base));
      await refresh(selected);
    } catch (e) {
      flash("error", String(e));
    } finally {
      setCacheBusy(false);
    }
  }

  async function onPickProfilesRoot() {
    try {
      const p = await api.pickFolder();
      if (p) setProfilesRootInput(p);
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onPickSandboxRoot() {
    try {
      const p = await api.pickFolder();
      if (p) setSandboxRootInput(p);
    } catch (e) {
      flash("error", String(e));
    }
  }

  async function onBrowse() {
    if (!engine || !selected) return;
    try {
      const p = await api.pickFolder();
      if (p) {
        setWorkDir(p);
        saveWorkDir(engine.key, selected, p);
      }
    } catch (e) {
      flash("error", String(e));
    }
  }

  if (!engine) {
    return (
      <div className="app">

      <div className="titlebar" data-tauri-drag-region>
        <div className="titlebar-left" data-tauri-drag-region>
          <span className="titlebar-title" data-tauri-drag-region>
            Profile Isolator
          </span>
        </div>
        <div className="titlebar-right">
<div className="titlebar-controls">
          <button type="button" className="win-btn" onClick={winMinimize} aria-label="Minimize">
            <svg width="10" height="1" viewBox="0 0 10 1"><rect width="10" height="1" fill="currentColor"/></svg>
          </button>
          <button type="button" className="win-btn" onClick={winToggleMax} aria-label="Maximize">
            {maximized ? (
              <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 3h5v5H2V3zm1-1h5v5" fill="none" stroke="currentColor" strokeWidth="1"/></svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1"/></svg>
            )}
          </button>
          <button type="button" className="win-btn close" onClick={winClose} aria-label="Close">
            <svg width="10" height="10" viewBox="0 0 10 10"><path d="M1 1l8 8M9 1L1 9" stroke="currentColor" strokeWidth="1.2"/></svg>
          </button>
          </div>
        </div>
      </div>

        <div className="empty">
          <h3>Loading</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="app">

      <div className="titlebar" data-tauri-drag-region>
        <div className="titlebar-left" data-tauri-drag-region>
          <span className="titlebar-title" data-tauri-drag-region>
            Profile Isolator
          </span>
        </div>
        <div className="titlebar-right">
<div className="titlebar-controls">
          <button type="button" className="win-btn" onClick={winMinimize} aria-label="Minimize">
            <svg width="10" height="1" viewBox="0 0 10 1"><rect width="10" height="1" fill="currentColor"/></svg>
          </button>
          <button type="button" className="win-btn" onClick={winToggleMax} aria-label="Maximize">
            {maximized ? (
              <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 3h5v5H2V3zm1-1h5v5" fill="none" stroke="currentColor" strokeWidth="1"/></svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1"/></svg>
            )}
          </button>
          <button type="button" className="win-btn close" onClick={winClose} aria-label="Close">
            <svg width="10" height="10" viewBox="0 0 10 10"><path d="M1 1l8 8M9 1L1 9" stroke="currentColor" strokeWidth="1.2"/></svg>
          </button>
          </div>
        </div>
      </div>

      <div className="shell">
      <aside className="sidebar">
        <div className="side-top">
          <div className="seg">
            {engines.map((e) => (
              <button
                key={e.key}
                className={e.key === engineKey ? "on" : ""}
                onClick={() => setEngineKey(e.key)}
              >
                {e.label}
              </button>
            ))}
          </div>
          <div className="root-path" title={root}>
            {root || "—"}
          </div>
        </div>

        <div className="section">
          <span>Profiles</span>
          <span className="n">{profiles.length}</span>
        </div>

<div
          ref={listRef}
          className={`list${draggingName ? " reordering" : ""}`}
        >
          {profiles.map((p, index) => (
            <div
              key={p.name}
              data-name={p.name}
              className={[
                "item",
                selected === p.name ? "on" : "",
                draggingName === p.name ? "dragging" : "",
                dropIndex === index && draggingName && draggingName !== p.name
                  ? "drop-target"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => {
                if (renaming || draggingName) return;
                selectedByEngine.current[engine.key] = p.name;
                setSelected(p.name);
              }}
              onDoubleClick={(e) => {
                e.stopPropagation();
                if ((e.target as HTMLElement).closest(".drag-handle, .item-actions")) return;
                startRename(p.name);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (renaming === p.name) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  selectedByEngine.current[engine.key] = p.name;
                  setSelected(p.name);
                }
                if (e.key === "F2") {
                  e.preventDefault();
                  startRename(p.name);
                }
              }}
            >
              <button
                type="button"
                className="drag-handle"
                title="Drag to reorder"
                aria-label={`Reorder ${p.name}`}
                onPointerDown={(e) => beginReorder(p.name, index, e)}
                onClick={(e) => e.stopPropagation()}
              >
                <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor" aria-hidden>
                  <circle cx="3" cy="3" r="1.2" />
                  <circle cx="7" cy="3" r="1.2" />
                  <circle cx="3" cy="8" r="1.2" />
                  <circle cx="7" cy="8" r="1.2" />
                  <circle cx="3" cy="13" r="1.2" />
                  <circle cx="7" cy="13" r="1.2" />
                </svg>
              </button>
              <div className="item-main">
                {renaming === p.name ? (
                  <input
                    ref={renameInputRef}
                    className="rename-input"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => {
                      e.stopPropagation();
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void commitRename();
                      } else if (e.key === "Escape") {
                        e.preventDefault();
                        setRenaming(null);
                      }
                    }}
                    onBlur={() => void commitRename()}
                  />
                ) : (
                  <div className="name" title="Double-click or F2 to rename">
                    {p.name}
                  </div>
                )}
                <div className="model">{p.model || "No model"}</div>
                <div className="url">{p.baseUrl || "—"}</div>
              </div>
              <div className="item-actions">
                {p.isActive && <span className="chip g">In use</span>}
                <button
                  type="button"
                  className="icon-action"
                  title={`Rename “${p.name}”`}
                  aria-label={`Rename ${p.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(p.name);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path
                      d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  className="icon-action"
                  title={`Duplicate “${p.name}”`}
                  aria-label={`Duplicate ${p.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    void onCopy(p.name);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.6" />
                    <path
                      d="M5 15V7a2 2 0 0 1 2-2h8"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  className="icon-action danger"
                  title={`Delete “${p.name}”`}
                  aria-label={`Delete ${p.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    selectedByEngine.current[engine.key] = p.name;
                    setSelected(p.name);
                    window.setTimeout(() => onDelete(p.name), 0);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path d="M4 7h16M9 7V5h6v2m-8 0l1 12h8l1-12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>
          ))}
          {profiles.length === 0 && (
            <div className="empty" style={{ minHeight: 120 }}>
              <p>No profiles yet.</p>
            </div>
          )}
        </div>

        <div className="foot">
          <button
            className="btn primary block"
            onClick={() => {
              setFromCurrent(true);
              setShowNew(true);
            }}
          >
            New Profile
          </button>
          <button
            className="btn block secondary"
            onClick={() => {
              setFromCurrent(true);
              setShowNew(true);
            }}
          >
            Import ~/{engine.defaultHomeName.replace(/^\./, "")}
          </button>
          </div>
      </aside>

      <section className="content">
        {!selectedProfile ? (
          <div className="empty">
            <h3>Select a profile</h3>
            <p>Choose one in the sidebar, or import your current configuration.</p>
          </div>
        ) : (
          <>
            <div className="head">
              <div>
                <h1>{selectedProfile.name}</h1>
                <div className="path">{selectedProfile.path}</div>
              </div>
              <div className="actions">
                <button
                  className="btn primary"
                  onClick={() => onLaunch(true)}
                  title="Start CLI with this profile"
                >
                  Launch
                </button>
                <button
                  type="button"
                  className="btn icon-btn"
                  onClick={cycleTheme}
                  title={`Theme: ${themeLabel} (click to cycle Auto / Light / Dark)`}
                  aria-label={`Theme ${themeLabel}`}
                >
                  {themeIcon}
                </button>
                <div
                  className={`more${moreOpen ? " open" : ""}`}
                  ref={moreRef}
                  onMouseEnter={() => {
                    if (moreLeaveTimer.current != null) {
                      window.clearTimeout(moreLeaveTimer.current);
                      moreLeaveTimer.current = null;
                    }
                  }}
                  onMouseLeave={() => {
                    if (moreLeaveTimer.current != null) {
                      window.clearTimeout(moreLeaveTimer.current);
                    }
                    // Brief delay so moving to the menu doesn't close it mid-flight
                    moreLeaveTimer.current = window.setTimeout(() => setMoreOpen(false), 180);
                  }}
                >
                  <button
                    type="button"
                    className="btn more-btn"
                    title="More"
                    aria-haspopup="menu"
                    aria-expanded={moreOpen}
                    onClick={() => setMoreOpen((v) => !v)}
                  >
                    More
                  </button>
                  {moreOpen && (
                    <div className="more-menu" role="menu">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setMoreOpen(false);
                          void onLaunch(false);
                        }}
                      >
                        Open terminal only
                        <span className="more-desc">Do not auto-run CLI</span>
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setMoreOpen(false);
                          void api.openPath(selectedProfile.path);
                        }}
                      >
                        Open profile folder
                      </button>
                      <div className="more-sep" />
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setMoreOpen(false);
                          void onDoctor();
                        }}
                      >
                        Doctor
                        <span className="more-desc">Check CLI paths and config</span>
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={cacheBusy}
                        onClick={() => {
                          setMoreOpen(false);
                          void openCache();
                        }}
                      >
                        Cache & storage
                        <span className="more-desc">Size, clean sandbox, move cache folder</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="metrics">
              <div className="metric">
                <div className="k">Model</div>
                <div className="v">{selectedProfile.model || "—"}</div>
              </div>
              <div className="metric">
                <div className="k">Provider</div>
                <div className="v">
                  {selectedProfile.providerName || selectedProfile.provider || "—"}
                </div>
              </div>
              <div className="metric">
                <div className="k">Endpoint</div>
                <div className="v">{selectedProfile.baseUrl || "—"}</div>
              </div>
            </div>

            <div className="tabs">
                              {(
                  [
                    ["config", engine.key === "claude" ? "Settings" : "Config"],
                    ["auth", engine.key === "claude" ? "MCP OAuth" : "Auth"],
                    ["launch", "Working directory"],
                  ] as const
                ).map(([id, label]) => (
                <button
                  key={id}
                  className={tab === id ? "on" : ""}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "config" && (
                <div className="pane">
                  {engine.key === "claude" && (
                    <div className="hint">
                      {`Primary Claude config. Put API routing under env:
  ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL`}
                    </div>
                  )}
                  <div className="pane-bar">
                  <span className="file">{engine.primaryLabel}</span>
                  <div className="right">
                    {engine.key === "claude" && (
                      <label>
                        <input
                          type="checkbox"
                          checked={mask}
                          onChange={async (e) => {
                            const m = e.target.checked;
                            setMask(m);
                            if (m) {
                              setConfigText(await api.maskSecret(engine.key, configRaw));
                              setAuthText(await api.maskSecret(engine.key, authRaw));
                            } else {
                              setConfigText(configRaw);
                              setAuthText(authRaw);
                            }
                          }}
                        />
                        Mask secrets
                      </label>
                    )}
                    <button
                      className="btn ghost sm"
                      onClick={async () => {
                        if (!selected) return;
                        const cfg = await api.readFile(engine.key, selected, "config");
                        setConfigRaw(cfg);
                        setConfigText(mask ? await api.maskSecret(engine.key, cfg) : cfg);
                      }}
                    >
                      Reload
                    </button>
                    <button className="btn primary sm" onClick={onSaveConfig}>
                      Save
                    </button>
                  </div>
                </div>
                <textarea
                  className="editor"
                  value={configText}
                  onChange={(e) => setConfigText(e.target.value)}
                  spellCheck={false}
                />
              </div>
            )}

            {tab === "auth" && (
                <div className="pane">
                  {engine.key === "claude" ? (
                    <div className="hint">
                      {`.credentials.json stores MCP OAuth state only.
API key / base URL / model live in Settings (settings.json → env).`}
                    </div>
                  ) : (
                    <div className="hint">
                      {`Codex API key is here in auth.json (OPENAI_API_KEY).
Provider / base_url / model are in config.toml (Config tab).`}
                    </div>
                  )}
                  <div className="pane-bar">
                    {engine.key === "codex" ? (
                      <label>
                        <input
                          type="checkbox"
                          checked={mask}
                          onChange={async (e) => {
                            const m = e.target.checked;
                            setMask(m);
                            setAuthText(
                              m ? await api.maskSecret(engine.key, authRaw) : authRaw
                            );
                          }}
                        />
                        Mask secrets
                      </label>
                    ) : (
                      <span className="file">{engine.secondaryLabel}</span>
                    )}
                    <div className="right">
                      <button
                        className="btn ghost sm"
                        onClick={async () => {
                          if (!selected) return;
                          const a = await api.readFile(engine.key, selected, "auth");
                          setAuthRaw(a);
                          // Claude MCP file: never mask. Codex auth: respect mask.
                          setAuthText(
                            engine.key === "codex" && mask
                              ? await api.maskSecret(engine.key, a)
                              : a
                          );
                        }}
                      >
                        Reload
                      </button>
                      <button className="btn primary sm" onClick={onSaveAuth}>
                        Save
                      </button>
                    </div>
                  </div>
                  <textarea
                    className="editor"
                    value={authText}
                    onChange={(e) => {
                      setAuthText(e.target.value);
                      if (engine.key !== "codex" || !mask) setAuthRaw(e.target.value);
                    }}
                    readOnly={engine.key === "codex" && mask}
                    spellCheck={false}
                  />
                </div>
              )}

            {tab === "launch" && (
              <div className="pane">
                <div className="field">
                  <span>Working directory</span>
                  <div className="field-row">
                    <input
                      type="text"
                      value={workDir}
                      onChange={(e) => {
                        const v = e.target.value;
                        setWorkDir(v);
                        if (engine && selected) saveWorkDir(engine.key, selected, v);
                      }}
                      placeholder="Project folder (remembered per profile)"
                    />
                    <button className="btn" onClick={onBrowse}>
                      Browse
                    </button>
                  </div>
                </div>
                <div className="field">
                  <span>Extra arguments</span>
                  <input
                    type="text"
                    value={args}
                    onChange={(e) => setArgs(e.target.value)}
                    placeholder="e.g. resume"
                  />
                </div>
                <div className="hint">
                  Opens PowerShell with {engine.homeEnv} set only for this profile.
                  Working directory is remembered for each profile.
                </div>
              </div>
            )}
            <div className="flags">
              <span className={`chip ${selectedProfile.hasConfig ? "g" : "r"}`}>
                {engine.primaryLabel}
              </span>
              <span className={`chip ${selectedProfile.hasAuth ? "g" : "r"}`}>
                {engine.secondaryLabel}
              </span>
              
              {selectedProfile.hasCatalog && <span className="chip o">Catalog</span>}
            </div>
          </>
        )}
      </section>
      </div>

      {showNew && (
        <div className="scrim" onClick={() => setShowNew(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New {engine.label} Profile</h3>
            <div className="field">
              <span>Name</span>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && onCreate()}
              />
            </div>
            <label className="checkline">
              <input
                type="checkbox"
                checked={fromCurrent}
                onChange={(e) => setFromCurrent(e.target.checked)}
              />
              <span>Import from ~/{engine.defaultHomeName}</span>
            </label>
            <div className="actions">
              <button className="btn block secondary" onClick={() => setShowNew(false)}>
                Cancel
              </button>
              <button className="btn primary block" onClick={onCreate} disabled={busy}>
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {doctorOpen && (
        <div className="scrim" onClick={() => setDoctorOpen(false)}>
          <div className="modal wide" onClick={(e) => e.stopPropagation()}>
            <h3>Diagnostics</h3>
            <textarea className="editor" style={{ minHeight: 300 }} readOnly value={doctorText} />
            <div className="actions single">
              <button className="btn primary block" onClick={() => setDoctorOpen(false)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      
      {cacheOpen && cacheReport && (
        <div className="scrim" onClick={() => setCacheOpen(false)}>
          <div className="modal wide" onClick={(e) => e.stopPropagation()}>
            <h3>Cache & storage</h3>
            <div className="hint" style={{ marginBottom: 10 }}>
              {`Local size only (shared sessions junctions not counted).
Sandbox cache is .sandbox-bin (often ~300MB each if not relocated).`}
            </div>
            <div className="cache-total">
              Total local: <strong>{formatBytes(cacheReport.totalLocalBytes)}</strong>
              <span className="cache-root"> · {cacheReport.profilesRoot}</span>
            </div>

            <div className="cache-list">
              {cacheReport.profiles.map((p) => (
                <div key={p.profile} className="cache-row">
                  <div className="cache-row-main">
                    <div className="name">{p.profile}</div>
                    <div className="model">{formatBytes(p.localBytes)}</div>
                    <div className="url">
                      {p.entries
                        .filter((e) => e.bytes > 0 || e.isJunction)
                        .slice(0, 4)
                        .map((e) =>
                          e.isJunction
                            ? `${e.name}→shared`
                            : `${e.name} ${formatBytes(e.bytes)}`
                        )
                        .join(" · ") || "—"}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn sm"
                    disabled={cacheBusy}
                    onClick={() => onCleanOneCache(p.profile)}
                  >
                    Clean
                  </button>
                </div>
              ))}
            </div>

            <div className="field" style={{ marginTop: 14 }}>
              <span>Profiles parent folder (Codex + Claude together)</span>
              <div className="field-row">
                <input
                  type="text"
                  value={profilesRootInput}
                  onChange={(e) => setProfilesRootInput(e.target.value)}
                  placeholder="e.g. F:\CodexProfiles"
                />
                <button type="button" className="btn" onClick={onPickProfilesRoot}>
                  Browse
                </button>
              </div>
              <label className="checkline" style={{ marginTop: 8 }}>
                <input
                  type="checkbox"
                  checked={leaveJunction}
                  onChange={(e) => setLeaveJunction(e.target.checked)}
                />
                <span>Leave junctions at old paths (Users\...\CodexProfiles & ClaudeProfiles)</span>
              </label>
              <div className="hint">
                {`Creates/moves under the parent folder:
  <parent>\\CodexProfiles
  <parent>\\ClaudeProfiles
Saved in ~/.profile-isolator/global.json. Sessions stay at ~/.codex.`}
              </div>
            </div>

            <div className="field" style={{ marginTop: 12 }}>
              <span>Sandbox cache only (optional)</span>
              <div className="field-row">
                <input
                  type="text"
                  value={sandboxRootInput}
                  onChange={(e) => setSandboxRootInput(e.target.value)}
                  placeholder="e.g. F:\CodexSandboxCache (empty = under each profile)"
                />
                <button type="button" className="btn" onClick={onPickSandboxRoot}>
                  Browse
                </button>
              </div>
              <div className="hint">
                Only relocates .sandbox-bin. Prefer moving the whole Profiles folder above if that is your goal.
              </div>
            </div>

            <div className="row-btns" style={{ marginTop: 12 }}>
              <button type="button" className="btn primary" disabled={cacheBusy} onClick={onApplyProfilesRoot}>
                Move both engines
              </button>
              <button type="button" className="btn" disabled={cacheBusy} onClick={onApplySandboxRoot}>
                Apply sandbox path
              </button>
              <button type="button" className="btn" disabled={cacheBusy} onClick={onCleanAllCaches}>
                Clean all caches
              </button>
              <button type="button" className="btn" onClick={() => setCacheOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.kind}`}>{toast.text}</div>}
    </div>
  );
}
