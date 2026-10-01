#!/usr/bin/env bash
#
# One-shot bootstrap for a Fedora (44+) workstation: qtile on Wayland as an extra
# display-manager session next to whatever the edition ships (Plasma here), same
# dotfiles/theming as el_x11_bootstrap.sh. Fedora packages qtile, its wlroots
# backend and every Wayland tool used, so unlike EL8 there are no venvs and no
# source builds. Containers: rootless podman; an existing docker/moby is left alone.
# Idempotent: safe to re-run.
#
# Backend split (see README): config.py, theme.sh, wallpaper.sh and screenshot.sh
# are shared and branch on the backend; the session entry
# (bin/starting-qtile-wayland.sh) and .config/qtile/autostart_wayland.sh are
# Wayland-only.

set -euo pipefail

### 0. Sanity check
if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo or as root." >&2
  exit 1
fi

### 0. Variables & helpers
TARGET_USER="${SUDO_USER:-$(logname)}"
TARGET_UID="$(id -u "$TARGET_USER")"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
export PATH="/usr/local/bin:$PATH"

. /etc/os-release
echo "platform: ${ID:-unknown} ${VERSION_ID:-?} ${VARIANT:-} (kernel $(uname -r))"
if [[ ${ID:-} != fedora ]]; then
  echo "This is the Fedora bootstrap; for Rocky/RHEL use el_x11_bootstrap.sh." >&2
  exit 1
fi

# Run as the target user, inside their systemd --user / D-Bus session (sudo
# drops both, and gsettings/systemctl --user silently go nowhere without them).
# NOT sudo -i: it re-joins the arguments into one escaped string for the login
# shell, turning every newline of a multi-line `bash -c '...'` into a line
# continuation. sudo -u -H execs the arguments verbatim.
as_user() {
  ( cd "$TARGET_HOME" && sudo -u "$TARGET_USER" -H env XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" "$@" )
}

# is the flatpak app installed (system or user)?
have_flatpak() { flatpak info "$1" >/dev/null 2>&1 || as_user flatpak info "$1" >/dev/null 2>&1; }

# Ensure dnf is always non-interactive
if ! grep -q '^defaultyes=True' /etc/dnf/dnf.conf; then
  sed -i '/^\[main\]/a defaultyes=True' /etc/dnf/dnf.conf
fi

### 1. Repos & core packages
dnf -y install dnf-plugins-core flatpak git stow unzip jq curl

# RPM Fusion: codecs + Intel VA-API (intel-media-driver lives in nonfree).
rpm -q rpmfusion-free-release >/dev/null 2>&1 || dnf -y install \
  "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
  "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
rpm -q ffmpeg >/dev/null 2>&1 || dnf -y swap ffmpeg-free ffmpeg --allowerasing
dnf -y update @multimedia --setopt=install_weak_deps=False --exclude=PackageKit-gstreamer-plugin || true
if lspci -n | grep -q ' 0300: 8086:'; then
  dnf -y install intel-media-driver   # Meteor Lake & newer: iHD
fi

flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

dnf -y update

# snapd: system_update.sh refreshes snaps; classic snaps (codium) need /snap.
dnf -y install snapd
[[ -e /snap ]] || ln -s /var/lib/snapd/snap /snap

# VSCodium from the project's RPM repo (not in Fedora), unless some codium
# (RPM or snap) is already there.
if ! command -v codium >/dev/null && [[ ! -x /var/lib/snapd/snap/bin/codium ]]; then
  rpmkeys --import https://gitlab.com/paulcarroty/vscodium-deb-rpm-repo/raw/master/pub.gpg
  cat > /etc/yum.repos.d/vscodium.repo <<'VSCODIUM_REPO'
[gitlab.com_paulcarroty_vscodium_repo]
name=download.vscodium.com
baseurl=https://download.vscodium.com/rpms/
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://gitlab.com/paulcarroty/vscodium-deb-rpm-repo/raw/master/pub.gpg
metadata_expire=1h
VSCODIUM_REPO
  dnf -y install codium
fi

# Brave from its own RPM repo (the flatpak lags upstream), unless a Brave -
# RPM or flatpak - is already installed. config.py/autostart use either.
if ! rpm -q brave-browser >/dev/null 2>&1 && ! have_flatpak com.brave.Browser; then
  [[ -f /etc/yum.repos.d/brave-browser.repo ]] || \
    dnf -y config-manager addrepo --from-repofile=https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo
  rpmkeys --import https://brave-browser-rpm-release.s3.brave.com/brave-core.asc || true
  dnf -y install brave-browser
fi

### 2. QTile Wayland (distro packages: qtile 0.37 + compiled wlroots 0.20 backend)
dnf -y install \
  qtile qtile-wayland qtile-extras \
  python3-psutil python3-dbus-fast python3-pulsectl-asyncio \
  xorg-x11-server-Xwayland \
  polkit-kde papirus-icon-theme fontawesome-fonts-all \
  abattis-cantarell-fonts abattis-cantarell-vf-fonts

# Our own session entry; the RPM's qtile.desktop expects a qtile.service that
# Fedora does not ship. bin/starting-qtile-wayland.sh comes from `stow .`.
cat > /usr/share/wayland-sessions/qtile-dotfiles.desktop <<EOF
[Desktop Entry]
Name=Qtile (Wayland, dotfiles)
Comment=Qtile tiling Wayland compositor with the ~/.dotfiles session setup
Exec=$TARGET_HOME/bin/starting-qtile-wayland.sh
Type=Application
DesktopNames=qtile;wlroots
Keywords=wm;tiling;wayland
EOF

### 3. Wayland session utilities (everything autostart_wayland.sh / config.py call)
dnf -y install \
  kitty rofi dunst libnotify \
  kanshi wlr-randr wlopm swaybg swaylock swayidle \
  grim slurp swappy wl-clipboard \
  xdg-desktop-portal xdg-desktop-portal-wlr xdg-desktop-portal-gtk \
  network-manager-applet copyq brightnessctl playerctl blueman \
  pavucontrol pulseaudio-utils btop yad ranger vlc qt5ct

### 4. Flatpak GUI apps (system-wide, alongside the ones already there)
flatpak install -y --noninteractive flathub \
  io.gitlab.librewolf-community \
  com.github.tchx84.Flatseal \
  md.obsidian.Obsidian \
  it.mijorus.gearlever \
  com.usebruno.Bruno

### 4.1 Citrix Workspace: WebKitGTK 4.0 for selfservice (the menu launcher)
# Fedora dropped the WebKitGTK 4.0 ABI, so selfservice dies with
# "libwebkit2gtk-4.0.so.37: cannot open shared object file". Citrix ships an
# Ubuntu build of it (+ ICU 70) for this, and util/integrate.sh extracts it to
# /usr/lib/x86_64-linux-gnu - on Fedora that alone is not enough:
#   - the dir is not in the linker path;
#   - the Ubuntu build needs libjpeg.so.8 (libjpeg 8 ABI). Fedora's libjpeg-turbo
#     is the 6.2 ABI, a symlink would crash, so build libjpeg-turbo from
#     Fedora's own source package with WITH_JPEG8=1.
# Every soname in that dir (webkit2gtk-4.0, javascriptcoregtk-4.0, icu 70,
# jpeg 8) is one Fedora does not ship, so nothing system-wide is shadowed.
install_citrix_webkit40() {
  # CTX_LIB only redirects a test run into a scratch root (skips ldconfig).
  local ica=/opt/Citrix/ICAClient ctx_lib=${CTX_LIB:-/usr/lib/x86_64-linux-gnu}   # WebKit hardcodes its helper paths here
  [[ -f $ica/Webkit2gtk4.0/webkit2gtk-4.0.tar.gz ]] || return 0
  if [[ ! -e $ctx_lib/libwebkit2gtk-4.0.so.37 ]]; then
    tar xzf "$ica/Webkit2gtk4.0/webkit2gtk-4.0.tar.gz" -C "${ctx_lib%/usr/lib/x86_64-linux-gnu}/" \
      --strip-components=1 --no-same-owner webkit2gtk-4.0-package/usr/lib
  fi
  if [[ ! -e $ctx_lib/libjpeg.so.8 ]]; then
    dnf -y install cmake nasm gcc make
    local tmp; tmp=$(mktemp -d)
    ( cd "$tmp"
      dnf -q download --source libjpeg-turbo
      rpm2cpio libjpeg-turbo-*.src.rpm | cpio -idm --quiet
      tar xzf libjpeg-turbo-*.tar.gz
      cmake -S libjpeg-turbo-*/ -B build -DCMAKE_BUILD_TYPE=Release \
        -DWITH_JPEG8=1 -DENABLE_STATIC=0 -DWITH_TURBOJPEG=0 >/dev/null
      make -C build -j"$(nproc)" jpeg >/dev/null
      cp -P build/libjpeg.so.8* "$ctx_lib/" )
    rm -rf "$tmp"
  fi
  if [[ -z ${CTX_LIB:-} ]]; then
    echo /usr/lib/x86_64-linux-gnu > /etc/ld.so.conf.d/citrix-webkit2gtk4.0.conf
    ldconfig
  fi
}
install_citrix_webkit40

### 5. Fonts & wallpapers
FONT_NAME="JetBrainsMono Nerd Font"
FONT_DIR="/usr/local/share/fonts/JetBrainsMonoNF"
if fc-list | grep -qi "$FONT_NAME"; then
  echo "'$FONT_NAME' is already installed. Skipping download."
else
  mkdir -p "$FONT_DIR"
  tmp=$(mktemp -d)
  curl -fL -o "$tmp/jbm.zip" https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip
  unzip -o -q "$tmp/jbm.zip" -d "$FONT_DIR"
  rm -rf "$tmp"
  fc-cache -f
fi

[[ -d $TARGET_HOME/Pictures/wallpapers ]] || \
  as_user git clone https://github.com/f-klement/wallpapers.git "$TARGET_HOME/Pictures/wallpapers"

### USER SPACE TOOLS ###
# Shell rc files are NOT edited here: the stowed .zshrc already wires up nvm,
# bun, fzf and brew (appending would write through the stow symlink into the repo).

### 6. Node & Bun 4 TS and UV 4 Python
dnf -y install uv
[[ -d $TARGET_HOME/.nvm ]] || as_user bash -c '
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | PROFILE=/dev/null bash
  . "$HOME/.nvm/nvm.sh" && nvm install node'
[[ -x $TARGET_HOME/.bun/bin/bun ]] || as_user bash -c 'curl -fsSL https://bun.com/install | bash'

### 7. CLIs & TUIs (all packaged on Fedora)
dnf -y install fzf ripgrep gdu bleachbit direnv

[[ -x $TARGET_HOME/.local/bin/lazydocker ]] || command -v lazydocker >/dev/null || \
  as_user bash -c 'curl -fsSL https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash'

# Homebrew for linux (modern compilers/toolchains; system_update.sh upgrades it)
# The installer only wants sudo when /home/linuxbrew is not writable, so create
# it for the user here and tell it not to try (no password prompt mid-script).
if [[ ! -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
  install -d -o "$TARGET_USER" -g "$TARGET_USER" /home/linuxbrew /home/linuxbrew/.linuxbrew
  as_user env NONINTERACTIVE=1 HOMEBREW_NO_SUDO=1 bash -c '
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    /home/linuxbrew/.linuxbrew/bin/brew install gcc'
fi

### 8. Containers: rootless podman
# Fedora's podman already uses the native kernel overlay rootless (no
# fuse-overlayfs, no storage.conf surgery as on EL8). A docker CLI is only added
# if none exists; an installed moby-engine daemon keeps running untouched.
dnf -y install podman skopeo buildah crun
command -v docker >/dev/null || dnf -y --setopt=install_weak_deps=False install docker-cli docker-compose

loginctl enable-linger "$TARGET_USER"
grep -q "^$TARGET_USER:" /etc/subuid 2>/dev/null || \
  usermod --add-subuids 200000-265535 --add-subgids 200000-265535 "$TARGET_USER"

# cgroup v2 delegation: rootless Kubernetes (minikube --driver=podman) needs
# cpu/cpuset/io on top of the default memory/pids.
install -d /etc/systemd/system/user@.service.d
cat > /etc/systemd/system/user@.service.d/delegate.conf <<'DELEGATE'
[Service]
Delegate=cpu cpuset io memory pids
DELEGATE
systemctl daemon-reload

as_user systemctl --user enable --now podman.socket || true

### 9. Session hardening: intentionally none
# el_x11_bootstrap.sh 9.5 (gnome-session trimming, tracker, dirty_bytes, zswap,
# Brave --disable-gpu) fixes a VMware guest behind xrdp. None of it applies here:
# no gnome-session anchors this session, Fedora already runs zram swap, and the
# Intel iGPU accelerates Brave fine.

### 9.6 Theming - Rosé Pine (dark) / Rosé Pine Dawn (light) across toolkits
# Same assets as el_x11_bootstrap.sh 9.6; bin/theme.sh does the switching and
# autostart_wayland.sh runs `theme.sh apply` every session. Wayland differences:
#   GTK (native Wayland)  : reads gsettings directly - no gsd-xsettings needed.
#   Qt5 + Qt6             : QT_QPA_PLATFORMTHEME=kde (plasma-integration) reads
#       ~/.config/kdeglobals; theme.sh MERGES its colours into that file, so
#       Plasma's own settings in it survive.
#   Portals               : ~/.config/xdg-desktop-portal/qtile-portals.conf.
dnf -y install gtk-murrine-engine gtk2-engines

# One-time safety copy of Plasma's kdeglobals before theme.sh first merges into it.
KG="$TARGET_HOME/.config/kdeglobals"
if [[ -f $KG && ! -L $KG && ! -e $KG.pre-dotfiles ]]; then
  cp -p "$KG" "$KG.pre-dotfiles"
fi

ROSE_GTK_VER="v2.2.0"; ROSE_CUR_VER="v1.1.0"
as_user env ROSE_GTK_VER="$ROSE_GTK_VER" ROSE_CUR_VER="$ROSE_CUR_VER" bash -e <<'THEME'
  mkdir -p ~/.themes ~/.icons/default
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/gtk3.tar.gz"    "https://github.com/rose-pine/gtk/releases/download/$ROSE_GTK_VER/gtk3.tar.gz"
  for c in BreezeX-RosePine-Linux BreezeX-RosePineDawn-Linux; do
    curl -fsSL -o "$tmp/$c.tar.xz" "https://github.com/rose-pine/cursors/releases/download/$ROSE_CUR_VER/$c.tar.xz"
    tar xJf "$tmp/$c.tar.xz" -C ~/.icons 2>/dev/null
  done
  tar xzf "$tmp/gtk3.tar.gz" -C "$tmp" 2>/dev/null
  for t in rose-pine-gtk rose-pine-moon-gtk rose-pine-dawn-gtk; do
    rm -rf ~/.themes/$t && cp -r "$tmp/gtk3/$t" ~/.themes/
    # Upstream ships a mis-generated LIGHT gtk-dark.css (see el_x11_bootstrap.sh).
    for v in gtk-3.0 gtk-3.20; do cp ~/.themes/$t/$v/gtk.css ~/.themes/$t/$v/gtk-dark.css; done
  done
  printf '[Icon Theme]\nName=Default\nComment=Default Cursor Theme\nInherits=BreezeX-RosePine-Linux\n' > ~/.icons/default/index.theme
  rm -rf "$tmp"

  # dark seed; theme.sh re-asserts the saved mode every session.
  gsettings set org.gnome.desktop.interface gtk-theme    'rose-pine-gtk'
  gsettings set org.gnome.desktop.interface icon-theme   'Papirus-Dark'
  gsettings set org.gnome.desktop.interface cursor-theme 'BreezeX-RosePine-Linux'
  gsettings set org.gnome.desktop.interface cursor-size  24
  gsettings set org.gnome.desktop.interface font-name    'Cantarell 11'
  gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono Nerd Font 10'
  gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

  # flatpak: let sandboxes see the theme and kdeglobals; KDE-runtime Qt apps via
  # the KDE platform theme. GTK_THEME must NOT be forced (breaks libadwaita).
  flatpak override --user --unset-env=GTK_THEME
  flatpak override --user --env=QT_QPA_PLATFORMTHEME=kde \
    --filesystem=xdg-config/gtk-3.0:ro --filesystem=xdg-config/gtk-4.0:ro \
    --filesystem=xdg-config/kdeglobals:ro --filesystem=~/.themes:ro --filesystem=~/.icons:ro

  # Obsidian: official Rosé Pine theme in every known vault (no-op before its first run).
  OBS_REG=~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json
  if [ -f "$OBS_REG" ]; then
    python3 -c 'import json,sys; [print(v["path"]) for v in json.load(open(sys.argv[1]))["vaults"].values()]' "$OBS_REG" |
    while read -r vault; do
      [ -d "$vault/.obsidian" ] || continue
      mkdir -p "$vault/.obsidian/themes/Rose Pine"
      curl -fsSL -o "$vault/.obsidian/themes/Rose Pine/manifest.json" https://raw.githubusercontent.com/rose-pine/obsidian/main/manifest.json
      curl -fsSL -o "$vault/.obsidian/themes/Rose Pine/theme.css"     https://raw.githubusercontent.com/rose-pine/obsidian/main/theme.css
      [ -f "$vault/.obsidian/appearance.json" ] || cat > "$vault/.obsidian/appearance.json" <<'APPEARANCE'
{
  "theme": "obsidian",
  "cssTheme": "Rose Pine",
  "interfaceFontFamily": "Cantarell",
  "textFontFamily": "Cantarell",
  "monospaceFontFamily": "JetBrains Mono Nerd Font"
}
APPEARANCE
    done
  fi

  # Brave (RPM and flatpak profile dirs): Rosé Pine from the Chrome Web Store via
  # Chromium's "External Extensions" (picked up on next start, no click).
  for d in ~/.config/BraveSoftware/Brave-Browser ~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser; do
    mkdir -p "$d/External Extensions"
    printf '{\n  "external_update_url": "https://clients2.google.com/service/update2/crx"\n}\n' \
      > "$d/External Extensions/noimedcjdohhokijigpfcbjcfcaaahej.json"
  done

  # LibreWolf: locally built static-theme XPI sideloaded into every profile
  # (needs the stowed ~/.config/rose-pine-firefox; skipped before `stow .`).
  XPI=~/.config/rose-pine-firefox/rose-pine@rosepinetheme.com.xpi
  for ini in ~/.librewolf/profiles.ini ~/.var/app/io.gitlab.librewolf-community/.librewolf/profiles.ini; do
    [ -f "$ini" ] && [ -f "$XPI" ] || continue
    root=$(dirname "$ini")
    grep -E '^Path=' "$ini" | cut -d= -f2 | while read -r rel; do
      prof="$root/$rel"; [ -d "$prof" ] || continue
      mkdir -p "$prof/extensions"
      cp "$XPI" "$prof/extensions/"
      grep -q 'rose-pine@rosepinetheme.com' "$prof/user.js" 2>/dev/null && continue
      cat >> "$prof/user.js" <<'USERJS'

// ── Rosé Pine static theme, sideloaded from ~/.dotfiles/.config/rose-pine-firefox ──
user_pref("xpinstall.signatures.required", false);       // locally built XPI is unsigned
user_pref("extensions.sideloadScopes", 1);                // Firefox >=74 ignores profile extensions/ without this
user_pref("extensions.autoDisableScopes", 14);            // ...and auto-enable what it finds there
user_pref("extensions.activeThemeID", "rose-pine@rosepinetheme.com");
user_pref("layout.css.prefers-color-scheme.content-override", 0);  // sites get prefers-color-scheme: dark
USERJS
    done
  done
THEME

### 10. Default applications (desktop IDs differ between RPM, snap and flatpak)
first_desktop() { for d in "$@"; do
  for dir in /usr/share/applications /var/lib/snapd/desktop/applications /var/lib/flatpak/exports/share/applications; do
    [[ -f $dir/$d ]] && { echo "$d"; return; }
  done; done; }
EDITOR_DESKTOP=$(first_desktop codium.desktop codium_codium.desktop com.vscodium.codium.desktop)
BROWSER_DESKTOP=$(first_desktop brave-browser.desktop com.brave.Browser.desktop)

if [[ -n $EDITOR_DESKTOP ]]; then
  for m in text/plain text/x-python text/x-shellscript; do as_user xdg-mime default "$EDITOR_DESKTOP" "$m"; done
fi
if [[ -n $BROWSER_DESKTOP ]]; then
  as_user xdg-settings set default-web-browser "$BROWSER_DESKTOP" || true
  for m in x-scheme-handler/http x-scheme-handler/https text/html; do as_user xdg-mime default "$BROWSER_DESKTOP" "$m"; done
fi
# Kitty as default terminal (system-wide)
alternatives --install /usr/bin/x-terminal-emulator x-terminal-emulator /usr/bin/kitty 50
alternatives --set x-terminal-emulator /usr/bin/kitty
# VLC as default video & music player
for m in video/mp4 video/x-matroska audio/mpeg audio/x-wav; do as_user xdg-mime default vlc.desktop "$m"; done

cat <<DONE

✔ Fedora qtile-Wayland bootstrap complete.
  1. cd ~/.dotfiles && stow --ignore='^\.bashrc$' .   (skip .bashrc if you keep your own)
  2. log out, pick "Qtile (Wayland, dotfiles)" in SDDM (Plasma stays available).
  Logs: ~/.local/share/qtile/qtile.log, ~/.local/share/qtile-startup.log
DONE
