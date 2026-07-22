"""
Multi-CLI Profile Isolator — modern desktop GUI

One app, two engines:
  Codex        -> CODEX_HOME        (config.toml + auth.json)
  Claude Code  -> CLAUDE_CONFIG_DIR (settings.json + .credentials.json)

Each terminal can use a different provider/model/key without affecting others,
while sessions can be shared so `resume` sees a project across providers.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from engines import ENGINES, CODEX, CLAUDE, Engine
from core import (
    ProfileSummary,
    create_profile,
    delete_profile,
    doctor_report,
    enable_shared_sessions,
    enable_shared_sessions_all,
    ensure_root,
    find_cli_command,
    get_default_home,
    get_engine,
    get_profiles_root,
    get_shared_session_home,
    list_profiles,
    mask_api_key,
    open_in_explorer,
    read_profile_file,
    safe_launch_directory,
    save_profile_file,
    session_share_status,
    start_profile_session,
)
from theme import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_RING,
    ACCENT_SOFT,
    BG,
    BORDER,
    BORDER_SOFT,
    DANGER,
    DANGER_BG,
    GOOD,
    GOOD_BG,
    INFO,
    INFO_BG,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XS,
    SURFACE,
    SURFACE_2,
    SURFACE_3,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARN,
    WARN_BG,
)

# Back-compat aliases used by remaining code paths
PANEL = SURFACE
PANEL2 = SURFACE_2
MUTED = TEXT_MUTED
CARD = SURFACE_2

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _pill(parent, text: str, *, fg: str, bg: str):
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=fg,
        fg_color=bg,
        corner_radius=RADIUS_XS,
        padx=7,
        pady=2,
    )


class ProfileCard(ctk.CTkFrame):
    def __init__(self, master, profile: ProfileSummary, selected: bool, on_click, **kwargs):
        fill = SURFACE_3 if selected else SURFACE_2
        edge = ACCENT_RING if selected else BORDER
        super().__init__(master, fg_color=fill, corner_radius=RADIUS_MD, **kwargs)
        self.profile = profile
        self.on_click = on_click
        self.configure(border_width=1, border_color=edge)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
        top.grid_columnconfigure(0, weight=1)

        name = ctk.CTkLabel(
            top,
            text=profile.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
            anchor="w",
        )
        name.grid(row=0, column=0, sticky="w")

        if profile.is_active:
            _pill(top, "ACTIVE", fg=GOOD, bg=GOOD_BG).grid(row=0, column=1, sticky="e")
        elif profile.sessions_shared:
            _pill(top, "SHARED", fg=INFO, bg=INFO_BG).grid(row=0, column=1, sticky="e")

        model = profile.model or "No model"
        ctk.CTkLabel(
            self,
            text=model,
            text_color=TEXT_SECONDARY,
            anchor="w",
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 0))

        host = profile.base_url or "—"
        ctk.CTkLabel(
            self,
            text=host,
            text_color=TEXT_FAINT,
            anchor="w",
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 12))

        self._bind_recursive(self)

    def _bind_recursive(self, widget):
        widget.bind("<Button-1>", self._click)
        for child in widget.winfo_children():
            self._bind_recursive(child)

    def _click(self, _event=None):
        self.on_click(self.profile.name)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI CLI Profile Isolator")
        self.geometry("1120x740")
        self.minsize(940, 620)
        self.configure(fg_color=BG)

        self.engine: Engine = ENGINES["codex"]
        self.selected: Optional[str] = None
        self.profiles: list[ProfileSummary] = []
        self.auth_raw = ""
        self._mask_auth = tk.BooleanVar(value=True)
        # remember selection per engine so switching tabs feels stateful
        self._last_selected: dict = {}

        ensure_root(self.engine)
        self._build()
        self._apply_engine_labels()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Top bar: brand + engine switcher + quiet actions
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 0))
        topbar.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(topbar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")
        self.lbl_title = ctk.CTkLabel(
            brand,
            text="Profile Isolator",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT,
        )
        self.lbl_title.pack(anchor="w")
        self.lbl_root = ctk.CTkLabel(
            brand,
            text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.lbl_root.pack(anchor="w", pady=(1, 0))

        self.engine_tabs = ctk.CTkSegmentedButton(
            topbar,
            values=[e.label for e in ENGINES.values()],
            command=self._on_engine_change,
            fg_color=SURFACE_2,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=SURFACE_2,
            unselected_hover_color=SURFACE_3,
            font=ctk.CTkFont(size=13),
            height=34,
            corner_radius=RADIUS_SM,
        )
        self.engine_tabs.set(self.engine.label)
        self.engine_tabs.grid(row=0, column=1, sticky="", padx=16)

        actions = ctk.CTkFrame(topbar, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e")
        for text, cmd in (
            ("Refresh", self.refresh),
            ("Folder", self.open_root),
            ("Doctor", self.show_doctor),
        ):
            ctk.CTkButton(
                actions,
                text=text,
                width=72,
                height=32,
                fg_color="transparent",
                hover_color=SURFACE_3,
                border_width=1,
                border_color=BORDER,
                text_color=TEXT_SECONDARY,
                corner_radius=RADIUS_SM,
                command=cmd,
            ).pack(side="left", padx=3)
        ctk.CTkButton(
            actions,
            text="Share",
            width=72,
            height=32,
            fg_color=SURFACE_2,
            hover_color=SURFACE_3,
            border_width=1,
            border_color=BORDER_SOFT,
            text_color=TEXT,
            corner_radius=RADIUS_SM,
            command=self.share_all_sessions,
        ).pack(side="left", padx=(8, 0))

        # Spacer row (keeps previous grid indices stable for body/footer)
        header = ctk.CTkFrame(self, fg_color="transparent", height=4)
        header.grid(row=1, column=0, sticky="ew")

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=20, pady=12)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left panel
        left = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=RADIUS_LG, border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.configure(width=300)

        left_top = ctk.CTkFrame(left, fg_color="transparent")
        left_top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        left_top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            left_top,
            text="Profiles",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")
        self.lbl_count = ctk.CTkLabel(left_top, text="0", text_color=TEXT_FAINT, font=ctk.CTkFont(size=12))
        self.lbl_count.grid(row=0, column=1, sticky="e")

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent", corner_radius=0)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.list_frame.grid_columnconfigure(0, weight=1)

        left_btns = ctk.CTkFrame(left, fg_color="transparent")
        left_btns.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
        left_btns.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            left_btns,
            text="New profile",
            height=36,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_SM,
            command=lambda: self.dialog_new(from_current_default=True),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.btn_import = ctk.CTkButton(
            left_btns,
            text="Import current",
            height=34,
            fg_color="transparent",
            hover_color=SURFACE_3,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SECONDARY,
            corner_radius=RADIUS_SM,
            command=lambda: self.dialog_new(from_current_default=True, force_import=True),
        )
        self.btn_import.grid(row=1, column=0, sticky="ew")

        # Right panel
        right = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=RADIUS_LG, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.empty = ctk.CTkFrame(right, fg_color="transparent")
        self.empty.grid(row=0, column=0, rowspan=4, sticky="nsew")
        ctk.CTkLabel(
            self.empty,
            text="No profile selected",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT,
        ).place(relx=0.5, rely=0.44, anchor="center")
        self.lbl_empty_hint = ctk.CTkLabel(
            self.empty,
            text="Import the current config or create a blank profile.",
            text_color=TEXT_MUTED,
        )
        self.lbl_empty_hint.place(relx=0.5, rely=0.51, anchor="center")

        self.detail = ctk.CTkFrame(right, fg_color="transparent")
        self.detail.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)
        self.detail.grid_rowconfigure(2, weight=1)
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_remove()

        dhead = ctk.CTkFrame(self.detail, fg_color="transparent")
        dhead.grid(row=0, column=0, sticky="ew")
        dhead.grid_columnconfigure(0, weight=1)
        self.lbl_name = ctk.CTkLabel(
            dhead, text="-", font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT, anchor="w"
        )
        self.lbl_name.grid(row=0, column=0, sticky="w")
        self.lbl_path = ctk.CTkLabel(
            dhead, text="-", text_color=TEXT_MUTED, anchor="w", font=ctk.CTkFont(size=11)
        )
        self.lbl_path.grid(row=1, column=0, sticky="w", pady=(2, 0))

        dbtns = ctk.CTkFrame(dhead, fg_color="transparent")
        dbtns.grid(row=0, column=1, rowspan=2, sticky="e")
        self.btn_launch = ctk.CTkButton(
            dbtns,
            text="Launch",
            width=108,
            height=34,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_SM,
            command=self.launch_cli,
        )
        self.btn_launch.pack(side="left", padx=3)
        ctk.CTkButton(
            dbtns,
            text="Terminal",
            width=92,
            height=34,
            fg_color="transparent",
            hover_color=SURFACE_3,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SECONDARY,
            corner_radius=RADIUS_SM,
            command=self.open_terminal,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            dbtns,
            text="Delete",
            width=72,
            height=34,
            fg_color="transparent",
            hover_color=DANGER_BG,
            border_width=1,
            border_color=BORDER,
            text_color=DANGER,
            corner_radius=RADIUS_SM,
            command=self.delete_selected,
        ).pack(side="left", padx=3)

        meta = ctk.CTkFrame(self.detail, fg_color="transparent")
        meta.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        for i in range(3):
            meta.grid_columnconfigure(i, weight=1)
        self.meta_model = self._meta_card(meta, "MODEL", 0)
        self.meta_provider = self._meta_card(meta, "PROVIDER", 1)
        self.meta_base = self._meta_card(meta, "BASE URL", 2)

        # tabs
        self.tabs = ctk.CTkTabview(
            self.detail,
            fg_color=SURFACE_2,
            segmented_button_fg_color=SURFACE,
            segmented_button_selected_color=SURFACE_3,
            segmented_button_selected_hover_color=SURFACE_3,
            segmented_button_unselected_color=SURFACE,
            segmented_button_unselected_hover_color=SURFACE_2,
            text_color=TEXT_MUTED,
            text_color_disabled=TEXT_FAINT,
            corner_radius=RADIUS_MD,
            border_width=1,
            border_color=BORDER,
        )
        self.tabs.grid(row=2, column=0, sticky="nsew")
        self._tab_primary = self.tabs.add("Config")
        self._tab_secondary = self.tabs.add("Credentials")
        tab_launch = self.tabs.add("Launch")
        tab_sessions = self.tabs.add("Sessions")

        self._tab_primary.grid_rowconfigure(0, weight=1)
        self._tab_primary.grid_columnconfigure(0, weight=1)
        self.txt_config = ctk.CTkTextbox(
            self._tab_primary,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG,
            border_width=1,
            border_color=BORDER,
            corner_radius=RADIUS_SM,
            text_color=TEXT,
        )
        self.txt_config.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        cfg_btns = ctk.CTkFrame(self._tab_primary, fg_color="transparent")
        cfg_btns.grid(row=1, column=0, sticky="e", padx=10, pady=10)
        ctk.CTkButton(
            cfg_btns, text="Reload", width=80, height=32, fg_color="transparent", hover_color=SURFACE_3,
            border_width=1, border_color=BORDER, text_color=TEXT_SECONDARY, corner_radius=RADIUS_SM,
            command=self.reload_config,
        ).pack(side="left", padx=4)
        self.btn_save_cfg = ctk.CTkButton(
            cfg_btns, text="Save", width=100, height=32, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#FFFFFF", corner_radius=RADIUS_SM, command=self.save_config,
        )
        self.btn_save_cfg.pack(side="left", padx=4)

        self._tab_secondary.grid_rowconfigure(1, weight=1)
        self._tab_secondary.grid_columnconfigure(0, weight=1)
        auth_top = ctk.CTkFrame(self._tab_secondary, fg_color="transparent")
        auth_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        ctk.CTkCheckBox(
            auth_top, text="Mask secrets", variable=self._mask_auth, command=self._refresh_auth_view,
            text_color=TEXT_MUTED, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER_SOFT,
        ).pack(side="left")
        self.txt_auth = ctk.CTkTextbox(
            self._tab_secondary,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG,
            border_width=1,
            border_color=BORDER,
            corner_radius=RADIUS_SM,
            text_color=TEXT,
        )
        self.txt_auth.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        auth_btns = ctk.CTkFrame(self._tab_secondary, fg_color="transparent")
        auth_btns.grid(row=2, column=0, sticky="e", padx=10, pady=10)
        ctk.CTkButton(
            auth_btns, text="Reload", width=80, height=32, fg_color="transparent", hover_color=SURFACE_3,
            border_width=1, border_color=BORDER, text_color=TEXT_SECONDARY, corner_radius=RADIUS_SM,
            command=self.reload_auth,
        ).pack(side="left", padx=4)
        self.btn_save_auth = ctk.CTkButton(
            auth_btns, text="Save", width=100, height=32, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#FFFFFF", corner_radius=RADIUS_SM, command=self.save_auth,
        )
        self.btn_save_auth.pack(side="left", padx=4)

        # launch tab
        tab_launch.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tab_launch, text="Working directory", text_color=TEXT_MUTED, anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(16, 6)
        )
        wd_row = ctk.CTkFrame(tab_launch, fg_color="transparent")
        wd_row.grid(row=1, column=0, sticky="ew", padx=14)
        wd_row.grid_columnconfigure(0, weight=1)
        self.entry_wd = ctk.CTkEntry(
            wd_row, height=34, fg_color=BG, border_color=BORDER, corner_radius=RADIUS_SM, text_color=TEXT,
        )
        self.entry_wd.grid(row=0, column=0, sticky="ew")
        self.entry_wd.insert(0, safe_launch_directory())
        ctk.CTkButton(
            wd_row, text="Browse", width=84, height=34, fg_color="transparent", hover_color=SURFACE_3,
            border_width=1, border_color=BORDER, text_color=TEXT_SECONDARY, corner_radius=RADIUS_SM,
            command=self.browse_wd,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkLabel(tab_launch, text="Extra args", text_color=TEXT_MUTED, anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w", padx=14, pady=(14, 6)
        )
        self.entry_args = ctk.CTkEntry(
            tab_launch, height=34, fg_color=BG, border_color=BORDER, corner_radius=RADIUS_SM,
            text_color=TEXT, placeholder_text="e.g. resume",
        )
        self.entry_args.grid(row=3, column=0, sticky="ew", padx=14)
        self.lbl_launch_hint = ctk.CTkLabel(tab_launch, text="", text_color=TEXT_FAINT, justify="left", anchor="w")
        self.lbl_launch_hint.grid(row=4, column=0, sticky="w", padx=14, pady=(14, 10))

        # sessions tab
        tab_sessions.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab_sessions, text="Shared sessions", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(16, 6))
        self.lbl_sessions_help = ctk.CTkLabel(tab_sessions, text="", text_color=TEXT_MUTED, justify="left", anchor="w")
        self.lbl_sessions_help.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        self.lbl_session_status = ctk.CTkLabel(
            tab_sessions, text="Status: -", text_color=INFO, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_session_status.grid(row=2, column=0, sticky="w", padx=14, pady=(4, 6))
        self.lbl_session_detail = ctk.CTkLabel(tab_sessions, text="", text_color=TEXT_FAINT, anchor="w", justify="left")
        self.lbl_session_detail.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))
        sess_btns = ctk.CTkFrame(tab_sessions, fg_color="transparent")
        sess_btns.grid(row=4, column=0, sticky="w", padx=14, pady=(4, 8))
        ctk.CTkButton(
            sess_btns, text="Share this", width=110, height=32, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#FFFFFF", corner_radius=RADIUS_SM, command=self.share_selected_sessions,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            sess_btns, text="Share all", width=100, height=32, fg_color="transparent", hover_color=SURFACE_3,
            border_width=1, border_color=BORDER, text_color=TEXT_SECONDARY, corner_radius=RADIUS_SM,
            command=self.share_all_sessions,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            sess_btns, text="Refresh", width=84, height=32, fg_color="transparent", hover_color=SURFACE_3,
            border_width=1, border_color=BORDER, text_color=TEXT_SECONDARY, corner_radius=RADIUS_SM,
            command=self.refresh_session_status,
        ).pack(side="left")
        self.lbl_shared_home = ctk.CTkLabel(tab_sessions, text="", text_color=TEXT_FAINT, anchor="w")
        self.lbl_shared_home.grid(row=5, column=0, sticky="w", padx=14, pady=(12, 10))

        # badges
        badges = ctk.CTkFrame(self.detail, fg_color="transparent")
        badges.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.badge_config = ctk.CTkLabel(
            badges, text="config: ok", text_color=GOOD, fg_color=GOOD_BG, corner_radius=RADIUS_XS, padx=8, pady=3,
        )
        self.badge_config.pack(side="left", padx=(0, 6))
        self.badge_auth = ctk.CTkLabel(
            badges, text="auth: ok", text_color=GOOD, fg_color=GOOD_BG, corner_radius=RADIUS_XS, padx=8, pady=3,
        )
        self.badge_auth.pack(side="left", padx=(0, 6))
        self.badge_catalog = ctk.CTkLabel(
            badges, text="model_catalog_json", text_color=WARN, fg_color=WARN_BG, corner_radius=RADIUS_XS, padx=8, pady=3,
        )

        # Footer
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=20, pady=(2, 12))
        foot.grid_columnconfigure(0, weight=1)
        self.lbl_status = ctk.CTkLabel(foot, text="Ready", text_color=TEXT_MUTED, anchor="w", font=ctk.CTkFont(size=11))
        self.lbl_status.grid(row=0, column=0, sticky="w")
        self.lbl_foot_right = ctk.CTkLabel(foot, text="", text_color=TEXT_FAINT, font=ctk.CTkFont(size=11))
        self.lbl_foot_right.grid(row=0, column=1, sticky="e")

    # ------------------------------------------------------------ engine
    def _on_engine_change(self, label: str):
        key = next((e.key for e in ENGINES.values() if e.label == label), None)
        if key:
            self.switch_engine(key)

    def switch_engine(self, key: str):
        if key == self.engine.key:
            return
        # remember current selection for the engine we are leaving
        if self.selected:
            self._last_selected[self.engine.key] = self.selected
        self.engine = get_engine(key)
        self.selected = self._last_selected.get(key)
        self.auth_raw = ""
        self._apply_engine_labels()
        self.refresh(select=self.selected)

    def _apply_engine_labels(self):
        e = self.engine
        self.title(f"{e.label} · Profile Isolator")
        self.lbl_title.configure(text=f"{e.label}")
        self.btn_launch.configure(text="Launch")
        self.btn_import.configure(text=f"Import ~/{e.default_home_name}")
        self.btn_save_cfg.configure(text=f"Save {e.primary_label}")
        self.btn_save_auth.configure(text=f"Save {e.secondary_label}")
        self.lbl_foot_right.configure(text=f"{e.home_env}  ·  per-terminal isolation")
        self.lbl_launch_hint.configure(
            text=f"Opens a new PowerShell with {e.home_env} set for this profile only."
        )
        self.lbl_sessions_help.configure(
            text=(
                f"Each profile normally has its own {e.home_env}, so resume history splits.\n"
                f"Share session storage to a common home (default ~/{e.default_home_name}).\n"
                f"{e.primary_label} / {e.secondary_label} stay private.\n"
                f"Use the same project folder, or: {e.resume_all_cmd}"
            )
        )
        self.lbl_shared_home.configure(text=f"Shared home: {get_shared_session_home(self.engine)}")

    def _meta_card(self, parent, title: str, col: int) -> ctk.CTkLabel:
        card = ctk.CTkFrame(
            parent,
            fg_color=SURFACE_2,
            corner_radius=RADIUS_MD,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 5, 0 if col == 2 else 5))
        ctk.CTkLabel(
            card,
            text=title,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 0))
        val = ctk.CTkLabel(
            card,
            text="-",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT,
            anchor="w",
            wraplength=200,
        )
        val.pack(fill="x", padx=12, pady=(4, 12))
        return val

    # ---------------------------------------------------------------- data
    def set_status(self, msg: str, level: str = "info"):
        colors = {"ok": GOOD, "warn": WARN, "error": DANGER, "info": TEXT_MUTED}
        self.lbl_status.configure(text=msg, text_color=colors.get(level, TEXT_MUTED))

    def refresh(self, select: Optional[str] = None):
        try:
            ensure_root(self.engine)
            self.lbl_root.configure(text=f"Profiles root: {get_profiles_root(self.engine)}")
            self.profiles = list_profiles(self.engine)
            self.lbl_count.configure(text=str(len(self.profiles)))
            keep = select or self.selected
            self._rebuild_list(keep)
            if keep and any(p.name == keep for p in self.profiles):
                self.select_profile(keep)
            elif self.profiles:
                self.select_profile(self.profiles[0].name)
            else:
                self.selected = None
                self.detail.grid_remove()
                self.empty.grid()
            self.set_status(f"Loaded {len(self.profiles)} {self.engine.label} profile(s)", "ok")
        except Exception as e:
            self.set_status(str(e), "error")
            messagebox.showerror("Error", str(e), parent=self)

    def _rebuild_list(self, selected: Optional[str]):
        for child in self.list_frame.winfo_children():
            child.destroy()
        for i, p in enumerate(self.profiles):
            card = ProfileCard(self.list_frame, p, selected=(p.name == selected), on_click=self.select_profile)
            card.grid(row=i, column=0, sticky="ew", pady=4)

    def select_profile(self, name: str):
        self.selected = name
        self._rebuild_list(name)
        prof = next((p for p in self.profiles if p.name == name), None)
        if not prof:
            self.detail.grid_remove()
            self.empty.grid()
            return
        self.empty.grid_remove()
        self.detail.grid()
        self.lbl_name.configure(text=prof.name)
        self.lbl_path.configure(text=prof.path)
        self.meta_model.configure(text=prof.model or "(not set)")
        prov = " / ".join([x for x in [prof.provider_name, prof.provider] if x]) or "(not set)"
        self.meta_provider.configure(text=prov)
        self.meta_base.configure(text=prof.base_url or "(not set)")

        self.badge_config.configure(
            text=f"{self.engine.primary_label}: ok" if prof.has_config else f"{self.engine.primary_label}: missing",
            text_color=GOOD if prof.has_config else DANGER,
            fg_color=GOOD_BG if prof.has_config else DANGER_BG,
        )
        self.badge_auth.configure(
            text=f"{self.engine.secondary_label}: ok" if prof.has_auth else f"{self.engine.secondary_label}: missing",
            text_color=GOOD if prof.has_auth else DANGER,
            fg_color=GOOD_BG if prof.has_auth else DANGER_BG,
        )
        if prof.has_catalog:
            self.badge_catalog.pack(side="left")
        else:
            self.badge_catalog.pack_forget()

        try:
            self.txt_config.delete("1.0", "end")
            self.txt_config.insert("1.0", read_profile_file(self.engine, name, "config"))
            self.auth_raw = read_profile_file(self.engine, name, "auth")
            self._refresh_auth_view()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
        self.refresh_session_status()

    def _refresh_auth_view(self):
        self.txt_auth.configure(state="normal")
        self.txt_auth.delete("1.0", "end")
        if self._mask_auth.get():
            self.txt_auth.insert("1.0", mask_api_key(self.engine, self.auth_raw))
            self.txt_auth.configure(state="disabled")
        else:
            self.txt_auth.insert("1.0", self.auth_raw)

    # -------------------------------------------------------------- actions
    def dialog_new(self, from_current_default: bool = True, force_import: bool = False):
        e = self.engine
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"New {e.label} Profile")
        dlg.geometry("460x300")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.focus_force()

        ctk.CTkLabel(dlg, text=f"Create {e.label} profile", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(18, 8))
        ctk.CTkLabel(dlg, text="Name", text_color=MUTED).pack(anchor="w", padx=20)
        name_entry = ctk.CTkEntry(dlg, height=36, fg_color="#0E121A", border_color=BORDER)
        name_entry.pack(fill="x", padx=20, pady=(4, 12))
        name_entry.focus()

        from_var = tk.BooleanVar(value=True if force_import else from_current_default)
        ctk.CTkCheckBox(dlg, text=f"Import from current ~/{e.default_home_name}", variable=from_var).pack(anchor="w", padx=20, pady=4)
        ctk.CTkLabel(dlg, text="If unchecked, creates a blank template for you to fill in.", text_color="#667085", wraplength=400, justify="left").pack(anchor="w", padx=20, pady=(4, 12))

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=16)

        def on_create():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("New Profile", "Please enter a profile name.", parent=dlg)
                return
            try:
                create_profile(self.engine, name, from_current=from_var.get(), force=False)
                dlg.destroy()
                self.refresh(select=name)
                self.set_status(f"Created profile '{name}'", "ok")
            except FileExistsError:
                if messagebox.askyesno("Exists", f"Profile '{name}' already exists. Overwrite?", parent=dlg):
                    try:
                        create_profile(self.engine, name, from_current=from_var.get(), force=True)
                        dlg.destroy()
                        self.refresh(select=name)
                        self.set_status(f"Re-created profile '{name}'", "ok")
                    except Exception as ex:
                        messagebox.showerror("Error", str(ex), parent=dlg)
            except Exception as ex:
                messagebox.showerror("Error", str(ex), parent=dlg)

        ctk.CTkButton(btns, text="Cancel", width=100, fg_color=PANEL2, hover_color=BORDER, command=dlg.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Create", width=100, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=on_create).pack(side="right")

    def delete_selected(self):
        if not self.selected:
            return
        if not messagebox.askyesno("Delete profile", f"Delete profile '{self.selected}'?\nThis removes its {self.engine.primary_label} and {self.engine.secondary_label}.", parent=self):
            return
        try:
            delete_profile(self.engine, self.selected)
            self.selected = None
            self.refresh()
            self.set_status("Profile deleted", "ok")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def launch_cli(self):
        if not self.selected:
            return
        if not find_cli_command(self.engine):
            messagebox.showerror("Error", f"{self.engine.command_names[0]} command not found in PATH", parent=self)
            return
        args = self.entry_args.get().strip().split() if self.entry_args.get().strip() else []
        try:
            start_profile_session(self.engine, self.selected, work_dir=self.entry_wd.get().strip() or None, run_cli=True, cli_args=args)
            self.set_status(f"Launched {self.engine.label} with profile '{self.selected}'", "ok")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def open_terminal(self):
        if not self.selected:
            return
        try:
            start_profile_session(self.engine, self.selected, work_dir=self.entry_wd.get().strip() or None, run_cli=False)
            self.set_status(f"Opened terminal with profile '{self.selected}'", "ok")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def browse_wd(self):
        path = filedialog.askdirectory(title="Select working directory", initialdir=self.entry_wd.get() or os.path.expanduser("~"))
        if path:
            self.entry_wd.delete(0, "end")
            self.entry_wd.insert(0, path)

    def save_config(self):
        if not self.selected:
            return
        try:
            save_profile_file(self.engine, self.selected, "config", self.txt_config.get("1.0", "end-1c"))
            self.refresh(select=self.selected)
            self.set_status(f"Saved {self.engine.primary_label}", "ok")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def reload_config(self):
        if not self.selected:
            return
        self.txt_config.delete("1.0", "end")
        self.txt_config.insert("1.0", read_profile_file(self.engine, self.selected, "config"))
        self.set_status(f"Reloaded {self.engine.primary_label}")

    def save_auth(self):
        if not self.selected:
            return
        if self._mask_auth.get():
            messagebox.showwarning(self.engine.secondary_label, 'Uncheck "Mask secrets" before editing/saving.', parent=self)
            return
        try:
            content = self.txt_auth.get("1.0", "end-1c")
            save_profile_file(self.engine, self.selected, "auth", content)
            self.auth_raw = content
            self.refresh(select=self.selected)
            self.set_status(f"Saved {self.engine.secondary_label}", "ok")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def reload_auth(self):
        if not self.selected:
            return
        self.auth_raw = read_profile_file(self.engine, self.selected, "auth")
        self._refresh_auth_view()
        self.set_status(f"Reloaded {self.engine.secondary_label}")

    def open_root(self):
        try:
            open_in_explorer(str(ensure_root(self.engine)))
            self.set_status(f"Opened {get_profiles_root(self.engine)}")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def show_doctor(self):
        try:
            report = doctor_report(self.engine, self.selected) + "\n\n" + session_share_status(self.engine, self.selected)
            dlg = ctk.CTkToplevel(self)
            dlg.title(f"{self.engine.label} doctor")
            dlg.geometry("580x500")
            dlg.configure(fg_color=PANEL)
            dlg.transient(self)
            dlg.grab_set()
            box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Consolas", size=13), fg_color="#0E121A")
            box.pack(fill="both", expand=True, padx=14, pady=14)
            box.insert("1.0", report)
            box.configure(state="disabled")
            ctk.CTkButton(dlg, text="Close", width=100, command=dlg.destroy).pack(pady=(0, 14))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def refresh_session_status(self):
        if not hasattr(self, "lbl_session_status"):
            return
        if not self.selected:
            self.lbl_session_status.configure(text="Status: (no profile)")
            self.lbl_session_detail.configure(text="")
            return
        prof = next((p for p in self.profiles if p.name == self.selected), None)
        shared_home = get_shared_session_home(self.engine)
        if prof and prof.sessions_shared:
            self.lbl_session_status.configure(text="Status: SHARED", text_color=INFO)
            self.lbl_session_detail.configure(
                text=f"Points to:\n{shared_home}\n\nSame Working directory, then:\n  {self.engine.resume_cmd}\n  {self.engine.resume_all_cmd}"
            )
        else:
            self.lbl_session_status.configure(text="Status: ISOLATED", text_color=WARN)
            self.lbl_session_detail.configure(
                text=f"Enable sharing so other providers can resume this project.\n{self.engine.primary_label} / {self.engine.secondary_label} stay private."
            )

    def share_selected_sessions(self):
        if not self.selected:
            return
        if not messagebox.askyesno(
            "Share sessions",
            f"Link profile '{self.selected}' session storage to:\n{get_shared_session_home(self.engine)}\n\n"
            f"• {self.engine.primary_label} / {self.engine.secondary_label} stay isolated\n"
            "• sessions + resume index become shared\n"
            f"• Close running {self.engine.label} windows first (DB may be locked)\n\nContinue?",
            parent=self,
        ):
            return
        try:
            report = enable_shared_sessions(self.engine, self.selected)
            self.refresh(select=self.selected)
            ok = report.get("ok")
            self.set_status(f"Shared sessions for '{self.selected}'" if ok else f"Partial share: {report}", "ok" if ok else "warn")
            if not ok:
                messagebox.showwarning("Share sessions", f"Finished with issues:\n{report}", parent=self)
            else:
                messagebox.showinfo("Share sessions", f"Done.\n\n{session_share_status(self.engine, self.selected)}", parent=self)
        except Exception as e:
            messagebox.showerror("Share sessions", str(e), parent=self)

    def share_all_sessions(self):
        if not messagebox.askyesno(
            "Share ALL sessions",
            f"Link ALL {self.engine.label} profiles' session storage to:\n{get_shared_session_home(self.engine)}\n\nProvider configs/keys stay isolated.\nClose running {self.engine.label} windows first.\n\nContinue?",
            parent=self,
        ):
            return
        try:
            results = enable_shared_sessions_all(self.engine)
            self.refresh(select=self.selected)
            failed = [r for r in results if not r.get("ok")]
            summary = session_share_status(self.engine)
            if failed:
                messagebox.showwarning("Share ALL", f"Some profiles failed:\n{failed}\n\n{summary}", parent=self)
                self.set_status("Shared sessions with some errors", "warn")
            else:
                messagebox.showinfo("Share ALL", f"All profiles linked.\n\n{summary}", parent=self)
                self.set_status("All profiles share sessions", "ok")
        except Exception as e:
            messagebox.showerror("Share ALL", str(e), parent=self)


def main():
    # HiDPI friendliness on Windows
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = App()
    app.mainloop()


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    main()
