#!/bin/sh
# Interactive region screenshot -> ~/Pictures/Screenshots + clipboard + Dunst toast
mkdir -p "$HOME/Pictures/Screenshots"
f="$HOME/Pictures/Screenshots/$(date +%Y-%m-%d_%H-%M-%S).png"
maim -s "$f" && xclip -selection clipboard -t image/png < "$f" && notify-send -a "Screenshot" "Screenshot saved" "$(basename "$f") copied to clipboard"
