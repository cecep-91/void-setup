#!/usr/bin/env bash
# Module 50: Gaming stack & optimizations:
# - Steam + 32-bit drivers (auto-matches the detected Intel/AMD/NVIDIA GPUs + Mesa/Vulkan/PipeWire)
# - GameMode, MangoHud (stealth monochrome), Vulkan-Tools
# - Native Discord (no autostart, optional via INSTALL_DISCORD=0)
# - Crisp native-Hz (144Hz) in-game 4:3 stretched hardware panel-fitter modes (zero pixelation)
# - Sysctl (vm.max_map_count, BBR + fq_codel, RAM-scaled min_free_kbytes), PAM limits, watchdog off
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void
resolve_target_user

log "Module 50: Installing Steam, 32-bit gaming drivers, GameMode & MangoHud..."

GAMING_PKGS=(
    steam steam-udev-rules
    mesa-dri-32bit vulkan-loader-32bit
    libglvnd-32bit libdrm-32bit libgcc-32bit libstdc++-32bit gnutls-32bit
    libpipewire-32bit alsa-pipewire-32bit pipewire-32bit libpulseaudio-32bit
    gamemode libgamemode-32bit
    MangoHud MangoHud-32bit
    Vulkan-Tools
    libatomic libXScrnSaver
)

# 32-bit Vulkan driver for every detected GPU vendor (both Mesa drivers if detection is impossible)
VENDORS="$(gpu_vendors)"
[ -n "$VENDORS" ] || VENDORS="8086 1002"
for v in $VENDORS; do
    case "$v" in
        8086) GAMING_PKGS+=(mesa-vulkan-intel-32bit) ;;
        1002) GAMING_PKGS+=(mesa-vulkan-radeon-32bit) ;;
    esac
done

# Match the installed NVIDIA driver branch automatically (never mix nvidia580 with nvidia 595!)
if [ "${DRY_RUN}" = "1" ]; then
    GAMING_PKGS+=(nvidia580-libs-32bit)
elif xbps-query nvidia580 >/dev/null 2>&1; then
    GAMING_PKGS+=(nvidia580-libs-32bit)
elif xbps-query nvidia >/dev/null 2>&1; then
    GAMING_PKGS+=(nvidia-libs-32bit)
fi

xbps_install_available "${GAMING_PKGS[@]}"

# 1. Kernel sysctl, BBR module, I/O schedulers, PAM limits, GameMode group & configs
log "Applying gaming sysctl, BBR, I/O schedulers, ulimit, GameMode & MangoHud configs..."
install_file "${REPO_ROOT}/configs/sysctl/99-gaming.conf"             "/etc/sysctl.d/99-gaming.conf"              0644
install_file "${REPO_ROOT}/configs/modprobe/bbr-modules-load.conf"    "/etc/modules-load.d/bbr.conf"              0644
install_file "${REPO_ROOT}/configs/udev/60-schedulers.rules"          "/etc/udev/rules.d/60-schedulers.rules"     0644
install_file "${REPO_ROOT}/configs/limits/99-gaming.conf"             "/etc/security/limits.d/99-gaming.conf"     0644
install_file "${REPO_ROOT}/configs/gamemode/gamemode.ini"             "${TARGET_HOME}/.config/gamemode.ini"       0644
install_file "${REPO_ROOT}/configs/mangohud/MangoHud.conf"            "${TARGET_HOME}/.config/MangoHud/MangoHud.conf" 0644

# vm.min_free_kbytes = 1% of RAM clamped to 64-256 MiB (scales from 4 GB to 64 GB machines)
MEM_KB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 16000000)"
MIN_FREE_KB=$(( MEM_KB / 100 ))
[ "$MIN_FREE_KB" -lt 65536 ] && MIN_FREE_KB=65536
[ "$MIN_FREE_KB" -gt 262144 ] && MIN_FREE_KB=262144
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] write /etc/sysctl.d/99-gaming-mem.conf (vm.min_free_kbytes = ${MIN_FREE_KB})"
else
    printf '# 1%% of RAM, clamped to 64-256 MiB\nvm.min_free_kbytes = %s\n' "$MIN_FREE_KB" > /etc/sysctl.d/99-gaming-mem.conf
    modprobe tcp_bbr 2>/dev/null || true
    modprobe sch_fq_codel 2>/dev/null || true
    sysctl --system >/dev/null 2>&1 || true
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --subsystem-match=block 2>/dev/null || true
    usermod -aG gamemode "${TARGET_USER}" 2>/dev/null || true
fi

# Disable the 10 ms split-lock #AC trap (Intel 12th gen+) and the hardware watchdog (Intel/AMD)
case "$(cpu_vendor)" in
    intel)
        grub_add_param "split_lock_detect=off"
        grub_add_param "modprobe.blacklist=iTCO_wdt" ;;
    amd)
        grub_add_param "modprobe.blacklist=sp5100_tco" ;;
esac
grub_add_param "nowatchdog"
grub_commit

# Transparent Hugepages: background-deferred allocation to cut TLB misses without compaction stalls
if [ "${DRY_RUN}" != "1" ]; then
    [ -w /sys/kernel/mm/transparent_hugepage/enabled ] && echo always > /sys/kernel/mm/transparent_hugepage/enabled || true
    [ -w /sys/kernel/mm/transparent_hugepage/defrag ] && echo defer+madvise > /sys/kernel/mm/transparent_hugepage/defrag || true
    if [ -f /etc/rc.local ] && ! grep -q 'transparent_hugepage/defrag' /etc/rc.local; then
        printf '\n# Gaming THP: always + background-deferred defrag (no compaction stutters)\necho always > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true\necho defer+madvise > /sys/kernel/mm/transparent_hugepage/defrag 2>/dev/null || true\n' >> /etc/rc.local
    fi
fi

# 2. Native-Hz (144Hz) 4:3 stretched hardware panel-fitter setup (zero pixelation)
log "Configuring native-Hz 4:3 stretched in-game display modes..."
install_file "${REPO_ROOT}/scripts/setup-gaming-display.sh" "${TARGET_HOME}/.local/bin/setup-gaming-display.sh" 0755
if [ "${DRY_RUN}" != "1" ]; then
    mkdir -p "${TARGET_HOME}/.config/autostart"
    cat <<EOF > "${TARGET_HOME}/.config/autostart/gaming-display.desktop"
[Desktop Entry]
Type=Application
Name=Gaming 4:3 Stretched Display Setup
Exec=${TARGET_HOME}/.local/bin/setup-gaming-display.sh
Hidden=false
X-GNOME-Autostart-enabled=true
EOF
    chown -R "${TARGET_USER}:${TARGET_USER}" \
        "${TARGET_HOME}/.config/gamemode.ini" \
        "${TARGET_HOME}/.config/MangoHud" \
        "${TARGET_HOME}/.local/bin/setup-gaming-display.sh" \
        "${TARGET_HOME}/.config/autostart/gaming-display.desktop"
fi
run_in_user_session '"$HOME/.local/bin/setup-gaming-display.sh"' || true

# 3. Native official Discord (no autostart!)
if [ "${INSTALL_DISCORD}" = "1" ]; then
    log "Installing native official Discord into /opt/discord (autostart disabled)..."
    if [ "${DRY_RUN}" = "1" ]; then
        info "[dry-run] download Discord Linux tarball -> /opt/discord, /usr/local/bin/discord, discord.desktop (no autostart)"
    else
        if [ ! -x /opt/discord/discord ]; then
            mkdir -p /opt /tmp/discord-dl
            curl -fSL "https://discord.com/api/download?platform=linux&format=tar.gz" -o /tmp/discord-dl/discord.tar.gz
            rm -rf /opt/discord
            tar -xzf /tmp/discord-dl/discord.tar.gz -C /tmp/discord-dl/
            mv /tmp/discord-dl/Discord /opt/discord
            rm -rf /tmp/discord-dl
            chmod -R a+rX /opt/discord
        fi

        cat <<'EOF' > /usr/local/bin/discord
#!/bin/sh
exec /opt/discord/discord --enable-gpu-rasterization --enable-zero-copy "$@"
EOF
        chmod 755 /usr/local/bin/discord

        cat <<'EOF' > /usr/share/applications/discord.desktop
[Desktop Entry]
Name=Discord
StartupWMClass=discord
Comment=All-in-one voice and text chat for gamers
GenericName=Internet Messenger
Exec=/usr/local/bin/discord --url -- %u
Icon=discord
Type=Application
Categories=Network;InstantMessaging;
MimeType=x-scheme-handler/discord;
Path=/opt/discord
EOF
        update-desktop-database /usr/share/applications 2>/dev/null || true

        # Disable auto-startup & host update lock
        mkdir -p "${TARGET_HOME}/.config/discord"
        python3 -c '
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text()) if p.exists() else {}
d["SKIP_HOST_UPDATE"] = True
d["OPEN_ON_STARTUP"] = False
d["MINIMIZE_TO_TRAY"] = True
p.write_text(json.dumps(d, indent=2) + "\n")
' "${TARGET_HOME}/.config/discord/settings.json"
        chown -R "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/.config/discord"

        # Pre-bootstrap client binary if not yet bootstrapped
        if [ ! -x "${TARGET_HOME}/.config/discord/Discord" ] && [ -x /opt/discord/updater_bootstrap ]; then
            log "Bootstrapping Discord client binary (headless)..."
            su -s /bin/sh - "${TARGET_USER}" -c "/opt/discord/updater_bootstrap --no-gui '${TARGET_HOME}/.config/discord' stable https://updates.discord.com/" || true
        fi
    fi
else
    info "Skipping Discord installation (--no-discord)."
fi

ok "Module 50 (gaming) complete."
