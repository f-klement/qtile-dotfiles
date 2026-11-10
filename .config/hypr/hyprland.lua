-- Hyprland Lua config -- entry point
-- See https://wiki.hypr.land/Configuring/Start/
--
-- Adapted from https://github.com/f-klement/hyprland-arch-dotfiles (the
-- "arch" reference repo), ported to match what the qtile setup on this
-- host (config.py, same .dotfiles) actually does: same apps, same VM
-- multihead window routing, same monitor layout, same notification/alert
-- placement, same daemon choices already made for this host (hypridle,
-- hyprlock, hyprpaper; polkit-kde-authentication-agent-1 kept; swaync
-- instead of dunst). Arch-only and previous-host-specific pieces (TUXEDO
-- tooling, gaming apps, hyprpanes, hyprsunset, kbuildsycoca6) were dropped.

require("env")
require("monitors")
require("autostart")
require("settings")
require("keybinds")
require("windowrules")
