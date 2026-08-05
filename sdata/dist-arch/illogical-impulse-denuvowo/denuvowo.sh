#!/usr/bin/env bash
#
# denuvowo — toggle cpuid_fault_emulation ("DenuvOwO") kernel support.
#   denuvowo enable   -> unload kvm_amd/kvm, load cpuid_fault_emulation
#   denuvowo disable  -> unload cpuid_fault_emulation, load kvm_amd/kvm
#   denuvowo status   -> prints "enabled" or "disabled"
#
# Elevates to root via sudo. The sudoers rule
# /etc/sudoers.d/21-denuvowo grants passwordless sudo for THIS
# script ONLY (not a blanket NOPASSWD), so there is no password
# prompt — and it works from the non-interactive Quickshell toggle.

set -euo pipefail

# If we are not root yet, re-exec through sudo.
# The sudoers rule allows this exact program without a password.
if [ "$(id -u)" -ne 0 ]; then
    exec sudo "/usr/local/bin/denuvowo" "$@"
fi

# Best-effort action: run it, report failure to stderr, but never abort.
try() {
    if "$@"; then
        return 0
    fi
    echo "denuvowo: command failed: $*" >&2
    return 1
}

# Is cpuid_fault_emulation currently loaded?
# We check /sys/module/<name> rather than `lsmod | grep -q` on purpose:
# `grep -q` exits the moment it matches, which closes the pipe and SIGPIPEs
# `lsmod`. With `set -o pipefail` set above, that SIGPIPE makes the whole
# pipeline report 141 (non-zero) instead of grep's 0, so the check would
# wrongly report "disabled" even when the module IS loaded. The /sys/module
# directory exists iff the module is loaded — no pipe, no SIGPIPE, no PATH
# dependency, and no dependence on the caller's SIGPIPE disposition.
loaded() { [ -d "/sys/module/cpuid_fault_emulation" ]; }

case "${1:-}" in
    enable)
        # Unloading kvm is best-effort: it may already be gone,
        # or be busy with a running VM. We still attempt to load cpuid either way.
        try modprobe -r kvm_amd kvm || true
        if ! try modprobe cpuid_fault_emulation; then
            echo "denuvowo: enable failed — could not load cpuid_fault_emulation" >&2
            exit 1
        fi
        ;;
    disable)
        try modprobe -r cpuid_fault_emulation || true
        if ! try modprobe kvm_amd kvm; then
            echo "denuvowo: disable failed — could not reload kvm" >&2
            exit 1
        fi
        ;;
    status)
        if loaded; then echo "enabled"; else echo "disabled"; fi
        ;;
    *)
        echo "Usage: denuvowo {enable|disable|status}" >&2
        exit 1
        ;;
esac
