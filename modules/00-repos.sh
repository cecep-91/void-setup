#!/usr/bin/env bash
# Module 00: Enable Void nonfree/multilib repositories and switch mirrors to Fastly CDN.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

require_root
require_void

MIRROR="${VOID_MIRROR:-https://repo-fastly.voidlinux.org}"

log "Module 00: Enabling nonfree + multilib repos and configuring Fastly mirrors (${MIRROR})..."

xbps_install void-repo-nonfree void-repo-multilib void-repo-multilib-nonfree

if [ "${DRY_RUN}" = "1" ]; then
    info "[dry-run] write /etc/xbps.d/{00-repository-main,10-repository-nonfree,10-repository-multilib,10-repository-multilib-nonfree}.conf -> ${MIRROR}"
else
    mkdir -p /etc/xbps.d
    printf 'repository=%s/current\n'                  "${MIRROR}" > /etc/xbps.d/00-repository-main.conf
    printf 'repository=%s/current/nonfree\n'          "${MIRROR}" > /etc/xbps.d/10-repository-nonfree.conf
    printf 'repository=%s/current/multilib\n'         "${MIRROR}" > /etc/xbps.d/10-repository-multilib.conf
    printf 'repository=%s/current/multilib/nonfree\n' "${MIRROR}" > /etc/xbps.d/10-repository-multilib-nonfree.conf
    xbps-install -S
fi

ok "Module 00 (repos) complete."
