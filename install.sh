#!/usr/bin/env bash
# void-noir-glass — Modular super-installer for Void Linux (XFCE + Noir Glass OS + Hybrid NVIDIA + Gaming)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

# Ordered canonical module registry: "<short-name>:<script>:<description>"
MODULES=(
    "repos:modules/00-repos.sh:Void Fastly mirrors + nonfree/multilib repositories"
    "base:modules/10-base.sh:Services, PipeWire (no mic suspend), NetworkManager + low-latency Wi-Fi, TLP, thermal-profile, chrony, zram, UFW, SSH"
    "desktop:modules/20-desktop.sh:Xorg, Intel/AMD graphics, minimal XFCE 4.20, LightDM, xfce4-terminal, Firefox, Thunar/gvfs, lid-lock"
    "nvidia:modules/30-nvidia-hybrid.sh:Hybrid NVIDIA (nvidia580, RTD3 D3cold 0W sleep, prime-run, dracut/GRUB)"
    "rice:modules/40-rice.sh:Noir Glass OS theme, 3 resolution-independent islands, Rofi, Dunst + zero-overlap Conky widgets"
    "gaming:modules/50-gaming.sh:Steam, 32-bit drivers, GameMode, MangoHud, Discord, BBR+fq_codel, RAM-scaled sysctl, 4:3 modes"
)

usage() {
    cat <<'EOF'
Usage: sudo ./install.sh [OPTIONS]

Run the full Void Linux setup or pick individual aspects cleanly.

Selection options:
  --all                 Run all modules in order (default if no selection flag given in non-interactive mode)
  --only <list>         Comma-separated modules to run (e.g. --only rice or --only nvidia,gaming)
  --skip <list>         Comma-separated modules to skip (e.g. --skip nvidia)
  --list                List all available modules and exit

Behavior options:
  --user <username>     Target non-root desktop user (default: $SUDO_USER or first UID>=1000 user)
  --mirror <url>        Void mirror base URL (default: https://repo-fastly.voidlinux.org)
  --nvidia-pkg <pkg>    NVIDIA driver package (default: nvidia580)
  --no-discord          Skip Discord inside the gaming module
  --no-ssh-hardening    Skip SSH key-only hardening inside the base module
  --dry-run             Print every step without modifying the system
  -h, --help            Show this help message

Examples:
  sudo ./install.sh --all                         # Full reproducible machine build
  sudo ./install.sh --skip nvidia                 # Intel/AMD-only laptop (skip NVIDIA module)
  sudo ./install.sh --only rice                   # Apply only the Noir Glass OS desktop rice
  sudo ./install.sh --only nvidia,gaming          # Only hybrid NVIDIA + Steam/Discord/4:3 gaming stack
  ./install.sh --all --dry-run                    # Preview every action safely without root
EOF
}

list_modules() {
    printf "${C_BOLD}Available modules:${C_RESET}\n"
    local entry name script desc
    for entry in "${MODULES[@]}"; do
        IFS=':' read -r name script desc <<< "$entry"
        printf "  %-10s  %-28s  %s\n" "$name" "$script" "$desc"
    done
}

module_exists() {
    local want="$1" entry name
    for entry in "${MODULES[@]}"; do
        IFS=':' read -r name _ _ <<< "$entry"
        [ "$name" = "$want" ] && return 0
    done
    return 1
}

in_csv() {
    local needle="$1" hay="$2"
    [[ ",${hay}," == *",${needle},"* ]]
}

MODE=""
ONLY_LIST=""
SKIP_LIST=""

while [ $# -gt 0 ]; do
    case "$1" in
        --all)              MODE="all" ;;
        --only)             shift; [ $# -gt 0 ] || err "--only requires a comma-separated list"; MODE="only"; ONLY_LIST="$1" ;;
        --skip)             shift; [ $# -gt 0 ] || err "--skip requires a comma-separated list"; MODE="${MODE:-all}"; SKIP_LIST="$1" ;;
        --list)             list_modules; exit 0 ;;
        --user)             shift; [ $# -gt 0 ] || err "--user requires a username"; export TARGET_USER="$1" ;;
        --mirror)           shift; [ $# -gt 0 ] || err "--mirror requires a URL"; export VOID_MIRROR="$1" ;;
        --nvidia-pkg)       shift; [ $# -gt 0 ] || err "--nvidia-pkg requires a package name"; export NVIDIA_PKG="$1" ;;
        --no-discord)       export INSTALL_DISCORD=0 ;;
        --no-ssh-hardening) export ENABLE_SSH_HARDENING=0 ;;
        --dry-run)          export DRY_RUN=1 ;;
        -h|--help)          usage; exit 0 ;;
        *)                  err "Unknown option: $1 (try --help)" ;;
    esac
    shift
done

# Interactive module picker when run with no flags in an interactive terminal
if [ -z "$MODE" ]; then
    if [ -t 0 ] && [ -t 1 ]; then
        list_modules
        printf "\nEnter modules to run (comma-separated, or 'all' [default: all]): "
        read -r reply
        reply="${reply:-all}"
        if [ "$reply" = "all" ]; then
            MODE="all"
        else
            MODE="only"
            ONLY_LIST="${reply// /}"
        fi
    else
        MODE="all"
    fi
fi

# Validate user-supplied module names
for list_var in "$ONLY_LIST" "$SKIP_LIST"; do
    [ -z "$list_var" ] && continue
    IFS=',' read -ra items <<< "$list_var"
    for item in "${items[@]}"; do
        [ -z "$item" ] && continue
        module_exists "$item" || err "Unknown module '${item}'. Run './install.sh --list' to see valid names."
    done
done

require_root
require_void
resolve_target_user

SELECTED=()
for entry in "${MODULES[@]}"; do
    IFS=':' read -r name script desc <<< "$entry"
    if [ "$MODE" = "only" ]; then
        in_csv "$name" "$ONLY_LIST" || continue
    fi
    if [ -n "$SKIP_LIST" ] && in_csv "$name" "$SKIP_LIST"; then
        continue
    fi
    SELECTED+=("$entry")
done

[ "${#SELECTED[@]}" -gt 0 ] || err "No modules selected."

printf "\n${C_BOLD}=== void-noir-glass installer ===${C_RESET}\n"
info "Target user : ${TARGET_USER} (${TARGET_HOME})"
info "Dry run     : ${DRY_RUN}"
info "Modules     : $(printf '%s ' "${SELECTED[@]%%:*}")"
printf "\n"

for entry in "${SELECTED[@]}"; do
    IFS=':' read -r name script desc <<< "$entry"
    printf -- "${C_BOLD}---> Running module: %s (%s)${C_RESET}\n" "$name" "$desc"
    bash "${SCRIPT_DIR}/${script}"
    printf "\n"
done

ok "All selected modules completed successfully!"
if [ "${DRY_RUN}" != "1" ]; then
    info "Reboot recommended if kernel modules, GRUB params, NVIDIA, or PAM limits were changed."
fi
