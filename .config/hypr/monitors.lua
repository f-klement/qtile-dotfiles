-- Monitor configuration
-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
--
-- Real layout confirmed via `wlr-randr` under the qtile session on this
-- host (same physical setup: built-in panel + Thunderbolt dock with two
-- identical Samsung LF24T450G panels, told apart by serial -- the external
-- monitors are literally the same hardware the reference repo describes,
-- just a different laptop's built-in panel). Matches qtile's config.py
-- SCREEN["small"/"landscape"/"portrait"] roles and positions exactly, so
-- switching sessions doesn't relearn the spatial layout.

hl.monitor({ output = "eDP-1", mode = "1920x1080@59.999", position = "0x840", scale = 1 })

-- Landscape external (HNMX502924)
hl.monitor({ output = "desc:Samsung Electric Company LF24T450G HNMX502924", mode = "1920x1200@74.94", position = "3120x382", scale = 1 })

-- Portrait external (HNMX502934), rotated 90 degrees
hl.monitor({ output = "desc:Samsung Electric Company LF24T450G HNMX502934", mode = "1920x1200@74.94", position = "1920x0", scale = 1, transform = 1 })

-- Fallback for any other/unlisted monitor.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })
