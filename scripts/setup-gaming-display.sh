#!/bin/sh
# Configure the hardware panel-fitter for full-screen stretched 4:3 (no black bars, smooth
# polyphase scaling instead of blocky nearest-neighbour) and add native-Hz 4:3 modes.
# Only 4:3 modes that fit inside the panel's native resolution are added.

# Auto-detect the internal panel (eDP/LVDS), falling back to the first connected output
OUT="$(xrandr --query 2>/dev/null | awk '/ connected/{print $1}' | grep -E '^(eDP|LVDS)' | head -n1)"
[ -n "$OUT" ] || OUT="$(xrandr --query 2>/dev/null | awk '/ connected/{print $1; exit}')"
[ -n "$OUT" ] || exit 0

xrandr --output "$OUT" --set "scaling mode" "Full" 2>/dev/null || true

# Native width/height and preferred (+) refresh rate of that output
INFO="$(xrandr --query 2>/dev/null | awk -v out="$OUT" '
    $1 == out { found=1; next }
    found && /^[^ ]/ { exit }
    found && /\+/ {
        split($1, wh, "x")
        for (i = 2; i <= NF; i++) if ($i ~ /\+/) { gsub(/[^0-9.]/, "", $i); printf "%s %s %.0f\n", wh[1], wh[2], $i; exit }
    }')"
NAT_W="$(echo "$INFO" | awk '{print $1}')"
NAT_H="$(echo "$INFO" | awk '{print $2}')"
RATE="$(echo "$INFO" | awk '{print $3}')"
[ -n "$NAT_W" ] && [ -n "$NAT_H" ] || exit 0
[ -n "$RATE" ] || RATE=60

# Create the mode if it does not exist yet, then attach it to the output if missing
add_mode() {
    NAME="$1"
    shift
    xrandr --query 2>/dev/null | grep -q "^ *${NAME} " || xrandr --newmode "$NAME" "$@" 2>/dev/null || true
    xrandr --query 2>/dev/null | awk -v out="$OUT" -v m="$NAME" '
        $1 == out { found=1; next }
        found && /^[^ ]/ { exit }
        found && $1 == m { ok=1 }
        END { exit ok ? 0 : 1 }' || xrandr --addmode "$OUT" "$NAME" 2>/dev/null || true
}

for res in "1440 1080" "1280 960" "1152 864" "1024 768"; do
    W="${res% *}"
    H="${res#* }"
    [ "$W" -le "$NAT_W" ] && [ "$H" -le "$NAT_H" ] || continue
    # Reduced-blanking CVT timings at the panel's native refresh rate
    LINE="$(cvt -r "$W" "$H" "$RATE" 2>/dev/null | sed -n 's/^Modeline "[^"]*" //p')"
    [ -n "$LINE" ] || LINE="$(cvt "$W" "$H" "$RATE" 2>/dev/null | sed -n 's/^Modeline "[^"]*" //p')"
    # shellcheck disable=SC2086
    [ -n "$LINE" ] && add_mode "${W}x${H}_${RATE}" $LINE
done
