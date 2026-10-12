-- Autostart
-- See https://wiki.hypr.land/Configuring/Basics/Autostart/
--
-- Adapted from the reference repo's autostart.lua: dropped everything
-- specific to that host (TUXEDO tray tooling, radiotray-ng, hyprsunset,
-- hyprpanes, kbuildsycoca6 with an Arch menu prefix) since none of it
-- applies here or to qtile's current feature set. Kept/ported: the daemon
-- choices already decided for this session (hypridle/hyprlock/hyprpaper
-- native; polkit-kde-authentication-agent-1 reused as-is; swaync instead of
-- dunst), plus qtile's own wallpaper script and cursor theme.

local home = os.getenv("HOME")

hl.on("hyprland.start", function()
    -- Session plumbing
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")

    -- Polkit agent: kept as the KDE one (already installed, already working,
    -- fixed to dock to the top of the screen under qtile this same session)
    -- rather than switching to hyprpolkitagent.
    for _, path in ipairs({
        "/usr/libexec/kf6/polkit-kde-authentication-agent-1",
        "/usr/libexec/polkit-kde-authentication-agent-1",
    }) do
        local f = io.open(path)
        if f then
            f:close()
            hl.exec_cmd(path)
            break
        end
    end

    -- Bar and notifications
    hl.exec_cmd("waybar -c " .. home .. "/.config/waybar/config -s " .. home .. "/.config/waybar/style.css")
    hl.exec_cmd("swaync")

    -- Clipboard history (cliphist, paired with rofi)
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")

    -- Wallpaper daemon, then hand off to the shared wallpaper.sh (qtile uses
    -- the same script) to actually pick and load an image via hyprpaper's
    -- IPC -- small delay so the IPC socket exists before the script calls it.
    hl.exec_cmd("hyprpaper")
    hl.exec_cmd("sh -c 'sleep 1; " .. home .. "/bin/wallpaper.sh restore || " .. home .. "/bin/wallpaper.sh'")

    -- Cursor theme: matches qtile's own light/dark-aware choice
    -- (config.py's wl_xcursor_theme), not the reference repo's unrelated
    -- Dracula-cursors preference.
    hl.exec_cmd("sh -c '" ..
        "mode=$(cat " .. home .. "/.local/state/theme-mode 2>/dev/null); " ..
        "theme=BreezeX-RosePine-Linux; " ..
        "[ \"$mode\" = light ] && theme=BreezeX-RosePineDawn-Linux; " ..
        "hyprctl setcursor \"$theme\" 24; " ..
        "gsettings set org.gnome.desktop.interface cursor-theme \"$theme\"; " ..
        "gsettings set org.gnome.desktop.interface cursor-size 24'")

    -- Idle/lock handling (hypridle.conf: lock at 15min, screen off at 20min,
    -- suspend at 30min -- same staggering as qtile's hypridle/hyprlock pair
    -- would use if it had one; qtile itself currently uses swayidle instead).
    hl.exec_cmd("hypridle")

    -- Pin workspaces 7/8/9 to the built-in/landscape/portrait screens, same
    -- three slots qtile's GROUP_ROLE uses (see windowrules.lua's debian-work
    -- VM routing). Via hyprctl dispatch rather than an unverified Lua
    -- workspace-config function -- moveworkspacetomonitor is a stable,
    -- well-documented dispatcher. Small delay so all 3 monitors are already
    -- attached before binding workspaces to them.
    hl.exec_cmd("sh -c '" ..
        "sleep 1; " ..
        "hyprctl dispatch moveworkspacetomonitor 7 eDP-1; " ..
        "hyprctl dispatch moveworkspacetomonitor 8 \"desc:Samsung Electric Company LF24T450G HNMX502924\"; " ..
        "hyprctl dispatch moveworkspacetomonitor 9 \"desc:Samsung Electric Company LF24T450G HNMX502934\"'")
end)
