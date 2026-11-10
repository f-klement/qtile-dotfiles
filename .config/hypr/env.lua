-- Environment variables
-- See https://wiki.hypr.land/Configuring/Advanced-and-Cool/Environment-variables/

hl.env("CLUTTER_BACKEND", "wayland")
hl.env("GDK_BACKEND", "wayland,x11")
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
hl.env("QT_SCALE_FACTOR", "1")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")

-- Cursor size for both hyprcursor and XWayland/toolkit apps. Theme matches
-- qtile's own choice (config.py's wl_xcursor_theme), light/dark picked in
-- autostart.lua at session start the same way qtile's config.py does.
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")

hl.env("MOZ_ENABLE_WAYLAND", "1")

-- This host is Intel iGPU (Meteor Lake-P, i915) -- no NVIDIA workarounds
-- needed. Explicitly forced to "0" (not just omitted) in case anything
-- system-wide sets it to 1 via pam_env; this overrides that for Hyprland
-- and everything it launches.
hl.env("WLR_NO_HARDWARE_CURSORS", "0")
