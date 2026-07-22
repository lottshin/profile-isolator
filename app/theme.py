"""Visual theme for AI CLI Profile Isolator.

Direction: Linear / Raycast tool UI — restrained zinc palette, one accent,
quiet secondary actions, hairline borders, soft hierarchy.
"""

from __future__ import annotations

# Surface
BG = "#0A0A0B"           # app background (near black)
SURFACE = "#111113"      # panels
SURFACE_2 = "#18181B"    # elevated / inputs
SURFACE_3 = "#1F1F23"    # hover / selected card fill
BORDER = "#27272A"       # hairline
BORDER_SOFT = "#3F3F46"  # slightly stronger hairline

# Text
TEXT = "#FAFAFA"
TEXT_SECONDARY = "#A1A1AA"
TEXT_MUTED = "#71717A"
TEXT_FAINT = "#52525B"

# Accent (single brand color — indigo, not toy blue)
ACCENT = "#6366F1"
ACCENT_HOVER = "#4F46E5"
ACCENT_SOFT = "#1E1B4B"   # selected/accent wash
ACCENT_RING = "#818CF8"

# Semantic (muted, not neon)
GOOD = "#34D399"
GOOD_BG = "#052E1C"
WARN = "#FBBF24"
WARN_BG = "#2A1F05"
DANGER = "#F87171"
DANGER_BG = "#2A1215"
INFO = "#93C5FD"
INFO_BG = "#0C1A2E"

# Geometry
RADIUS_LG = 14
RADIUS_MD = 10
RADIUS_SM = 8
RADIUS_XS = 6

# Spacing helpers (for docs / consistency)
PAD = 16
GAP = 10
