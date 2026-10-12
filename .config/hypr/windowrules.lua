-- Window rules
-- See https://wiki.hypr.land/Configuring/Basics/Window-Rules/
--
-- Adapted from the reference repo: dropped every rule for an app that
-- isn't part of this setup (steam/lutris/wine/discord/obs/audacious/
-- bootdevticker/laptop-mode-tool/etc.). Kept the float rules for apps that
-- genuinely are in use, and ADDED what qtile's config.py does that the
-- reference repo never needed:
--   - debian-work VM multihead routing (qtile's VIRT_VIEWER_HEAD1/2/3):
--     virt-viewer's 2 (heads=2) windows, told apart by title, one per
--     pinned workspace/screen.
--   - alert/notification-style windows docked near the top of the screen
--     (qtile's ALERT_WINDOWS -> _dock_to_top), approximated here with a
--     fixed top-center-ish `move` percentage -- Hyprland's windowrule
--     language has no dynamic "center by actual window width" primitive
--     the way qtile's Python hook computed one live; this is a static
--     stand-in for the same intent.

local function float_rule(name, class_pat)
    hl.window_rule({ name = name, match = { class = class_pat }, float = true })
end

-- Generic floating dialogs (qtile's floating_layout.float_rules)
float_rule("float-polkit-kde",  "org.kde.polkit-kde-authentication-agent-1")
float_rule("float-nm-editor",   "nm-connection-editor")
float_rule("float-blueman",     "blueman-manager")
float_rule("float-pavucontrol", "pavucontrol")
float_rule("float-rofi",        "rofi")
float_rule("float-yad",         "[Yy]ad")
float_rule("float-dialog",      "dialog")
float_rule("float-error",       "error")
float_rule("float-notification","notification")
float_rule("float-pinentry",    "pinentry(-gtk-2)?")
float_rule("float-ssh-askpass", "ssh-askpass")

------------------------------------
---- WORKSPACE ASSIGNMENT (qtile's GROUP_MATCHES) ----
------------------------------------

hl.window_rule({ name = "ws-brave",    match = { class = "brave-browser" },           workspace = "1" })
hl.window_rule({ name = "ws-codium",   match = { class = "codium" },                  workspace = "2" })
hl.window_rule({ name = "ws-dolphin",  match = { class = "org.kde.dolphin" },         workspace = "5" })
hl.window_rule({ name = "ws-obsidian", match = { class = "obsidian" },                workspace = "6" })

------------------------------------
---- debian-work VM multihead (qtile's VIRT_VIEWER_HEAD1/2/3) ----
------------------------------------
-- heads=2 on the VM opens one virt-viewer window per guest display, titled
-- "debian-work (1)"/"debian-work (2)" (or bare "debian-work" at a single
-- head). Workspace 7 is pinned to the built-in screen, 8 to landscape, 9 to
-- portrait (see the moveworkspacetomonitor calls in autostart.lua) -- same
-- three slots qtile uses, so switching sessions doesn't relearn this either.

hl.window_rule({
    name = "vm-head1",
    match = { class = "virt-viewer", title = "^debian-work(\\s\\(1\\))?$" },
    workspace = "7",
})
hl.window_rule({
    name = "vm-head2",
    match = { class = "virt-viewer", title = "^debian-work\\s\\(2\\)$" },
    workspace = "8",
})
hl.window_rule({
    name = "vm-head3",
    match = { class = "virt-viewer", title = "^debian-work\\s\\(3\\)$" },
    workspace = "9",  -- unused at heads=2, future-proofing (matches qtile)
})
-- virt-viewer's own small popups (e.g. when an output/display closes) share
-- its class but carry no title -- float + dock near top like other alerts
-- instead of silently landing in whatever workspace is active.
hl.window_rule({
    name  = "vm-popup-float",
    match = { class = "virt-viewer", title = "^$" },
    float = true,
})

------------------------------------
---- ALERT / NOTIFICATION WINDOWS: dock near the top ----
------------------------------------

local function alert_rule(name, match)
    hl.window_rule({ name = name .. "-float", match = match, float = true })
    hl.window_rule({ name = name .. "-move",  match = match, move = "35% 3%" })
end

alert_rule("alert-polkit", { class = "org.kde.polkit-kde-authentication-agent-1" })
alert_rule("alert-vm-popup", { class = "virt-viewer", title = "^$" })
alert_rule("alert-dialog", { class = "dialog" })
alert_rule("alert-error", { class = "error" })
alert_rule("alert-notification", { class = "notification" })

------------------------------------
---- OPACITY ----
------------------------------------
-- virt-viewer stays fully opaque (debian-work's SPICE GL surface) -- same
-- reasoning as qtile's _apply_opacity exclusion: any opacity < 1.0 forces
-- the compositor to alpha-composite every frame instead of scanning it out
-- directly, a plausible source of tearing/artifacts on a continuously
-- updating GL surface.
hl.window_rule({ name = "opacity-virt-viewer", match = { class = "virt-viewer" }, opacity = "1.0 1.0" })

local function opacity_rule(name, class_pat, focused, unfocused)
    hl.window_rule({ name = name, match = { class = class_pat }, opacity = focused .. " " .. unfocused })
end

opacity_rule("opacity-rofi",     "rofi",          "0.9", "0.6")
opacity_rule("opacity-brave",    "brave-browser", "0.9", "0.85")
opacity_rule("opacity-dolphin",  "org.kde.dolphin","0.9", "0.85")
opacity_rule("opacity-kitty",    "kitty",         "0.9", "0.85")
opacity_rule("opacity-vscodium", "codium",        "0.9", "0.85")

------------------------------------
---- LAYER RULES ----
------------------------------------

hl.layer_rule({
    name  = "rofi-blur",
    match = { namespace = "rofi" },
    blur  = true,
})

------------------------------------
---- MISC (from the shipped example config) ----
------------------------------------

hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})
