#!/usr/bin/env bash
# Shared helper library for void-noir-glass installation modules.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"
ENABLE_SSH_HARDENING="${ENABLE_SSH_HARDENING:-1}"
INSTALL_DISCORD="${INSTALL_DISCORD:-1}"

# ANSI colors (disabled when not a tty)
if [ -t 1 ]; then
    C_BOLD="\033[1m"
    C_DIM="\033[2m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_RED="\033[31m"
    C_RESET="\033[0m"
else
    C_BOLD="" C_DIM="" C_GREEN="" C_YELLOW="" C_RED="" C_RESET=""
fi

log()  { printf "${C_BOLD}[+]${C_RESET} %s\n" "$*"; }
info() { printf "${C_DIM}    %s${C_RESET}\n" "$*"; }
ok()   { printf "${C_GREEN}[✓]${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}[!]${C_RESET} %s\n" "$*" >&2; }
err()  { printf "${C_RED}[✗]${C_RESET} %s\n" "$*" >&2; exit 1; }

require_root() {
    if [ "${DRY_RUN}" = "1" ]; then
        return 0
    fi
    if [ "$(id -u)" -ne 0 ]; then
        err "This script must be run as root (try: sudo $0 $*)"
    fi
}

require_void() {
    if [ "${DRY_RUN}" = "1" ]; then
        return 0
    fi
    if ! command -v xbps-install >/dev/null 2>&1; then
        err "xbps-install not found — this installer targets Void Linux (glibc x86_64)."
    fi
}

resolve_target_user() {
    if [ -n "${TARGET_USER:-}" ]; then
        :
    elif [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
        TARGET_USER="${SUDO_USER}"
    else
        TARGET_USER="$(awk -F: '$3 >= 1000 && $3 < 65000 && $7 !~ /nologin|false/ {print $1; exit}' /etc/passwd || true)"
    fi
    if [ -z "${TARGET_USER:-}" ]; then
        err "Could not auto-detect a non-root user. Pass --user <username> or set TARGET_USER."
    fi
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
        err "User '${TARGET_USER}' does not exist."
    fi
    TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
    TARGET_UID="$(id -u "${TARGET_USER}")"
    export TARGET_USER TARGET_HOME TARGET_UID
}

run_cmd() {
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} %s\n" "$*"
        return 0
    fi
    "$@"
}

xbps_install() {
    local pkgs=("$@")
    if [ "${#pkgs[@]}" -eq 0 ]; then
        return 0
    fi
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} xbps-install -Sy %s\n" "${pkgs[*]}"
        return 0
    fi
    xbps-install -Sy "${pkgs[@]}"
}

xbps_install_available() {
    local pkgs=()
    local p
    for p in "$@"; do
        if [ "${DRY_RUN}" = "1" ] || xbps-query -R "$p" >/dev/null 2>&1; then
            pkgs+=("$p")
        else
            warn "Package '$p' not found in active repos — skipping."
        fi
    done
    if [ "${#pkgs[@]}" -gt 0 ]; then
        xbps_install "${pkgs[@]}"
    fi
}

enable_service() {
    local svc="$1"
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} ln -sfn /etc/sv/%s /var/service/%s\n" "$svc" "$svc"
        return 0
    fi
    if [ -d "/etc/sv/${svc}" ]; then
        ln -sfn "/etc/sv/${svc}" "/var/service/${svc}"
    else
        warn "Service '/etc/sv/${svc}' not installed — skipping."
    fi
}

disable_service() {
    local svc="$1"
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} rm -f /var/service/%s\n" "$svc"
        return 0
    fi
    rm -f "/var/service/${svc}"
}

install_file() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} install -Dm%s %s %s\n" "$mode" "$src" "$dst"
        return 0
    fi
    install -Dm"${mode}" "$src" "$dst"
}

# Run a command inside the target user's active graphical X11/D-Bus session if one is running.
run_in_user_session() {
    local script="$1"
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} run_in_user_session(%s): <xfconf/session commands>\n" "${TARGET_USER}"
        return 0
    fi
    local pid dbus_addr disp
    pid="$(pgrep -u "${TARGET_USER}" -n xfce4-session 2>/dev/null || true)"
    if [ -z "$pid" ]; then
        warn "No active xfce4-session for '${TARGET_USER}'; skipping live session apply (will apply on next login)."
        return 1
    fi
    dbus_addr="$(tr '\0' '\n' < "/proc/${pid}/environ" 2>/dev/null | grep '^DBUS_SESSION_BUS_ADDRESS=' | cut -d= -f2- || true)"
    disp="$(tr '\0' '\n' < "/proc/${pid}/environ" 2>/dev/null | grep '^DISPLAY=' | cut -d= -f2- || true)"
    su -s /bin/bash - "${TARGET_USER}" -c "
export DISPLAY=\"${disp:-:0}\"
export XDG_RUNTIME_DIR=\"/run/user/${TARGET_UID}\"
export DBUS_SESSION_BUS_ADDRESS=\"${dbus_addr}\"
${script}
"
}

# Idempotently append a kernel parameter to GRUB_CMDLINE_LINUX_DEFAULT
grub_add_param() {
    local param="$1"
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} add GRUB param: %s\n" "$param"
        return 0
    fi
    [ -f /etc/default/grub ] || { warn "/etc/default/grub not found — skipping '$param'."; return 0; }
    local re="${param//./\\.}"
    if ! grep -Eq "^GRUB_CMDLINE_LINUX_DEFAULT=.*[ \"]${re}([ \"]|\$)" /etc/default/grub; then
        sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=\"\(.*\)\"|GRUB_CMDLINE_LINUX_DEFAULT=\"\1 ${param}\"|" /etc/default/grub
        sed -i 's|GRUB_CMDLINE_LINUX_DEFAULT=" |GRUB_CMDLINE_LINUX_DEFAULT="|' /etc/default/grub
        GRUB_DIRTY=1
    fi
}

grub_commit() {
    if [ "${DRY_RUN}" = "1" ]; then
        printf "${C_DIM}[dry-run]${C_RESET} update-grub\n"
        return 0
    fi
    if [ "${GRUB_DIRTY:-0}" = "1" ] && command -v update-grub >/dev/null 2>&1; then
        log "Updating GRUB configuration..."
        update-grub
        GRUB_DIRTY=0
    fi
}

# Detect the running kernel series package (e.g. linux6.18) for initramfs rebuilds
detect_running_kernel_pkg() {
    local major_minor
    major_minor="$(uname -r | awk -F. '{print $1"."$2}')"
    if [ "${DRY_RUN}" = "1" ] || xbps-query "linux${major_minor}" >/dev/null 2>&1; then
        echo "linux${major_minor}"
    else
        xbps-query -l | awk '/^ii linux[0-9]+\.[0-9]+-[0-9]/{print $2; exit}' | sed 's/-[0-9].*//'
    fi
}

# Print "intel", "amd" or "other" for the CPU vendor
cpu_vendor() {
    if grep -qi "GenuineIntel" /proc/cpuinfo 2>/dev/null; then echo intel
    elif grep -qi "AuthenticAMD" /proc/cpuinfo 2>/dev/null; then echo amd
    else echo other
    fi
}

# Print the PCI vendor ids (8086 intel, 1002 amd, 10de nvidia) of all display controllers
gpu_vendors() {
    lspci -n 2>/dev/null | awk '$2 ~ /^03/ {split($3, a, ":"); print a[1]}' | sort -u
}

# Detect the installed kernel series header package (e.g. linux6.18-headers)
detect_kernel_headers_pkg() {
    local kver major_minor
    kver="$(uname -r)"
    major_minor="$(echo "$kver" | awk -F. '{print $1"."$2}')"
    if [ "${DRY_RUN}" = "1" ]; then
        echo "linux${major_minor}-headers"
        return 0
    fi
    if xbps-query -R "linux${major_minor}-headers" >/dev/null 2>&1; then
        echo "linux${major_minor}-headers"
    else
        echo "linux-headers"
    fi
}
