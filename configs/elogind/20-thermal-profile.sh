#!/bin/sh
# Re-apply saved CPU RAPL / TCC / GPU thermal profile after suspend or hibernate
# (BIOS resets MSR/MMIO RAPL and TCC Offset on S3/s2idle resume).
# Works as both an elogind system-sleep hook ($1="post") and a zzz.d/resume hook ($1="").
if [ "$1" = "post" ] || [ -z "$1" ]; then
    /usr/local/bin/thermal-profile restore >/dev/null 2>&1 || true
fi
