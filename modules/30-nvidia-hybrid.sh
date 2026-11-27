#!/usr/bin/env bash
# Module 30: Hybrid Intel/AMD + NVIDIA laptop setup (NVIDIA-specific only):
# - Proprietary nvidia580 (avoids nvidia-595 GSP/ACPI boot rwlock deadlocks)
# - Fine-grained Runtime D3 (D3cold) sleep on AC & battery (0 W idle)
# - prime-run offload helper, nouveau blacklist, DRM KMS flags, dracut/initramfs
# TLP, thermald and thermal-profile live in module 10 (base).
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void

NVIDIA_PKG="${NVIDIA_PKG:-nvidia580}"
HEADERS_PKG="$(detect_kernel_headers_pkg)"

log "Module 30: Installing hybrid NVIDIA stack (${NVIDIA_PKG} + ${HEADERS_PKG})..."

xbps_install "${HEADERS_PKG}" "${NVIDIA_PKG}" tlp

# Modprobe, Dracut, Udev RTD3, and TLP drop-ins
log "Installing modprobe, dracut, udev RTD3, and TLP configurations..."
install_file "${REPO_ROOT}/configs/modprobe/nvidia-hybrid.conf" "/etc/modprobe.d/nvidia-hybrid.conf"   0644
install_file "${REPO_ROOT}/configs/dracut/nvidia.conf"          "/etc/dracut.conf.d/nvidia.conf"       0644
install_file "${REPO_ROOT}/configs/udev/80-nvidia-pm.rules"     "/etc/udev/rules.d/80-nvidia-pm.rules" 0644
install_file "${REPO_ROOT}/configs/tlp/03-nvidia-rtd3.conf"     "/etc/tlp.d/03-nvidia-rtd3.conf"       0644

# NVIDIA PRIME Render Offload helper
install_file "${REPO_ROOT}/scripts/prime-run" "/usr/local/bin/prime-run" 0755

# Kernel cmdline: blacklist nouveau + enable DRM KMS without fbdev conflict
grub_add_param "rd.driver.blacklist=nouveau"
grub_add_param "modprobe.blacklist=nouveau"
grub_add_param "nvidia-drm.modeset=1"
grub_add_param "nvidia-drm.fbdev=0"
grub_commit

enable_service tlp
enable_service nvidia-powerd

if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] regenerate initramfs (xbps-reconfigure -f linux<ver>), reload udev & tlp"
else
    udevadm control --reload-rules 2>/dev/null || true
    tlp start >/dev/null 2>&1 || true
    KPKG="$(detect_running_kernel_pkg)"
    if [ -n "${KPKG:-}" ]; then
        log "Rebuilding initramfs for ${KPKG} (omitting nouveau/early nvidia)..."
        xbps-reconfigure -f "${KPKG}"
    fi
fi

ok "Module 30 (nvidia-hybrid) complete."
