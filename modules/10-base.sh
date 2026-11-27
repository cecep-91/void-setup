#!/usr/bin/env bash
# Module 10: Universal system foundation (every machine gets these):
# services, PipeWire audio that never suspends the mic, NetworkManager + low-latency Wi-Fi,
# TLP (Wi-Fi/audio power rules), thermal-profile, chrony NTP, zramen swap, socklog, TRIM, UFW, SSH.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void
resolve_target_user

log "Module 10: Installing base system, audio, networking, power, logging & security..."

xbps_install \
    dbus elogind polkit curl tar xz nano btop fastfetch pciutils \
    NetworkManager network-manager-applet iw iproute2 lsof \
    pipewire wireplumber alsa-pipewire rtkit \
    tlp tlp-rdw \
    chrony zramen socklog-void cronie ufw os-prober btrfs-progs

VENDOR="$(cpu_vendor)"
case "$VENDOR" in
    intel) xbps_install_available intel-ucode thermald ;;
    amd)   xbps_install_available linux-firmware-amd ;;
esac

# 1. NetworkManager (replaces dhcpcd/wpa_supplicant) + low-latency Wi-Fi
log "Configuring NetworkManager, DNS and low-latency Wi-Fi..."
install_file "${REPO_ROOT}/configs/networkmanager/dns.conf"        "/etc/NetworkManager/conf.d/dns.conf"        0644
install_file "${REPO_ROOT}/configs/networkmanager/20-wifi-perf.conf" "/etc/NetworkManager/conf.d/20-wifi-perf.conf" 0644
install_file "${REPO_ROOT}/configs/modprobe/iwlwifi-perf.conf"     "/etc/modprobe.d/iwlwifi-perf.conf"          0644
install_file "${REPO_ROOT}/configs/udev/81-net-pm.rules"           "/etc/udev/rules.d/81-net-pm.rules"          0644
install_file "${REPO_ROOT}/configs/udev/82-audio-perf.rules"       "/etc/udev/rules.d/82-audio-perf.rules"      0644
if [ "${DRY_RUN}" != "1" ]; then
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger --action=add --subsystem-match=pci --attr-match=class=0x028000 --attr-match=class=0x020000 2>/dev/null || true
    udevadm trigger --action=add --subsystem-match=pci --attr-match=class=0x040380 --attr-match=class=0x040300 2>/dev/null || true
    udevadm trigger --action=add --subsystem-match=hdaudio 2>/dev/null || true
fi
disable_service dhcpcd
disable_service wpa_supplicant
enable_service dbus
enable_service NetworkManager

# 2. PipeWire + WirePlumber + PipeWire-Pulse + ALSA routing (mic/DAC never auto-suspend)
log "Configuring PipeWire + WirePlumber + ALSA bridge..."
install_file "${REPO_ROOT}/configs/pipewire/51-disable-suspension.conf" "/etc/wireplumber/wireplumber.conf.d/51-disable-suspension.conf" 0644
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] link PipeWire/WirePlumber/ALSA drop-ins and /etc/xdg/autostart/pipewire.desktop"
else
    mkdir -p /etc/pipewire/pipewire.conf.d /etc/alsa/conf.d /etc/xdg/autostart
    ln -sfn /usr/share/examples/wireplumber/10-wireplumber.conf   /etc/pipewire/pipewire.conf.d/10-wireplumber.conf
    ln -sfn /usr/share/examples/pipewire/20-pipewire-pulse.conf   /etc/pipewire/pipewire.conf.d/20-pipewire-pulse.conf
    ln -sfn /usr/share/alsa/alsa.conf.d/50-pipewire.conf          /etc/alsa/conf.d/50-pipewire.conf
    ln -sfn /usr/share/alsa/alsa.conf.d/99-pipewire-default.conf  /etc/alsa/conf.d/99-pipewire-default.conf
    ln -sfn /usr/share/applications/pipewire.desktop              /etc/xdg/autostart/pipewire.desktop
fi

# 3. TLP: Wi-Fi/NIC/audio never power-managed, unused Bluetooth off; thermal-profile CLI
log "Configuring TLP and thermal-profile..."
install_file "${REPO_ROOT}/configs/tlp/01-wifi.conf"       "/etc/tlp.d/01-wifi.conf"       0644
install_file "${REPO_ROOT}/configs/tlp/02-bluetooth.conf"  "/etc/tlp.d/02-bluetooth.conf"  0644
install_file "${REPO_ROOT}/configs/tlp/04-audio-perf.conf" "/etc/tlp.d/04-audio-perf.conf" 0644
install_file "${REPO_ROOT}/scripts/thermal-profile"               "/usr/local/bin/thermal-profile"                  0755
install_file "${REPO_ROOT}/configs/sudoers/thermal-profile"       "/etc/sudoers.d/zz-thermal-profile"               0440
install_file "${REPO_ROOT}/configs/elogind/20-thermal-profile.sh" "/etc/elogind/system-sleep/20-thermal-profile.sh" 0755
install_file "${REPO_ROOT}/configs/elogind/20-thermal-profile.sh" "/etc/zzz.d/resume/60-thermal-profile.sh"         0755
enable_service tlp
[ "$VENDOR" = "intel" ] && enable_service thermald

if [ "${DRY_RUN}" != "1" ]; then
    rm -f /etc/sudoers.d/thermal-profile
    visudo -cf /etc/sudoers.d/zz-thermal-profile >/dev/null 2>&1 || err "Invalid sudoers file: /etc/sudoers.d/zz-thermal-profile"
    if [ -f /etc/rc.local ] && ! grep -q '/usr/local/bin/thermal-profile restore' /etc/rc.local; then
        printf '\n# Apply saved CPU/GPU thermal profile on boot\n/usr/local/bin/thermal-profile restore >/dev/null 2>&1 || true\n' >> /etc/rc.local
    fi
    tlp start >/dev/null 2>&1 || true
    rfkill block bluetooth 2>/dev/null || true
    /usr/local/bin/thermal-profile restore >/dev/null 2>&1 || true
fi

# 4. Compressed RAM swap (ZSTD 50%), NTP clock sync, persistent syslog, weekly SSD TRIM
log "Enabling zramen (ZSTD), chronyd, socklog, cronie + weekly fstrim..."
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] configure /etc/sv/zramen/conf, /etc/cron.weekly/fstrim, noatime in /etc/fstab"
else
    mkdir -p /etc/sv/zramen /etc/cron.weekly
    cat <<'CONF' > /etc/sv/zramen/conf
export ZRAM_COMP_ALGORITHM=zstd
export ZRAM_SIZE=50
CONF
    cat <<'CONF' > /etc/cron.weekly/fstrim
#!/bin/sh
/usr/bin/fstrim -av
CONF
    chmod 755 /etc/cron.weekly/fstrim
    usermod -aG socklog "${TARGET_USER}" 2>/dev/null || true

    # Add noatime to ext4 root & boot mounts in /etc/fstab (idempotent)
    cp -n /etc/fstab /etc/fstab.bak 2>/dev/null || true
    sed -i '/[[:space:]]\/[[:space:]]\+ext4[[:space:]]\+defaults[[:space:]]/s/defaults/defaults,noatime/' /etc/fstab
    sed -i '/[[:space:]]\/boot[[:space:]]\+ext4[[:space:]]\+defaults[[:space:]]/s/defaults/defaults,noatime/' /etc/fstab
    mount -o remount / 2>/dev/null || true
    mount -o remount /boot 2>/dev/null || true
fi

enable_service zramen
enable_service chronyd
enable_service socklog-unix
enable_service nanoklogd
enable_service cronie

# 5. Firewall (UFW: deny incoming, allow outgoing, rate-limit SSH). Idempotent: existing rules are kept.
log "Configuring UFW firewall..."
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] ufw default deny incoming; allow outgoing; limit 22/tcp; ufw enable"
else
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    ufw limit 22/tcp comment "SSH rate-limited" >/dev/null
    ufw --force enable >/dev/null
fi
enable_service ufw

# Enable GRUB os-prober for automatic Windows / multi-OS dual-boot detection
if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] enable GRUB_DISABLE_OS_PROBER=false in /etc/default/grub"
elif [ -f /etc/default/grub ]; then
    if grep -q "GRUB_DISABLE_OS_PROBER" /etc/default/grub; then
        sed -i 's/^#*GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' /etc/default/grub
    else
        printf '\nGRUB_DISABLE_OS_PROBER=false\n' >> /etc/default/grub
    fi
    GRUB_DIRTY=1
    grub_commit
fi

# 6. SSH hardening (only disables passwords if an authorized_keys file already exists!)
if [ "${ENABLE_SSH_HARDENING}" = "1" ] && [ -d /etc/ssh ]; then
    if [ "${DRY_RUN}" = "1" ]; then
        info "[dry-run] harden /etc/ssh/sshd_config.d/99-hardening.conf (only if authorized_keys present)"
    elif [ -s /root/.ssh/authorized_keys ] || [ -s "${TARGET_HOME}/.ssh/authorized_keys" ]; then
        log "Hardening SSH (key-only authentication; authorized_keys verified)..."
        ssh-keygen -A >/dev/null 2>&1 || true
        install_file "${REPO_ROOT}/configs/ssh/99-hardening.conf" "/etc/ssh/sshd_config.d/99-hardening.conf" 0644
        sshd -t
        sv restart /var/service/sshd 2>/dev/null || true
    else
        warn "No non-empty authorized_keys found — skipping SSH password lockout for safety."
    fi
fi

ok "Module 10 (base) complete."
