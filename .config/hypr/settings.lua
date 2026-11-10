-- Look & feel, layout engine, misc/binds/xwayland behaviour
-- See https://wiki.hypr.land/Configuring/Basics/Variables/
--
-- Adapted from the reference repo: border colours read qtile's own theme
-- state file and Rose Pine palette (colors.py) directly -- hardcoded here
-- rather than via an external themes/<mode>/theme.sh indirection, since
-- qtile itself doesn't have one either (config.py defines doom_colors
-- inline the same way). kb_layout matches this host's real layout
-- (`localectl`: de,us), not the reference repo's single "de".

local function theme_borders()
    -- Rose Pine (dark) iris / base, Rose Pine Dawn (light) iris / base --
    -- same colors.py values qtile's layout_theme uses for
    -- border_focus/border_normal (doom_colors[7]/doom_colors[0]).
    local dark_active,  dark_inactive  = "rgba(c4a7e7ff)", "rgba(191724ff)"
    local light_active, light_inactive = "rgba(907aa9ff)", "rgba(faf4edff)"
    local mode = "dark"
    local f = io.open(os.getenv("HOME") .. "/.local/state/theme-mode")
    if f then
        local m = f:read("*l")
        f:close()
        if m then mode = m end
    end
    if mode == "light" then
        return light_active, light_inactive
    end
    return dark_active, dark_inactive
end
local border_active, border_inactive = theme_borders()

hl.config({
    general = {
        gaps_in = 1,
        gaps_out = 2,
        border_size = 1,
        resize_on_border = true,

        col = {
            active_border = border_active,
            inactive_border = border_inactive,
        },

        layout = "dwindle",
    },

    decoration = {
        rounding       = 6,
        rounding_power = 2,

        active_opacity   = 1,
        inactive_opacity = 0.85,   -- matches qtile's _OPACITY_UNFOCUSED
        fullscreen_opacity = 1.0,

        dim_inactive = true,
        dim_strength = 0.1,

        blur = {
            enabled           = true,
            size              = 8,
            passes            = 1,
            xray              = true,
            new_optimizations = true,
        },
    },

    dwindle = {
        preserve_split       = true,
        special_scale_factor = 0.8,
    },

    input = {
        kb_layout  = "de,us",
        kb_options = "grp:alt_shift_toggle",

        repeat_rate  = 50,
        repeat_delay = 300,

        numlock_by_default          = true,
        left_handed                 = false,
        follow_mouse                = 1,
        float_switch_override_focus = false,
        sensitivity                 = 0.6,

        touchpad = {
            -- matches qtile's wl_input_rules: InputConfig(tap=True, dwt=True, natural_scroll=False)
            disable_while_typing   = true,
            natural_scroll         = false,
            clickfinger_behavior   = false,
            middle_button_emulation = true,
            tap_to_click            = true,
            drag_lock                = false,
        },
    },

    cursor = {
        enable_hyprcursor = true,
        no_warps          = false,
        hide_on_touch      = true,
    },

    gestures = {
        workspace_swipe_distance             = 400,
        workspace_swipe_invert               = true,
        workspace_swipe_min_speed_to_force   = 30,
        workspace_swipe_cancel_ratio         = 0.5,
        workspace_swipe_create_new           = true,
        workspace_swipe_forever              = true,
    },

    misc = {
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
        mouse_move_enables_dpms  = true,
        vrr                      = true,
        enable_swallow           = true,
        focus_on_activate        = false,
        swallow_regex            = "^(kitty)$",
    },

    debug = {
        vfr           = true,
        disable_logs  = false,
    },

    binds = {
        workspace_back_and_forth = true,
        allow_workspace_cycles   = true,
        pass_mouse_when_bound    = false,
    },

    xwayland = {
        force_zero_scaling = true,
    },
})

hl.gesture({
    fingers   = 3,
    direction = "horizontal",
    action    = "workspace",
})

------------------------
---- ANIMATIONS ----
------------------------

hl.curve("myBezier",  { type = "bezier", points = { {0.05, 0.9},  {0.1, 1.05}  } })
hl.curve("linear",    { type = "bezier", points = { {0, 0},       {1, 1}       } })
hl.curve("wind",      { type = "bezier", points = { {0.05, 0.9},  {0.1, 1.05}  } })
hl.curve("winIn",     { type = "bezier", points = { {0.1, 1.1},   {0.1, 1.1}   } })
hl.curve("winOut",    { type = "bezier", points = { {0.3, -0.3},  {0, 1}       } })
hl.curve("slow",      { type = "bezier", points = { {0, 0.85},    {0.3, 1}     } })
hl.curve("overshot",  { type = "bezier", points = { {0.7, 0.6},   {0.1, 1.1}   } })
hl.curve("bounce",    { type = "bezier", points = { {1.1, 1.6},   {0.1, 0.85}  } })

hl.config({ animations = { enabled = true } })

hl.animation({ leaf = "windowsIn",   enabled = true, speed = 5,   bezier = "slow",    style = "popin" })
hl.animation({ leaf = "windowsOut",  enabled = true, speed = 5,   bezier = "winOut",  style = "popin" })
hl.animation({ leaf = "windowsMove", enabled = true, speed = 5,   bezier = "wind",    style = "slide" })
hl.animation({ leaf = "border",      enabled = true, speed = 10,  bezier = "linear" })
hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "linear",  style = "loop" })
hl.animation({ leaf = "fade",        enabled = true, speed = 5,   bezier = "overshot" })
hl.animation({ leaf = "workspaces",  enabled = true, speed = 5,   bezier = "wind" })
hl.animation({ leaf = "windows",     enabled = true, speed = 5,   bezier = "bounce",  style = "popin" })
