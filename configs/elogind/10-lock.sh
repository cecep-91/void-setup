#!/bin/sh
# Always lock the active LightDM seat immediately before suspend/hibernate.
if [ "$1" = "pre" ]; then
    export XDG_SEAT_PATH="/org/freedesktop/DisplayManager/Seat0"
    /usr/bin/dm-tool lock 2>/dev/null || true
    sleep 0.4
fi
