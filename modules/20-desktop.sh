#!/usr/bin/env bash
# Module 20: Minimal Xorg + Intel/AMD graphics (auto-detected) + XFCE 4.20 + LightDM +
# xfce4-terminal + Firefox + Thunar/gvfs/ntfs-3g/tumbler + desktop portals + viewers + lid-close lock.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void
resolve_target_user

log "Module 20: Installing Xorg, GPU drivers, minimal XFCE 4.20, LightDM, xfce4-terminal & core apps..."

xbps_install \
    xorg mesa-dri vulkan-loader \
    xfwm4 xfce4-session xfce4-panel xfce4-settings xfdesktop xfconf \
    Thunar xfce4-power-manager xfce4-pulseaudio-plugin xfce4-clipman-plugin xfce4-genmon-plugin xfce-polkit xfce4-docklike-plugin \
    lightdm lightdm-gtk-greeter \
    gvfs gvfs-mtp gvfs-smb ntfs-3g tumbler ffmpegthumbnailer \
    xdg-desktop-portal xdg-desktop-portal-gtk \
    firefox xfce4-terminal pavucontrol xfce4-screenshooter \
    unzip 7zip xarchiver ristretto mpv mousepad

# Vulkan + video-acceleration stack for every detected GPU vendor (both if detection is impossible)
VENDORS="$(gpu_vendors)"
[ -n "$VENDORS" ] || VENDORS="8086 1002"
for v in $VENDORS; do
    case "$v" in
        8086) info "Intel graphics detected"; xbps_install_available intel-media-driver mesa-vulkan-intel ;;
        1002) info "AMD graphics detected";   xbps_install_available mesa-vulkan-radeon mesa-vaapi mesa-vdpau ;;
    esac
done

# QEMU/KVM guest integration: automatic display resize & clipboard via SPICE
if grep -qiE 'QEMU|KVM|Bochs' /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/product_name 2>/dev/null \
    || lspci -n 2>/dev/null | grep -qE '(^|[[:space:]])(1af4|1b36):'; then
    info "QEMU/KVM virtual machine detected — installing SPICE guest agent..."
    xbps_install_available spice-vdagent
    enable_service spice-vdagentd
fi

# Enable LightDM display manager
enable_service lightdm

# Configure hardware-decoded mpv (VA-API on the integrated GPU keeps playback cool)
install_file "${REPO_ROOT}/configs/mpv/mpv.conf" "${TARGET_HOME}/.config/mpv/mpv.conf" 0644
run_cmd chown -R "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/.config/mpv"

# Always lock screen via LightDM before suspend / lid close
log "Configuring auto-lock on lid close & suspend..."
install_file "${REPO_ROOT}/configs/elogind/10-lock.sh" "/etc/elogind/system-sleep/10-lock.sh" 0755

run_xfconf_session '
xfconf-query -c xfce4-session -p /general/LockCommand -n -t string -s "dm-tool lock"
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lock-screen-suspend-hibernate -n -t bool -s true
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/logind-handle-lid-switch -n -t bool -s false
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-battery -n -t uint -s 1
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-ac -n -t uint -s 1
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/inactivity-on-battery -n -t uint -s 15
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/blank-on-battery -n -t int -s 5
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-battery-sleep -n -t uint -s 10
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-battery-off -n -t uint -s 15
xfconf-query -c thunar -p /last-menubar-visible -n -t bool -s false
xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 0
' || warn "Failed to apply desktop XFCE settings."

ok "Module 20 (desktop) complete."
