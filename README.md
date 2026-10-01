# qtile-dotfiles

A minimal qtile dotfiles setup with two targets:

| bootstrap | target | backend |
|---|---|---|
| `el_x11_bootstrap.sh` | Rocky / RHEL 8 VM behind xrdp | X11 (inside gnome-session) |
| `fedora_wayland_bootstrap.sh` | Fedora 44+ workstation (here: Latitude 5550, Plasma edition) | Wayland (own SDDM session next to Plasma) |

The EL bootstrap detects the platform rather than assuming EL8: it maps
powertools/crb, probes the kernel for the best zswap zpool + compressor,
tests for native (non-fuse) rootless overlay, and prefers distro packages
over from-source builds where they exist. The Fedora bootstrap needs none of
that: qtile, its wlroots backend and every Wayland tool are packaged.

Containers are rootless podman driven by the docker CLI via DOCKER_HOST;
there is no docker daemon on EL (an existing one on Fedora is left alone).

## One config, two backends

- **Shared, branching on the backend**: `.config/qtile/config.py`
  (`qtile.core.name`; screens come from `generate_screens`, so no xrandr),
  `bin/theme.sh`, `bin/wallpaper.sh` (feh / swaybg), `bin/screenshot.sh`
  (flameshot / grim+slurp+swappy).
- **Per backend**, because the tooling does not overlap:
  - X11: `bin/starting-qtile.sh`, `.config/qtile/autostart_x11.sh`, `lock_with_random_bg_x11.sh`
  - Wayland: `bin/starting-qtile-wayland.sh`, `.config/qtile/autostart_wayland.sh`,
    `lock_with_random_bg_wayland.sh`, `.config/kanshi/config` (monitor layout),
    `.config/xdg-desktop-portal/qtile-portals.conf`

## Deploy

Deploy configs with GNU stow. The setup file will ask for the root password.

```bash
# EL / X11
chmod +x el_x11_bootstrap.sh
sudo ./el_x11_bootstrap.sh
stow .

# Fedora / Wayland
sudo ./fedora_wayland_bootstrap.sh
stow --ignore='^\.bashrc$' .   # keep the machine's own ~/.bashrc
# log out, choose "Qtile (Wayland, dotfiles)" in SDDM
```
