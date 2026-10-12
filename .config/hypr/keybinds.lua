-- Keybinds
-- See https://wiki.hypr.land/Configuring/Basics/Binds/
--
-- Adapted from the reference repo: app launchers and commands point at
-- what qtile's config.py actually uses on this host (kitty, brave-browser,
-- codium, dolphin, the Obsidian flatpak, ~/bin/screenshot.sh, wpctl/
-- brightnessctl), not the repo's Volume.sh/MediaCtrl.sh/WallpaperSelect.sh
-- scripts (none of which exist here). wlogout (installed) covers the power
-- menu instead of reimplementing qtile's yad-based one.

local home    = os.getenv("HOME")
local mainMod = "SUPER"

local browser = "brave-browser"
local term    = "kitty"
local editor  = "codium"
local files   = "dolphin"
local notes   = "flatpak run md.obsidian.Obsidian"
local screenshot = home .. "/bin/screenshot.sh"

local function combo(mods, k)
    if mods == "" then return k end
    return mods .. " + " .. k
end

------------------------------------
---- APPS / SYSTEM ----
------------------------------------

hl.bind(combo(mainMod, "SHIFT + C"),   hl.dsp.exec_cmd("hyprctl reload"))
hl.bind(combo(mainMod, "E"),           hl.dsp.exec_cmd(editor))
hl.bind(combo(mainMod, "Q"),           hl.dsp.exec_cmd(term))
hl.bind(combo(mainMod, "D"),           hl.dsp.exec_cmd(files))
hl.bind(combo(mainMod, "B"),           hl.dsp.exec_cmd(browser))
hl.bind(combo(mainMod, "O"),           hl.dsp.exec_cmd(notes))
hl.bind(combo(mainMod, "ALT + Space"), hl.dsp.exec_cmd("pkill rofi || rofi -show drun"))
hl.bind(combo(mainMod, "L"),           hl.dsp.exec_cmd("loginctl lock-session"))
hl.bind("CTRL + ALT + Delete",         hl.dsp.exec_cmd("wlogout"))

------------------------------------
---- WINDOW ACTIONS ----
------------------------------------

hl.bind(combo(mainMod, "Space"),       hl.dsp.window.float({ action = "toggle" }))
hl.bind(combo(mainMod, "F"),           hl.dsp.window.fullscreen())
hl.bind(combo(mainMod, "ALT + X"),     hl.dsp.window.kill())
hl.bind(combo(mainMod, "SHIFT + Q"),   hl.dsp.window.close())
hl.bind(combo(mainMod, "P"),           hl.dsp.window.pseudo())
hl.bind(combo(mainMod, "G"),           hl.dsp.group.toggle())
hl.bind("ALT + Tab",                   hl.dsp.group.next())

------------------------------------
---- FOCUS / MOVE ----
------------------------------------

hl.bind(combo(mainMod, "Left"),  hl.dsp.window.move_focus({ direction = "l" }))
hl.bind(combo(mainMod, "Right"), hl.dsp.window.move_focus({ direction = "r" }))
hl.bind(combo(mainMod, "Up"),    hl.dsp.window.move_focus({ direction = "u" }))
hl.bind(combo(mainMod, "Down"),  hl.dsp.window.move_focus({ direction = "d" }))

hl.bind(combo(mainMod, "SHIFT + Left"),  hl.dsp.window.move({ direction = "l" }))
hl.bind(combo(mainMod, "SHIFT + Right"), hl.dsp.window.move({ direction = "r" }))
hl.bind(combo(mainMod, "SHIFT + Up"),    hl.dsp.window.move({ direction = "u" }))
hl.bind(combo(mainMod, "SHIFT + Down"),  hl.dsp.window.move({ direction = "d" }))

-- Next/prev monitor in physical order (qtile's Mod+Tab / Mod+Shift+Tab)
hl.bind(combo(mainMod, "Tab"),         hl.dsp.exec_cmd("hyprctl dispatch focusmonitor +1"))
hl.bind(combo(mainMod, "SHIFT + Tab"), hl.dsp.exec_cmd("hyprctl dispatch focusmonitor -1"))

------------------------------------
---- WORKSPACES ----
------------------------------------

for i = 1, 9 do
    hl.bind(combo(mainMod, tostring(i)), hl.dsp.workspace({ id = tostring(i) }))
    hl.bind(combo(mainMod, "SHIFT + " .. i), hl.dsp.window.move_to_workspace({ id = tostring(i) }))
end

------------------------------------
---- SCREENSHOTS (qtile's screenshot.sh, shared) ----
------------------------------------

hl.bind("Print",                       hl.dsp.exec_cmd(screenshot .. " gui"))   -- select region
hl.bind(combo(mainMod, "ALT + S"),     hl.dsp.exec_cmd(screenshot .. " gui"))   -- for keyboards without Print
hl.bind(combo("SHIFT", "Print"),       hl.dsp.exec_cmd(screenshot .. " clip"))  -- full screen to clipboard
hl.bind(combo("CTRL", "Print"),        hl.dsp.exec_cmd(screenshot .. " full"))  -- full screen to ~/Pictures

------------------------------------
---- MEDIA / VOLUME / BRIGHTNESS (qtile's own commands) ----
------------------------------------

hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("pactl set-sink-volume @DEFAULT_SINK@ +5%"))
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("pactl set-sink-volume @DEFAULT_SINK@ -5%"))
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("pactl set-sink-mute @DEFAULT_SINK@ toggle"))
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("pactl set-source-mute @DEFAULT_SOURCE@ toggle"))
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("brightnessctl set 5%+"))
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl set 5%-"))
