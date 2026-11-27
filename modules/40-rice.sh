#!/usr/bin/env bash
# Module 40: Noir Glass OS (Stealth Monochrome) desktop rice (vanilla-XFCE resource parity):
# - Fonts (Inter, Fira Code, Nerd Fonts Symbols, Noto), Papirus-Dark (grey), Bibata cursor, 4K dark wallpapers
# - Native XFWM4 compositor (0 extra daemons, instant fullscreen unredirect), Rofi + Power/Wi-Fi Menu, Dunst, Starship, Qt5/6
# - 3 non-overlapping floating glass top islands + conflict-free keyboard shortcuts (Super tap, Super+D, Super+V, Ctrl+Alt+T)
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void
resolve_target_user

log "Module 40: Installing Noir Glass OS (Stealth Monochrome) rice packages & assets..."

xbps_install \
    rofi dunst starship fish-shell conky cava playerctl xcape wmctrl xdotool \
    maim xclip qt5ct qt6ct \
    papirus-icon-theme papirus-folders adwaita-icon-theme \
    font-inter font-firacode nerd-fonts-symbols-ttf noto-fonts-ttf dejavu-fonts-ttf

# Dunst must own org.freedesktop.Notifications: remove the competing XFCE notification daemon
if [ "${DRY_RUN}" != "1" ]; then
    xbps-remove -Ry xfce4-notifyd 2>/dev/null || true
fi

# Monochrome grey Papirus folders
log "Applying monochrome grey Papirus folder icons..."
run_cmd papirus-folders -C grey --theme Papirus-Dark
run_cmd gtk-update-icon-cache -f /usr/share/icons/Papirus-Dark 2>/dev/null || true

# Crisp Bibata-Modern-Classic vector cursor
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] download Bibata-Modern-Classic cursor to /usr/share/icons/"
elif [ ! -d /usr/share/icons/Bibata-Modern-Classic ]; then
    log "Installing Bibata-Modern-Classic cursor theme..."
    mkdir -p /usr/share/icons
    curl -fsSL -o /tmp/bibata.tar.xz \
        "https://github.com/ful1e5/Bibata_Cursor/releases/latest/download/Bibata-Modern-Classic.tar.xz"
    tar -xf /tmp/bibata.tar.xz -C /usr/share/icons/
    rm -f /tmp/bibata.tar.xz
fi

# 3 curated dark-backdrop 4K wallpapers
log "Ensuring curated dark 4K wallpapers exist in /usr/share/backgrounds/..."
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] fetch noir-minimal-5k.jpg, noir-anime-4k.jpg, oled-astolfo-4k.png"
else
    mkdir -p /usr/share/backgrounds
    [ -s /usr/share/backgrounds/noir-minimal-5k.jpg ] || \
        curl -fsSL -o /usr/share/backgrounds/noir-minimal-5k.jpg "https://w.wallhaven.cc/full/md/wallhaven-mdjrqy.jpg"
    [ -s /usr/share/backgrounds/noir-anime-4k.jpg ] || \
        curl -fsSL -o /usr/share/backgrounds/noir-anime-4k.jpg   "https://w.wallhaven.cc/full/zm/wallhaven-zmkwmv.jpg"
    [ -s /usr/share/backgrounds/oled-astolfo-4k.png ] || \
        curl -fsSL -o /usr/share/backgrounds/oled-astolfo-4k.png "https://w.wallhaven.cc/full/e7/wallhaven-e72kv8.png"
    chmod 644 /usr/share/backgrounds/*
fi

# Install single-source-of-truth Noir Glass theme engine + screenshot helper
log "Installing Noir Glass theme engine into ${TARGET_HOME}/.config/noir-glass/..."
install_file "${REPO_ROOT}/rice/theme-tokens.json"     "${TARGET_HOME}/.config/noir-glass/theme-tokens.json" 0644
install_file "${REPO_ROOT}/rice/base-dark.css"         "${TARGET_HOME}/.config/noir-glass/base-dark.css"     0644
install_file "${REPO_ROOT}/rice/apply-theme.py"        "${TARGET_HOME}/.config/noir-glass/apply-theme.py"    0755
install_file "${REPO_ROOT}/scripts/screenshot-region.sh" "${TARGET_HOME}/.local/bin/screenshot-region.sh"    0755

if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] run apply-theme.py -> /usr/share/themes/Noir-Glass + user configs"
else
    python3 "${TARGET_HOME}/.config/noir-glass/apply-theme.py" \
        --tokens "${TARGET_HOME}/.config/noir-glass/theme-tokens.json" \
        --home "${TARGET_HOME}" \
        --system-root "/"

    rm -rf /usr/share/themes/Noir-Glass
    cp -r "${TARGET_HOME}/.themes/Noir-Glass" /usr/share/themes/Noir-Glass
    chmod -R a+rX /usr/share/themes/Noir-Glass

    # Starship prompt in ~/.bashrc (fallback) + default login shell -> fish
    touch "${TARGET_HOME}/.bashrc"
    grep -q 'starship init bash' "${TARGET_HOME}/.bashrc" || \
        printf '\neval "$(starship init bash)"\n' >> "${TARGET_HOME}/.bashrc"
    if [ -x /usr/bin/fish ]; then
        chsh -s /usr/bin/fish "${TARGET_USER}"
    fi

    mkdir -p "${TARGET_HOME}/.config/autostart" "${TARGET_HOME}/Pictures/Screenshots"

    # Remove files left behind by earlier versions of this rice
    rm -f "${TARGET_HOME}/.local/bin/start-clipman.sh" "${TARGET_HOME}/.local/bin/start-nm-applet.sh"
    rm -rf "${TARGET_HOME}"/.config/xfce4/panel/launcher-1[3-5]

    # Void launcher desktop entry for panel-1 plugin-1 (opens centered frosted Rofi)
    mkdir -p "${TARGET_HOME}/.config/xfce4/panel/launcher-1"
    cat <<'EOF' > "${TARGET_HOME}/.config/xfce4/panel/launcher-1/rofi-launcher.desktop"
[Desktop Entry]
Name=Applications
Comment=Open Application Launcher
Exec=rofi -show drun
Icon=void-logo-notext
Terminal=false
Type=Application
EOF

    chown -R "${TARGET_USER}:${TARGET_USER}" \
        "${TARGET_HOME}/.config" "${TARGET_HOME}/.local" "${TARGET_HOME}/.themes" \
        "${TARGET_HOME}/.bashrc" "${TARGET_HOME}/.xprofile" "${TARGET_HOME}/Pictures"
fi

# Apply live XFCE settings, 3 floating top islands, shortcuts & daemons if X11 session active
log "Applying XFCE theme, 3 floating top islands, keyboard shortcuts & daemons..."
run_in_user_session '
# Stop the panel first: on exit it writes every plugin setting back to xfconf and would
# overwrite the values applied below. It is started again at the end of this block.
xfce4-panel --quit 2>/dev/null || true
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    pgrep -u "$(id -u)" -x xfce4-panel >/dev/null || break
    sleep 0.3
done

# Theme, icons, cursor, font
xfconf-query -c xsettings -p /Net/ThemeName -n -t string -s "Noir-Glass"
xfconf-query -c xsettings -p /Net/IconThemeName -n -t string -s "Papirus-Dark"
xfconf-query -c xsettings -p /Gtk/CursorThemeName -n -t string -s "Bibata-Modern-Classic"
xfconf-query -c xsettings -p /Gtk/CursorThemeSize -n -t int -s 22
xfconf-query -c xsettings -p /Gtk/FontName -n -t string -s "Inter 10"
command -v gsettings >/dev/null 2>&1 && gsettings set org.gnome.desktop.interface color-scheme "prefer-dark" 2>/dev/null || true

# XFWM4 theme, built-in compositor (0 extra daemons, instant fullscreen unredirect, no dock/popup shadows), clean Alt+Tab dock, 4 workspaces
xfconf-query -c xfwm4 -p /general/theme -n -t string -s "Noir-Glass"
xfconf-query -c xfwm4 -p /general/use_compositing -n -t bool -s true
xfconf-query -c xfwm4 -p /general/unredirect_overlays -n -t bool -s true
xfconf-query -c xfwm4 -p /general/vblank_mode -n -t string -s "xpresent"
xfconf-query -c xfwm4 -p /general/show_dock_shadow -n -t bool -s false
xfconf-query -c xfwm4 -p /general/show_popup_shadow -n -t bool -s false
xfconf-query -c xfwm4 -p /general/show_frame_shadow -n -t bool -s true
xfconf-query -c xfwm4 -p /general/shadow_opacity -n -t int -s 35
xfconf-query -c xfwm4 -p /general/frame_opacity -n -t int -s 100
xfconf-query -c xfwm4 -p /general/inactive_opacity -n -t int -s 100
xfconf-query -c xfwm4 -p /general/move_opacity -n -t int -s 100
xfconf-query -c xfwm4 -p /general/resize_opacity -n -t int -s 100
xfconf-query -c xfwm4 -p /general/popup_opacity -n -t int -s 100
xfconf-query -c xfwm4 -p /general/cycle_preview -n -t bool -s false
xfconf-query -c xfwm4 -p /general/cycle_draw_frame -n -t bool -s false
xfconf-query -c xfwm4 -p /general/cycle_tabwin_mode -n -t int -s 0
xfconf-query -c xfwm4 -p /general/workspace_count -n -t int -s 4
xfconf-query -c xfwm4 -p /general/workspace_names -n -t string -t string -t string -t string -s "1" -s "2" -s "3" -s "4"

# Dark 4K primary wallpaper on every connected output & workspace, clean icon-free desktop
MONS="monitor0"
for o in $(xrandr --query 2>/dev/null | grep " connected" | cut -d" " -f1); do MONS="$MONS monitor${o}"; done
for m in $MONS; do
    for w in 0 1 2 3; do
        xfconf-query -c xfce4-desktop -p "/backdrop/screen0/${m}/workspace${w}/last-image" -n -t string -s "/usr/share/backgrounds/noir-minimal-5k.jpg"
        xfconf-query -c xfce4-desktop -p "/backdrop/screen0/${m}/workspace${w}/image-style" -n -t int -s 5
    done
done
xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 0

# Screen width drives the island anchors, so the layout is correct on any resolution
SCR_W=$(xrandr --current 2>/dev/null | grep -o "current [0-9]*" | head -n1 | cut -d" " -f2)
[ -n "$SCR_W" ] || SCR_W=1920
MID_X=$(( SCR_W / 2 ))
RIGHT_X=$(( SCR_W - 1 ))

# 3 non-overlapping auto-sized floating glass top islands (Left, Dead-Center, Right).
# bar_icon_size 20 keeps xfce4-pulseaudio-plugin horizontal ([mic][speaker], never stacked).
xfconf-query -c xfce4-panel -p /panels -n -t int -t int -t int -s 1 -s 2 -s 3
xfconf-query -c xfce4-panel -p /panels/dark-mode -n -t bool -s true

# Panel 1 (Top-Left: Void launcher + Docklike + Workspaces), Panel 2 (Dead-Center: Clock),
# Panel 3 (Top-Right: Clipboard + App Systray | Wi-Fi + Volume + Battery + Power)
for spec in "1:p=6;x=0;y=0:1 2 4" "2:p=9;x=${MID_X};y=0:9" "3:p=2;x=${RIGHT_X};y=0:11 6 12 7 8 10"; do
    n="${spec%%:*}"; rest="${spec#*:}"; pos="${rest%%:*}"; ids="${rest#*:}"
    P="/panels/panel-${n}"
    xfconf-query -c xfce4-panel -p "${P}/background-style" -n -t int -s 1
    xfconf-query -c xfce4-panel -p "${P}/background-rgba" -n -t double -t double -t double -t double -s 0 -s 0 -s 0 -s 0
    xfconf-query -c xfce4-panel -p "${P}/mode" -n -t uint -s 0
    xfconf-query -c xfce4-panel -p "${P}/nrows" -n -t uint -s 1
    xfconf-query -c xfce4-panel -p "${P}/autohide-behavior" -n -t uint -s 0
    xfconf-query -c xfce4-panel -p "${P}/size" -n -t int -s 42
    xfconf-query -c xfce4-panel -p "${P}/icon-size" -n -t int -s 20
    xfconf-query -c xfce4-panel -p "${P}/length" -n -t double -s 1.0
    xfconf-query -c xfce4-panel -p "${P}/position" -n -t string -s "${pos}"
    xfconf-query -c xfce4-panel -p "${P}/position-locked" -n -t bool -s true
    xfconf-query -c xfce4-panel -p "${P}/enable-struts" -n -t bool -s true
    args=(); for i in $ids; do args+=(-t int -s "$i"); done
    xfconf-query -c xfce4-panel -p "${P}/plugin-ids" -n -a "${args[@]}"
done

# Plugins
xfconf-query -c xfce4-panel -p /plugins/plugin-1 -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /plugins/plugin-1 -n -t string -s "launcher"
xfconf-query -c xfce4-panel -p /plugins/plugin-1/items -n -t string -a -s "rofi-launcher.desktop"

xfconf-query -c xfce4-panel -p /plugins/plugin-2 -n -t string -s "docklike"
xfconf-query -c xfce4-panel -p /plugins/plugin-2/forceIconSize -n -t bool -s true
xfconf-query -c xfce4-panel -p /plugins/plugin-2/iconSize -n -t int -s 20
xfconf-query -c xfce4-panel -p /plugins/plugin-2/indicatorColor -n -t string -s "rgb(228,228,234)"
xfconf-query -c xfce4-panel -p /plugins/plugin-2/indicatorColorFromTheme -n -t bool -s false
xfconf-query -c xfce4-panel -p /plugins/plugin-2/pinned -n -a -t string -s "thunar.desktop" -t string -s "xfce4-terminal.desktop" -t string -s "firefox.desktop"

xfconf-query -c xfce4-panel -p /plugins/plugin-4 -n -t string -s "pager"
xfconf-query -c xfce4-panel -p /plugins/plugin-4/miniature-view -n -t bool -s false
xfconf-query -c xfce4-panel -p /plugins/plugin-4/rows -n -t int -s 1
xfconf-query -c xfce4-panel -p /plugins/plugin-4/workspace-scrolling -n -t bool -s true

xfconf-query -c xfce4-panel -p /plugins/plugin-6 -n -t string -s "systray"
xfconf-query -c xfce4-panel -p /plugins/plugin-6/icon-size -n -t int -s 18
xfconf-query -c xfce4-panel -p /plugins/plugin-6/single-row -n -t bool -s true
xfconf-query -c xfce4-panel -p /plugins/plugin-6/square-icons -n -t bool -s false
xfconf-query -c xfce4-panel -p /plugins/plugin-6/symbolic-icons -n -t bool -s true

xfconf-query -c xfce4-panel -p /plugins/plugin-7 -n -t string -s "pulseaudio"
xfconf-query -c xfce4-panel -p /plugins/plugin-7/enable-keyboard-shortcuts -n -t bool -s true
xfconf-query -c xfce4-panel -p /plugins/plugin-7/rec-indicator-persistent -n -t bool -s false

xfconf-query -c xfce4-panel -p /plugins/plugin-8 -n -t string -s "power-manager-plugin"

xfconf-query -c xfce4-panel -p /plugins/plugin-9 -n -t string -s "clock"
xfconf-query -c xfce4-panel -p /plugins/plugin-9/mode -n -t int -s 2
xfconf-query -c xfce4-panel -p /plugins/plugin-9/digital-layout -n -t int -s 3
xfconf-query -c xfce4-panel -p /plugins/plugin-9/digital-time-font -n -t string -s "Inter SemiBold 10"
xfconf-query -c xfce4-panel -p /plugins/plugin-9/digital-time-format -n -t string -s "%a, %b %d   %H:%M"

xfconf-query -c xfce4-panel -p /plugins/plugin-10 -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /plugins/plugin-10 -n -t string -s "launcher"
xfconf-query -c xfce4-panel -p /plugins/plugin-10/items -n -t string -a -s "power-menu.desktop"

xfconf-query -c xfce4-panel -p /plugins/plugin-11 -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /plugins/plugin-11 -n -t string -s "xfce4-clipman-plugin"

xfconf-query -c xfce4-panel -p /plugins/plugin-12 -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /plugins/plugin-12 -n -t string -s "genmon"
xfconf-query -c xfce4-panel -p /plugins/plugin-12/command -n -t string -s "$HOME/.local/bin/wifi-status.sh"
xfconf-query -c xfce4-panel -p /plugins/plugin-12/use-label -n -t bool -s false
xfconf-query -c xfce4-panel -p /plugins/plugin-12/update-period -n -t int -s 5000
xfconf-query -c xfce4-panel -p /plugins/plugin-12/enable-single-row -n -t bool -s true

for n in 13 14 15 16 17 18; do
    xfconf-query -c xfce4-panel -p "/plugins/plugin-${n}" -r -R 2>/dev/null || true
done

# xfce4-terminal (Noir Glass monochrome, lightweight native GTK3/VTE)
xfconf-query -c xfce4-terminal -p /font-use-system -n -t bool -s false
xfconf-query -c xfce4-terminal -p /font-name -n -t string -s "Fira Code 10.5"
xfconf-query -c xfce4-terminal -p /background-mode -n -t string -s "TERMINAL_BACKGROUND_TRANSPARENT"
xfconf-query -c xfce4-terminal -p /background-darkness -n -t double -s 0.86
xfconf-query -c xfce4-terminal -p /color-foreground -n -t string -s "#f3f3f5"
xfconf-query -c xfce4-terminal -p /color-background -n -t string -s "#0e1016"
xfconf-query -c xfce4-terminal -p /color-cursor -n -t string -s "#e4e4ea"
xfconf-query -c xfce4-terminal -p /color-cursor-use-default -n -t bool -s false
xfconf-query -c xfce4-terminal -p /color-selection -n -t string -s "#ffffff"
xfconf-query -c xfce4-terminal -p /color-selection-background -n -t string -s "#4a4e5e"
xfconf-query -c xfce4-terminal -p /color-selection-use-default -n -t bool -s false
xfconf-query -c xfce4-terminal -p /color-use-theme -n -t bool -s false
xfconf-query -c xfce4-terminal -p /color-palette -n -t string -s "#18181d;#f27474;#7fd1a0;#f3c57a;#a6a6b8;#d4d4e0;#9cc7c7;#e4e4ea;#484852;#ff9494;#9be0b6;#f7d699;#c4c4d4;#ececf4;#b6dada;#ffffff"
xfconf-query -c xfce4-terminal -p /misc-menubar-default -n -t bool -s false
xfconf-query -c xfce4-terminal -p /misc-toolbar-default -n -t bool -s false
xfconf-query -c xfce4-terminal -p /misc-borders-default -n -t bool -s true
xfconf-query -c xfce4-terminal -p /misc-cursor-shape -n -t string -s "TERMINAL_CURSOR_SHAPE_IBEAM"
xfconf-query -c xfce4-terminal -p /misc-slim-tabs -n -t bool -s true
xfconf-query -c xfce4-terminal -p /misc-show-unsafe-paste-dialog -n -t bool -s false
xfconf-query -c xfce4-terminal -p /scrolling-bar -n -t string -s "TERMINAL_SCROLLBAR_NONE"
xfconf-query -c xfce4-terminal -p /scrolling-lines -n -t uint -s 10000

# Conflict-free keyboard ergonomics
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/Super_L" -r 2>/dev/null || true
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Primary><Alt>d" -r 2>/dev/null || true
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Alt>F1" -n -t string -s "rofi -show drun"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>Return" -n -t string -s "xfce4-terminal"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Primary><Alt>t" -n -t string -s "xfce4-terminal"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>e" -n -t string -s "thunar"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>v" -n -t string -s "xfce4-popup-clipman"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>t" -n -t string -s "/usr/local/bin/thermal-profile menu"
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>x" -n -t string -s "$HOME/.config/rofi/powermenu.sh"
xfconf-query -c xfce4-panel -p /plugins/clipman/settings/save-on-quit -n -t bool -s true
xfconf-query -c xfce4-panel -p /plugins/clipman/settings/max-texts-in-history -n -t uint -s 30
xfconf-query -c xfce4-panel -p /plugins/clipman/settings/add-primary-clipboard -n -t bool -s false
xfconf-query -c xfce4-panel -p /plugins/clipman/settings/history-ignore-primary-clipboard -n -t bool -s true
xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super><Shift>s" -n -t string -s "$HOME/.local/bin/screenshot-region.sh"
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>d" -n -t string -s "show_desktop_key"
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>q" -n -t string -s "close_window_key"
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>Left" -n -t string -s "tile_left_key"
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>Right" -n -t string -s "tile_right_key"
xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>Up" -n -t string -s "maximize_window_key"
for i in 1 2 3 4; do
    xfconf-query -c xfce4-keyboard-shortcuts -p "/xfwm4/custom/<Super>${i}" -n -t string -s "workspace_${i}_key"
done

# Restart live WM (built-in compositor), notifications, xcape, widgets, panel & desktop
pkill -u "$(id -u)" xfce4-notifyd 2>/dev/null || true
pkill -u "$(id -u)" dunst 2>/dev/null || true
pkill -u "$(id -u)" picom 2>/dev/null || true
pkill -u "$(id -u)" xcape 2>/dev/null || true
# (never `pkill -f` a pattern that also appears in this script: it would kill this very shell)
[ -r "${XDG_RUNTIME_DIR:-/tmp}/auto-compositor.pid" ] && kill "$(cat "${XDG_RUNTIME_DIR:-/tmp}/auto-compositor.pid")" 2>/dev/null || true
pkill -u "$(id -u)" -x auto-compositor 2>/dev/null || true
sleep 0.3
nohup xfwm4 --replace >/dev/null 2>&1 </dev/null &
sleep 1
nohup dunst >/dev/null 2>&1 </dev/null &
xcape -e "Super_L=Alt_L|F1"
nohup "$HOME/.local/bin/auto-compositor.sh" >/dev/null 2>&1 </dev/null &
"$HOME/.config/conky/start.sh"
nohup xfce4-panel >/dev/null 2>&1 </dev/null &
sleep 1
xfdesktop --reload
' || true

ok "Module 40 (rice) complete."
