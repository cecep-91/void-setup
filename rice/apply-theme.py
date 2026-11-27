#!/usr/bin/env python3
"""Single-source-of-truth theme generator for Noir Glass OS (Stealth Monochrome)."""
import argparse
import glob
import json
import os
import re
import subprocess
from pathlib import Path


def write(path: Path, content: str, mode: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        os.chmod(path, mode)


def detect_net_iface() -> str:
    """Auto-detect primary wireless or wired interface for Conky telemetry."""
    net = Path("/sys/class/net")
    if net.is_dir():
        ifaces = sorted(p.name for p in net.iterdir() if p.name != "lo")
        for prefix in ("wl", "en", "eth"):
            for name in ifaces:
                if name.startswith(prefix):
                    return name
        if ifaces:
            return ifaces[0]
    return "wlp0s20f3"


def generate_xfwm4(theme_dir: Path, t: dict):
    c = t["colors"]
    d = theme_dir / "xfwm4"
    d.mkdir(parents=True, exist_ok=True)
    write(
        d / "themerc",
        f"""active_text_color={c['text_primary']}
inactive_text_color={c['text_muted']}
active_text_shadow_color=#000000
inactive_text_shadow_color=#000000
button_offset=8
button_spacing=6
full_width_title=true
maximized_offset=0
shadow_delta_height=0
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=0
shadow_opacity=0
show_app_icon=false
title_horizontal_offset=10
title_shadow_active=false
title_shadow_inactive=false
title_vertical_offset_active=0
title_vertical_offset_inactive=0
""",
    )

    def solid_xpm(name, w, h, bg, bd=None, side=None):
        lines = [f"/* XPM */\nstatic char * {name}_xpm[] = {{"]
        if bd:
            lines += [f'"{w} {h} 2 1",', f'"a c {bg}",', f'"b c {bd}",']
        else:
            lines += [f'"{w} {h} 1 1",', f'"a c {bg}",']
        for y in range(h):
            row = []
            for x in range(w):
                is_b = bool(bd) and (
                    (side == "top" and y == 0)
                    or (side == "bottom" and y == h - 1)
                    or (side == "left" and x == 0)
                    or (side == "right" and x == w - 1)
                    or (side == "tl" and (y == 0 or x == 0))
                    or (side == "tr" and (y == 0 or x == w - 1))
                    or (side == "bl" and (y == h - 1 or x == 0))
                    or (side == "br" and (y == h - 1 or x == w - 1))
                )
                row.append("b" if is_b else "a")
            lines.append(f'"{"".join(row)}"{"," if y < h - 1 else ""}')
        lines.append("};")
        write(d / f"{name}.xpm", "\n".join(lines) + "\n")

    def button_xpm(name, bg, dot, bd_top):
        w, h = 22, 28
        lines = [
            f"/* XPM */\nstatic char * {name}_xpm[] = {{",
            f'"{w} {h} 3 1",',
            f'"a c {bg}",',
            f'"b c {bd_top}",',
            f'"c c {dot}",',
        ]
        cx, cy, r2 = 10.5, 14.0, 22.0
        for y in range(h):
            row = "".join(
                "b" if y == 0 else ("c" if (x - cx) ** 2 + (y - cy) ** 2 <= r2 else "a")
                for x in range(w)
            )
            lines.append(f'"{row}"{"," if y < h - 1 else ""}')
        lines.append("};")
        write(d / f"{name}.xpm", "\n".join(lines) + "\n")

    act_bg, ina_bg = "#121215", "#17171B"
    act_bd, ina_bd = "#26262C", "#1F1F25"
    for st, bg, bd in [("active", act_bg, act_bd), ("inactive", ina_bg, ina_bd)]:
        for i in range(1, 6):
            solid_xpm(f"title-{i}-{st}", 4, 28, bg, bd, "top")
        solid_xpm(f"top-left-{st}", 6, 28, bg, bd, "tl")
        solid_xpm(f"top-right-{st}", 6, 28, bg, bd, "tr")
        solid_xpm(f"left-{st}", 1, 16, bg, bd, "left")
        solid_xpm(f"right-{st}", 1, 16, bg, bd, "right")
        solid_xpm(f"bottom-{st}", 16, 1, bg, bd, "bottom")
        solid_xpm(f"bottom-left-{st}", 3, 3, bg, bd, "bl")
        solid_xpm(f"bottom-right-{st}", 3, 3, bg, bd, "br")

    button_xpm("close-active", act_bg, "#7E7E8A", act_bd)
    button_xpm("close-prelight", act_bg, c["status_danger"], act_bd)
    button_xpm("close-pressed", act_bg, "#D65A5A", act_bd)
    button_xpm("close-inactive", ina_bg, "#3A3A44", ina_bd)

    for btn in [
        "maximize",
        "maximize-toggled",
        "hide",
        "shade",
        "shade-toggled",
        "stick",
        "stick-toggled",
    ]:
        button_xpm(f"{btn}-active", act_bg, "#646470", act_bd)
        button_xpm(f"{btn}-prelight", act_bg, c["accent"], act_bd)
        button_xpm(f"{btn}-pressed", act_bg, "#FFFFFF", act_bd)
        button_xpm(f"{btn}-inactive", ina_bg, "#34343D", ina_bd)


def generate_gtk3_theme(theme_dir: Path, t: dict, base_gresource: str | None, base_css: Path | None = None):
    c = t["colors"]
    g = t["geometry"]
    out = theme_dir / "gtk-3.0"
    out.mkdir(parents=True, exist_ok=True)
    css = ""

    if base_css and base_css.exists():
        css = base_css.read_text(encoding="utf-8")
    elif base_gresource and Path(base_gresource).exists():
        css = subprocess.check_output(
            ["gresource", "extract", base_gresource, "/org/gnome/arc-theme/gtk-main-dark.css"],
            text=True,
        )

    if css:

        def remap_hex(m):
            h = m.group(0)
            r, gr, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            if b > r + 40 and b > 140:
                return c["selection_bg"] if b > 200 else c["selection_bg_hover"]
            if b >= r + 4:
                if max(r, gr, b) < 135:
                    lum = max(11, min(46, int((r * 0.25 + gr * 0.30 + b * 0.20) * 0.46)))
                else:
                    lum = int((r + gr + b) / 3)
                return f"#{lum:02x}{lum:02x}{min(255, lum + 2):02x}"
            return h

        def remap_rgba(m):
            r, gr, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
            if b > r + 40 and b > 140:
                return f"rgba(74, 78, 94, {a})"
            if b >= r + 4:
                if max(r, gr, b) < 135:
                    lum = max(11, min(46, int((r * 0.25 + gr * 0.30 + b * 0.20) * 0.46)))
                else:
                    lum = int((r + gr + b) / 3)
                return f"rgba({lum}, {lum}, {min(255, lum + 2)}, {a})"
            return m.group(0)

        css = re.sub(r"#[0-9a-fA-F]{6}\b", remap_hex, css)
        css = re.sub(
            r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)",
            remap_rgba,
            css,
        )
        css = re.sub(r"-gtk-icon-source:\s*-gtk-scaled\([^;]*\);", "-gtk-icon-source: none;", css)
        css = re.sub(r"background-image:\s*-gtk-scaled\([^;]*\);", "background-image: none;", css)

    # Append crisp token-driven overrides (vector controls, accessible focus rings, monochrome palette)
    css += f"""
/* =========================================================
   NOIR GLASS — STEALTH MONOCHROME TOKENS
   ========================================================= */
@define-color theme_bg_color {c['bg_surface']};
@define-color theme_fg_color {c['text_primary']};
@define-color theme_base_color {c['bg_canvas']};
@define-color theme_text_color {c['text_primary']};
@define-color theme_selected_bg_color {c['selection_bg']};
@define-color theme_selected_fg_color {c['selection_fg']};
@define-color selected_bg_color {c['selection_bg']};
@define-color selected_fg_color {c['selection_fg']};
@define-color link_color {c['link']};
@define-color borders #26262C;

*:focus {{
    outline-color: {c['accent_border']};
    outline-style: solid;
    outline-width: 1px;
    outline-offset: -1px;
}}

*:link,
button:link,
button:link > label,
button:visited,
button:visited > label {{
    color: {c['link']};
}}
*:link:hover,
button:link:hover > label {{
    color: #FFFFFF;
}}

button, entry, combobox button {{
    border-radius: {g['radius_control']}px;
}}

button:active,
button:checked,
button.suggested-action,
row:selected,
treeview:selected,
treeview.view:selected,
treeview.view:selected:focus,
iconview:selected,
.view:selected,
.view text:selected,
textview text:selected,
textview text selection,
entry selection,
entry selection:focus,
.thunar toolbar entry selection,
.thunar toolbar entry selection:focus,
.thunar .inline-toolbar entry selection,
.thunar .inline-toolbar entry selection:focus,
.primary-toolbar entry selection,
.primary-toolbar entry selection:focus,
headerbar entry selection,
headerbar entry selection:focus,
.osd entry selection,
.osd entry selection:focus,
entry.warning selection,
entry.warning selection:focus,
entry.error selection,
entry.error selection:focus,
entry.search-missing selection,
entry.search-missing selection:focus,
infobar.info selection,
infobar.question selection,
infobar.warning selection,
infobar.error selection,
label selection,
label:selected,
calendar:selected,
*:selected,
selection {{
    background-color: {c['selection_bg']};
    color: {c['selection_fg']};
}}
button.suggested-action:hover,
button:checked:hover {{
    background-color: {c['selection_bg_hover']};
    border-color: {c['selection_bg_hover']};
    color: {c['selection_fg']};
}}
button.suggested-action:active,
button:checked:active {{
    background-color: {c['selection_bg_active']};
    border-color: {c['selection_bg_active']};
    color: {c['selection_fg']};
}}
button:active label,
button:checked label,
button.suggested-action label,
button.suggested-action:hover label,
row:selected label,
.view:selected label {{
    background-color: transparent;
    color: {c['selection_fg']};
}}

menu menuitem:hover,
menu menuitem:selected,
.menu menuitem:hover,
.menu menuitem:selected,
.context-menu menuitem:hover,
.context-menu menuitem:selected,
popover menuitem:hover,
popover menuitem:selected,
menuitem:hover,
menuitem:selected,
menuitem.button.flat:hover,
modelbutton.flat:hover {{
    background-color: {c['accent_soft']};
    color: #FFFFFF;
    border-radius: 8px;
}}
menu menuitem:hover label,
menu menuitem:selected label,
menu menuitem:hover arrow,
.menu menuitem:hover label,
.menu menuitem:selected label,
.context-menu menuitem:hover label,
.context-menu menuitem:selected label,
popover menuitem:hover label,
popover menuitem:selected label,
menuitem:hover label,
menuitem:selected label,
menuitem.button.flat:hover label,
menuitem.button.flat:hover arrow,
modelbutton.flat:hover label,
modelbutton.flat:hover arrow {{
    background-color: transparent;
    color: #FFFFFF;
}}

.thunar toolbar entry,
.thunar .inline-toolbar entry,
.primary-toolbar entry,
headerbar entry {{
    background-color: rgba(28, 28, 34, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.10);
    color: {c['text_primary']};
    border-radius: {g['radius_control']}px;
}}
.thunar toolbar entry:focus,
.thunar .inline-toolbar entry:focus,
.primary-toolbar entry:focus,
headerbar entry:focus {{
    background-color: rgba(34, 34, 42, 0.94);
    border: 1px solid {c['accent']};
    color: {c['text_primary']};
    box-shadow: none;
}}

checkbutton check, treeview.check {{
    -gtk-icon-source: none;
    background-image: none;
    background-color: {c['bg_elevated']};
    border: 1px solid #45454F;
    border-radius: 5px;
    min-width: 15px;
    min-height: 15px;
    color: {c['on_accent']};
}}
checkbutton check:checked, treeview.check:checked {{
    -gtk-icon-source: -gtk-icontheme("object-select-symbolic");
    background-color: {c['accent']};
    border-color: {c['accent']};
    color: {c['on_accent']};
}}
radiobutton radio, treeview.radio {{
    -gtk-icon-source: none;
    background-image: none;
    background-color: {c['bg_elevated']};
    border: 1px solid #45454F;
    border-radius: 999px;
    min-width: 15px;
    min-height: 15px;
}}
radiobutton radio:checked, treeview.radio:checked {{
    background-color: {c['accent']};
    border: 4px solid {c['accent']};
    box-shadow: inset 0 0 0 3px {c['on_accent']};
}}
switch {{
    background-image: none;
    background-color: #24262E;
    border: 1px solid #3A3D4A;
    border-radius: 999px;
    min-width: 34px;
    min-height: 18px;
    padding: 2px;
    color: transparent;
    font-size: 0;
}}
switch:checked {{
    background-color: {c['selection_bg']};
    border-color: {c['selection_bg_hover']};
}}
switch slider {{
    background-image: none;
    background-color: #C8CAD4;
    border: none;
    border-radius: 999px;
    min-width: 14px;
    min-height: 14px;
}}
switch:checked slider {{
    background-color: #FFFFFF;
}}
scale trough {{
    background-color: #2A2A32;
    border-radius: 999px;
    min-height: 5px;
    border: none;
}}
scale highlight {{
    background-color: {c['accent']};
    border-radius: 999px;
    border: none;
}}
scale slider {{
    background-image: none;
    background-color: {c['text_primary']};
    border: 2px solid {c['bg_canvas']};
    border-radius: 999px;
    min-width: 14px;
    min-height: 14px;
}}
scrollbar slider {{
    background-color: #383842;
    border-radius: 999px;
}}
scrollbar slider:hover {{
    background-color: {c['accent']};
}}
"""
    write(out / "gtk.css", css)
    write(out / "gtk-dark.css", css)


def generate_user_configs(home: Path, t: dict, system_root: Path):
    c = t["colors"]
    g = t["geometry"]
    ty = t["typography"]
    a = t["assets"]
    cfg = home / ".config"

    # 1. GTK3 user overrides (Top bar capsules, Calendar popup, Thunar frosted glass, Alt-Tab)
    write(
        cfg / "gtk-3.0" / "settings.ini",
        f"""[Settings]
gtk-theme-name={t['name']}
gtk-icon-theme-name={a['icon_theme']}
gtk-cursor-theme-name={a['cursor_theme']}
gtk-cursor-theme-size={a['cursor_size']}
gtk-font-name={ty['sans']} {ty['ui_size']}
gtk-application-prefer-dark-theme=1
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
""",
    )

    write(
        cfg / "gtk-3.0" / "gtk.css",
        f"""/* =========================================================
   NOIR GLASS — SHELL, TOP BAR, THUNAR, CALENDAR & OVERLAYS
   ========================================================= */
.xfce4-panel,
.xfce4-panel.background {{
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
    color: {c['text_primary']};
}}

/* Floating dark glass capsules (32px pill inside 42px panel -> exact 5px top == 5px bottom margin) */
#launcher-1 button,
#docklike-plugin,
#clock-button {{
    background-color: {c['bg_glass']};
    border: 1px solid {c['border_glass']};
    border-radius: {g['radius_pill']}px;
    margin-top: 5px;
    margin-bottom: 5px;
    box-shadow: none;
}}

#launcher-1 button {{
    margin-left: 16px;
    margin-right: 6px;
    padding: 0 10px;
}}
#launcher-1 button:hover {{
    background-color: rgba(34, 34, 42, 0.86);
    border-color: {c['accent_border']};
}}

#docklike-plugin {{
    padding: 0 8px;
    margin-right: 6px;
}}
#docklike-plugin button {{
    background-color: transparent;
    border: none;
    box-shadow: none;
    border-radius: {g['radius_pill']}px;
    padding: 2px 6px;
    margin: 2px 2px;
    transition: background-color 150ms ease;
}}
#docklike-plugin button:hover {{
    background-color: {c['accent_soft']};
}}

/* Monochrome Workspace Capsule (1 2 3 4) */
#pager-4 button {{
    background-color: {c['bg_glass']};
    border-top: 1px solid {c['border_glass']};
    border-bottom: 1px solid {c['border_glass']};
    border-left: none;
    border-right: none;
    border-radius: 0;
    box-shadow: none;
    min-width: 28px;
    min-height: 0;
    padding: 0 8px;
    margin: 5px 0;
    color: {c['text_secondary']};
    font-weight: 600;
    font-size: 9pt;
    transition: background-color 150ms ease, color 150ms ease;
}}
#pager-4 button:first-child {{
    border-top-left-radius: {g['radius_pill']}px;
    border-bottom-left-radius: {g['radius_pill']}px;
    border-left: 1px solid {c['border_glass']};
    padding-left: 12px;
}}
#pager-4 button:last-child {{
    border-top-right-radius: {g['radius_pill']}px;
    border-bottom-right-radius: {g['radius_pill']}px;
    border-right: 1px solid {c['border_glass']};
    padding-right: 12px;
}}
#pager-4 button:hover {{
    background-color: rgba(42, 42, 50, 0.86);
    color: #FFFFFF;
}}
#pager-4 button:checked {{
    background-color: rgba(255, 255, 255, 0.22);
    color: #FFFFFF;
    font-weight: 700;
}}

/* Dead-Center Date & Time Pill */
#clock-button {{
    padding: 0 18px;
    font-weight: 600;
    font-feature-settings: "tnum";
}}
.xfce4-panel #clock-button:hover,
.xfce4-panel #clock-button:checked,
.xfce4-panel #clock-button:active {{
    background-color: rgba(34, 34, 42, 0.90);
    border-color: {c['accent_border']};
    color: {c['text_primary']};
}}
.xfce4-panel #clock-button:checked label,
.xfce4-panel #clock-button:active label {{
    background-color: transparent;
    color: {c['text_primary']};
}}

/* =========================================================
   RIGHT UNIFIED GLASS ISLAND
   Seamless 32px glass pill (y=5..37 inside 42px panel -> exact 5px top == 5px bottom);
   Layout: [Clipboard] [App Tray Icons...] | [Wi-Fi] [Volume] [Battery 100%] [Power]
   100% deterministic divider on #genmon-12 (Wi-Fi), zero :first-child hacks,
   identical 26px rounded pill hover on EVERY icon, uniform 6px spacing (3px each side).
   ========================================================= */
#systray-6,
#systray-6 > frame,
#systray-6 > frame > border,
#systray-6 > box > * {{
    border: none;
    background: transparent;
    box-shadow: none;
    padding: 0;
    margin: 0;
}}

/* Systray sits at native y=0..42 (margin: 0) so ALL current & incoming
   tray icons (SNI + legacy XEmbed) auto-center at exact y=21! */
#systray-6 > box {{
    background-color: transparent;
    background-image: linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0.18) 0px,
        rgba(255, 255, 255, 0.18) 1px,
        rgba(14, 16, 22, 0.78) 1px,
        rgba(14, 16, 22, 0.78) 31px,
        rgba(255, 255, 255, 0.18) 31px,
        rgba(255, 255, 255, 0.18) 32px
    );
    background-size: 100% 32px;
    background-position: 0px 5px;
    background-repeat: no-repeat;
    border: none;
    box-shadow: none;
    margin: 0;
    padding: 0;
}}

/* Universal 26x26 circular tray buttons (Steam, Discord, and EVERY incoming tray app) */
#systray-6 button,
#sn-button {{
    background-color: transparent;
    border: none;
    box-shadow: none;
    border-radius: {g['radius_pill']}px;
    min-height: 26px;
    min-width: 26px;
    padding: 0;
    margin: 8px 3px;
    transition: background-color 150ms ease;
}}
#systray-6 socket:hover,
#systray-6 widget:hover {{
    background-color: {c['accent_soft']};
    border-radius: {g['radius_pill']}px;
}}

/* Unbroken y=5..37 glass capsule on panel control shells */
#xfce4-clipman-plugin,
#genmon-12 .genmon_plugin,
.genmon_plugin,
#pulseaudio-button,
#xfce4-power-manager-plugin,
#launcher-10 button {{
    background-color: {c['bg_glass']};
    border-top: 1px solid {c['border_glass']};
    border-bottom: 1px solid {c['border_glass']};
    border-left: none;
    border-right: none;
    border-radius: 0;
    box-shadow: none;
    margin-top: 5px;
    margin-bottom: 5px;
    margin-left: 0;
    margin-right: 0;
    padding: 0 3px;
    min-height: 0;
    min-width: 0;
    color: {c['text_primary']};
}}

/* Smooth native rounded left cap on Clipman */
#xfce4-clipman-plugin {{
    border-top-left-radius: {g['radius_pill']}px;
    border-bottom-left-radius: {g['radius_pill']}px;
    border-left: 1px solid {c['border_glass']};
    padding-left: 5px;
    padding-right: 3px;
}}

/* Permanent crisp 1px x 14px vertical divider right before Wi-Fi (#genmon-12) */
#genmon-12 .genmon_plugin,
.genmon_plugin {{
    background-image: linear-gradient(rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.34));
    background-size: 1px 14px;
    background-position: 7px center;
    background-repeat: no-repeat;
    padding-left: 13px;
    padding-right: 2px;
}}
.genmon_imagebox {{
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}}
#genmon-12 button,
.genmon_imagebutton {{
    background-color: transparent;
    border: none;
    box-shadow: none;
    border-radius: {g['radius_pill']}px;
    min-width: 26px;
    min-height: 26px;
    padding: 0;
    margin: 2px 0;
    color: {c['text_primary']};
    transition: background-color 150ms ease, color 150ms ease;
}}

/* Smooth native rounded right cap on Power launcher */
#launcher-10 button {{
    border-top-right-radius: {g['radius_pill']}px;
    border-bottom-right-radius: {g['radius_pill']}px;
    border-right: 1px solid {c['border_glass']};
    padding-left: 3px;
    padding-right: 5px;
    margin-right: 16px;
}}

/* Exact 26x26 inner circle hover targets for Clipman, Volume & Power; 26px stadium pill for Battery */
#xfce4-clipman-plugin > image,
#launcher-10 button > image {{
    border-radius: {g['radius_pill']}px;
    min-width: 26px;
    min-height: 26px;
    padding: 0;
    margin: 2px 0;
    background-color: transparent;
    transition: background-color 150ms ease, color 150ms ease;
}}
/* xfce4-pulseaudio-plugin 0.5.1 flips to a vertical [mic / speaker] stack when
   panel size > 2 * icon-size + 4. bar_icon_size (20) keeps it horizontal at 42 px,
   so the recording indicator sits beside the speaker instead of below it. */
#pulseaudio-button > box {{
    background-color: transparent;
    border-radius: {g['radius_pill']}px;
    min-width: 26px;
    min-height: 26px;
    padding: 0 3px;
    margin: 2px 0;
    transition: background-color 150ms ease, color 150ms ease;
}}
#pulseaudio-button > box > image,
#pulseaudio-button > image {{
    padding: 0;
    margin: 0;
    background-color: transparent;
}}
#pulseaudio-button image.recording-indicator {{
    color: {c['status_danger']};
}}
#xfce4-power-manager-plugin > box {{
    border-radius: {g['radius_pill']}px;
    min-height: 26px;
    padding: 0 7px;
    margin: 2px 0;
    background-color: transparent;
    transition: background-color 150ms ease, color 150ms ease;
}}

/* Keep outer glass shell UNCHANGED on hover/checked/active */
.xfce4-panel #xfce4-clipman-plugin:hover,
.xfce4-panel #xfce4-clipman-plugin:checked,
.xfce4-panel #xfce4-clipman-plugin:active,
.xfce4-panel #pulseaudio-button:hover,
.xfce4-panel #pulseaudio-button:checked,
.xfce4-panel #pulseaudio-button:active,
.xfce4-panel #xfce4-power-manager-plugin:hover,
.xfce4-panel #xfce4-power-manager-plugin:checked,
.xfce4-panel #xfce4-power-manager-plugin:active,
.xfce4-panel #launcher-10 button:hover,
.xfce4-panel #launcher-10 button:checked,
.xfce4-panel #launcher-10 button:active {{
    background-color: {c['bg_glass']};
    color: #FFFFFF;
}}

/* Identical sleek 26px rounded pill hover highlight across ALL icons on the Right Island */
.xfce4-panel #systray-6 button:hover,
.xfce4-panel #systray-6 button:active,
.xfce4-panel #systray-6 button:checked,
.xfce4-panel #sn-button:hover,
.xfce4-panel #sn-button:active,
.xfce4-panel #sn-button:checked,
.xfce4-panel #genmon-12 button:hover,
.xfce4-panel #genmon-12 button:active,
.xfce4-panel #genmon-12 button:checked,
.xfce4-panel .genmon_imagebutton:hover,
.xfce4-panel .genmon_imagebutton:active,
.xfce4-panel .genmon_imagebutton:checked,
.xfce4-panel #xfce4-clipman-plugin:hover > image,
.xfce4-panel #xfce4-clipman-plugin:checked > image,
.xfce4-panel #xfce4-clipman-plugin:active > image,
.xfce4-panel #pulseaudio-button:hover > box,
.xfce4-panel #pulseaudio-button:checked > box,
.xfce4-panel #pulseaudio-button:active > box,
.xfce4-panel #xfce4-power-manager-plugin:hover > box,
.xfce4-panel #xfce4-power-manager-plugin:checked > box,
.xfce4-panel #xfce4-power-manager-plugin:active > box,
.xfce4-panel #launcher-10 button:hover > image,
.xfce4-panel #launcher-10 button:checked > image,
.xfce4-panel #launcher-10 button:active > image {{
    background-color: {c['accent_soft']};
    color: #FFFFFF;
}}
.xfce4-panel #pulseaudio-button:checked > box > label,
.xfce4-panel #pulseaudio-button:hover > box > label,
.xfce4-panel #xfce4-power-manager-plugin:checked > box > label,
.xfce4-panel #xfce4-power-manager-plugin:hover > box > label {{
    background-color: transparent;
    color: #FFFFFF;
}}

/* Modern Frosted Calendar Popup (flush border matches undecorated GtkWindow) */
calendar {{
    background-color: {c['bg_glass_strong']};
    color: {c['text_primary']};
    border: 1px solid {c['border_glass']};
    border-radius: 0;
    padding: 4px 6px;
    font-family: "{ty['sans']}";
    font-size: 11pt;
    min-width: 316px;
    min-height: 248px;
}}
calendar.header {{
    background-color: rgba(255, 255, 255, 0.05);
    border: none;
    border-bottom: 1px solid {c['border_subtle']};
    border-radius: 0;
    color: {c['text_primary']};
    font-weight: 700;
    padding: 6px 8px;
}}
calendar.button {{
    color: {c['text_primary']};
    border-radius: 8px;
    padding: 4px 8px;
}}
calendar.button:hover {{
    background-color: {c['accent_soft']};
    color: #FFFFFF;
}}
calendar.highlight {{
    color: {c['text_secondary']};
    font-weight: 600;
}}
calendar:selected {{
    background-color: {c['accent']};
    color: {c['on_accent']};
    border-radius: 8px;
    font-weight: 700;
}}
calendar:indeterminate {{
    color: #4E4E58;
}}

/* Menus, Context Submenus & Volume Popup (transparent CSD wrapper so corners clip cleanly) */
window.csd.popup,
window.csd.popup.background,
.csd.popup {{
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
}}
.csd.popup decoration,
window.csd.popup decoration {{
    border-radius: 12px;
    border: none;
    background-color: transparent;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}}
menu, .menu, .context-menu {{
    margin: 0;
    padding: 5px;
    background-color: {c['bg_glass_strong']};
    border: 1px solid {c['border_glass']};
    border-radius: 0;
    color: {c['text_primary']};
}}
.csd menu, .csd .menu, .csd .context-menu,
popover, popover.background {{
    background-color: {c['bg_glass_strong']};
    border: 1px solid {c['border_glass']};
    border-radius: 12px;
    color: {c['text_primary']};
}}
popover, popover.background {{
    padding: 5px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}}
menu menuitem:hover,
menu menuitem:selected,
.menu menuitem:hover,
.menu menuitem:selected,
.context-menu menuitem:hover,
.context-menu menuitem:selected,
popover menuitem:hover,
popover menuitem:selected {{
    background-color: {c['accent_soft']};
    color: #FFFFFF;
    border-radius: 8px;
}}
menu menuitem:hover label,
menu menuitem:selected label,
.menu menuitem:hover label,
.menu menuitem:selected label,
.context-menu menuitem:hover label,
.context-menu menuitem:selected label,
popover menuitem:hover label,
popover menuitem:selected label {{
    background-color: transparent;
    color: #FFFFFF;
}}

/* Translucent Thunar File Manager */
window.thunar {{
    background-color: rgba(14, 14, 18, 0.92);
}}
window.thunar menubar,
window.thunar toolbar,
window.thunar .location-bar,
window.thunar statusbar {{
    background-color: rgba(16, 16, 20, 0.88);
    border-color: {c['border_subtle']};
}}
window.thunar paned,
window.thunar .standard-view,
window.thunar scrolledwindow,
window.thunar viewport,
window.thunar treeview.view,
window.thunar iconview.view {{
    background-color: transparent;
}}
window.thunar .sidebar,
window.thunar .shortcuts-pane {{
    background-color: rgba(10, 10, 13, 0.86);
    border-right: 1px solid {c['border_subtle']};
}}
window.thunar treeview.view:selected,
window.thunar iconview.view:selected {{
    background-color: {c['accent_hover']};
    border-radius: {g['radius_control']}px;
    color: #FFFFFF;
}}

/* Sleek Frosted Glass Alt-Tab Dock (macOS / Noir Glass OS style) */
XfwmTabwinWidget {{
    -XfwmTabwinWidget-icon-size: 64;
    -XfwmTabwinWidget-listview-icon-size: 32;
}}
#xfwm-tabwin {{
    background-color: rgba(14, 14, 18, 0.84);
    border: 1px solid {c['border_glass']};
    border-radius: {g['radius_window']}px;
    box-shadow: none;
    padding: 16px 20px 14px 20px;
    color: {c['text_primary']};
}}
#xfwm-tabwin button {{
    background-color: transparent;
    background-image: none;
    border: 1px solid transparent;
    border-radius: 12px;
    box-shadow: none;
    padding: 12px 14px;
    margin: 4px 6px;
    color: {c['text_secondary']};
    transition: background-color 120ms ease, border-color 120ms ease;
}}
#xfwm-tabwin button label {{
    background-color: transparent;
    color: {c['text_secondary']};
    font-size: 9pt;
    margin-top: 6px;
}}
#xfwm-tabwin button:hover {{
    background-color: rgba(228, 228, 234, 0.10);
    border-color: rgba(255, 255, 255, 0.16);
    color: #FFFFFF;
}}
#xfwm-tabwin button:selected,
#xfwm-tabwin button:checked,
#xfwm-tabwin button:focus {{
    background-color: rgba(228, 228, 234, 0.16);
    border: 1px solid {c['accent_border']};
    border-radius: 12px;
    color: #FFFFFF;
    outline: none;
}}
#xfwm-tabwin button:selected label,
#xfwm-tabwin button:checked label,
#xfwm-tabwin button:focus label,
#xfwm-tabwin button:hover label {{
    background-color: transparent;
    color: #FFFFFF;
    font-weight: 600;
}}
#xfwm-tabwin > box > label {{
    color: {c['text_primary']};
    font-weight: 600;
    font-size: 10pt;
    margin-top: 10px;
    padding: 2px 8px;
}}

/* Clean inner padding for xfce4-terminal (VTE3) */
vte-terminal {{
    padding: 12px 16px;
}}
""",
    )

    # 2. GTK4 / Libadwaita
    write(
        cfg / "gtk-4.0" / "settings.ini",
        f"""[Settings]
gtk-application-prefer-dark-theme=1
gtk-font-name={ty['sans']} {ty['ui_size']}
gtk-icon-theme-name={a['icon_theme']}
gtk-cursor-theme-name={a['cursor_theme']}
gtk-cursor-theme-size={a['cursor_size']}
""",
    )
    write(
        cfg / "gtk-4.0" / "gtk.css",
        f""":root {{
    --accent-color: {c['link']};
    --accent-bg-color: {c['selection_bg']};
    --accent-fg-color: {c['selection_fg']};
    --window-bg-color: {c['bg_surface']};
    --window-fg-color: {c['text_primary']};
    --view-bg-color: {c['bg_canvas']};
    --view-fg-color: {c['text_primary']};
    --headerbar-bg-color: {c['bg_surface']};
    --headerbar-fg-color: {c['text_primary']};
    --dialog-bg-color: #141418;
    --dialog-fg-color: {c['text_primary']};
    --card-bg-color: {c['bg_elevated']};
    --card-fg-color: {c['text_primary']};
    --popover-bg-color: #16161B;
    --popover-fg-color: {c['text_primary']};
}}

@define-color accent_color {c['link']};
@define-color accent_bg_color {c['selection_bg']};
@define-color accent_fg_color {c['selection_fg']};
@define-color window_bg_color {c['bg_surface']};
@define-color window_fg_color {c['text_primary']};
@define-color view_bg_color {c['bg_canvas']};
@define-color view_fg_color {c['text_primary']};
@define-color headerbar_bg_color {c['bg_surface']};
@define-color headerbar_fg_color {c['text_primary']};
@define-color dialog_bg_color #141418;
@define-color dialog_fg_color {c['text_primary']};
@define-color card_bg_color {c['bg_elevated']};
@define-color card_fg_color {c['text_primary']};
@define-color popover_bg_color #16161B;
@define-color popover_fg_color {c['text_primary']};

selection,
label selection,
entry selection,
textview text selection {{
    background-color: {c['selection_bg']};
    color: {c['selection_fg']};
}}

window.dialog,
window.messagedialog,
dialog,
alertdialog {{
    background-color: #141418;
    color: {c['text_primary']};
}}

/* Remove GTK4 CSD outer shadow buffer so the XFWM4 compositor renders unified shadow & 12px corners */
window.csd,
window.csd:backdrop {{
    box-shadow: none;
    margin: 0;
}}
""",
    )

    # 3. Qt5 / Qt6 Monochrome Palette (graphite selection #4A4E5E + crisp white text)
    qt_palette = f"""[ColorScheme]
active_colors=#fff3f3f5, #ff1a1a1f, #ff25252c, #ff1f1f25, #ff0b0b0d, #ff16161b, #fff3f3f5, #ffffffff, #fff3f3f5, #ff0b0b0d, #ff121215, #ff08080a, #ff4a4e5e, #ffffffff, #ffd8d8e2, #ffa6a6b0, #ff16161b, #ff000000, #ff1a1a1f, #fff3f3f5, #80f3f3f5
disabled_colors=#ff6e6e78, #ff16161b, #ff202026, #ff1a1a1f, #ff0b0b0d, #ff141418, #ff6e6e78, #ffffffff, #ff6e6e78, #ff0b0b0d, #ff121215, #ff08080a, #ff2a2a32, #ff6e6e78, #ff888892, #ff6e6e78, #ff141418, #ff000000, #ff1a1a1f, #ff6e6e78, #806e6e78
inactive_colors=#ffe0e0e6, #ff1a1a1f, #ff25252c, #ff1f1f25, #ff0b0b0d, #ff16161b, #ffe0e0e6, #ffffffff, #ffe0e0e6, #ff0b0b0d, #ff121215, #ff08080a, #ff323540, #fff3f3f5, #ffd8d8e2, #ffa6a6b0, #ff16161b, #ff000000, #ff1a1a1f, #fff3f3f5, #80f3f3f5
"""
    for qtver in ("qt5ct", "qt6ct"):
        write(cfg / qtver / "colors" / "noir-glass.conf", qt_palette)
        write(
            cfg / qtver / f"{qtver}.conf",
            f"""[Appearance]
color_scheme_path={home}/.config/{qtver}/colors/noir-glass.conf
custom_palette=true
icon_theme={a['icon_theme']}
style=Fusion

[Fonts]
fixed="{ty['mono']},{int(ty['mono_size'])},-1,5,50,0,0,0,0,0"
general="{ty['sans']},{ty['ui_size']},-1,5,50,0,0,0,0,0"
""",
        )

    # 4. Centered Dark-Glass Rofi Launcher + Power Menu (rendered natively via XFWM4 compositor)
    write(
        cfg / "rofi" / "config.rasi",
        f"""configuration {{
    modi: "drun,window";
    show-icons: true;
    icon-theme: "{a['icon_theme']}";
    font: "{ty['sans']} 10.5";
    drun-display-format: "{{name}}";
    display-drun: "Apps";
    display-window: "Windows";
    location: 0;
    disable-history: false;
    sidebar-mode: false;
    click-to-exit: true;
    hover-select: true;
    me-select-entry: "";
    me-accept-entry: "MousePrimary";
    kb-cancel: "Escape,Control+g,Control+bracketleft,Alt+F1";
}}
@theme "{home}/.config/rofi/noir-glass.rasi"
""",
    )
    write(
        cfg / "rofi" / "noir-glass.rasi",
        f"""* {{
    bg:          #0E1016D1;
    bg-alt:      #FFFFFF14;
    fg:          {c['text_primary']};
    fg-muted:    {c['text_secondary']};
    accent:      {c['selection_bg']};
    on-accent:   {c['selection_fg']};
    border-col:  #FFFFFF2E;
    border-sub:  #FFFFFF1A;
    background-color: transparent;
    text-color: @fg;
}}

window {{
    width: 640px;
    background-color: @bg;
    border: 1px;
    border-color: @border-col;
    border-radius: {g['radius_card']}px;
    padding: 18px;
}}

mainbox {{
    spacing: 14px;
    children: [ inputbar, listview ];
}}

inputbar {{
    background-color: @bg-alt;
    border: 1px;
    border-color: @border-sub;
    border-radius: 10px;
    padding: 10px 14px;
    spacing: 10px;
    children: [ prompt, entry ];
}}

prompt {{
    text-color: @fg-muted;
    font: "{ty['sans']} SemiBold 10";
}}

entry {{
    placeholder: "Search applications...";
    placeholder-color: #6E6E78;
    text-color: @fg;
}}

listview {{
    columns: 2;
    lines: 6;
    spacing: 6px;
    fixed-height: true;
    scrollbar: false;
    border: 0px;
}}

element {{
    padding: 10px 12px;
    spacing: 12px;
    border-radius: 10px;
    orientation: horizontal;
    background-color: transparent;
    text-color: @fg;
}}

element normal.normal,
element alternate.normal {{
    background-color: transparent;
    text-color: @fg;
}}

element normal.active,
element alternate.active {{
    background-color: @bg-alt;
    text-color: @fg;
}}

element selected.normal,
element selected.active {{
    background-color: @accent;
    text-color: @on-accent;
}}

element-icon {{
    size: 28px;
    vertical-align: 0.5;
    background-color: transparent;
}}

element-text {{
    vertical-align: 0.5;
    text-color: inherit;
    background-color: transparent;
}}
""",
    )
    write(
        cfg / "rofi" / "powermenu.sh",
        """#!/bin/sh
chosen=$(printf "Lock\\nSuspend\\nLog Out\\nReboot\\nShutdown" | rofi -dmenu -i -p "Power" -theme-str 'window { width: 320px; } listview { columns: 1; lines: 5; } entry { placeholder: "Select action..."; }')
case "$chosen" in
    "Lock")     dm-tool lock ;;
    "Suspend")  xfce4-session-logout --suspend ;;
    "Log Out")  xfce4-session-logout --logout --fast ;;
    "Reboot")   xfce4-session-logout --reboot --fast ;;
    "Shutdown") xfce4-session-logout --halt --fast ;;
esac
""",
        mode=0o755,
    )

    # 6. Dunst Frosted Monochrome Notifications + OSD
    write(
        cfg / "dunst" / "dunstrc",
        f"""[global]
    follow = mouse
    width = 340
    height = (0, 120)
    origin = top-right
    offset = (16, 54)
    notification_limit = 4
    indicate_hidden = yes
    sort = yes
    stack_duplicates = true
    hide_duplicate_count = false
    show_indicators = yes
    word_wrap = yes
    ellipsize = end
    show_age_threshold = 60
    progress_bar = true
    progress_bar_height = 6
    progress_bar_corner_radius = 4
    progress_bar_frame_width = 0
    padding = 14
    horizontal_padding = 16
    text_icon_padding = 14
    frame_width = 1
    frame_color = "#3A3A46"
    gap_size = 8
    separator_color = frame
    corner_radius = {g['radius_card']}
    font = {ty['sans']} 9.5
    line_height = 3
    format = "<b>%s</b>\\n%b"
    icon_theme = {a['icon_theme']}
    enable_recursive_icon_lookup = true
    max_icon_size = 36
    mouse_left_click = close_current
    mouse_right_click = close_all

[urgency_low]
    background = "#0E1016DD"
    foreground = "{c['text_secondary']}"
    highlight = "{c['accent']}"
    timeout = 4

[urgency_normal]
    background = "#0E1016E0"
    foreground = "{c['text_primary']}"
    highlight = "{c['accent']}"
    timeout = 5

[urgency_critical]
    background = "#1A1216DB"
    foreground = "{c['text_primary']}"
    frame_color = "{c['status_danger']}"
    highlight = "{c['status_danger']}"
    timeout = 0
""",
    )

    # 7. Starship Prompt + Fish Shell (Minimal Stealth Monochrome)
    write(
        cfg / "starship.toml",
        """add_newline = false
format = "$directory$git_branch$git_status$character"

[directory]
style = "bold #F3F3F5"
truncation_length = 3
truncate_to_repo = true

[git_branch]
symbol = " "
style = "#A6A6B0"
format = "[$symbol$branch]($style) "

[git_status]
style = "#E4E4EA"
format = "([$all_status$ahead_behind]($style) )"

[character]
success_symbol = "[❯](bold #E4E4EA) "
error_symbol = "[❯](bold #F27474) "
""",
    )
    write(
        cfg / "fish" / "config.fish",
        """set -g fish_greeting ""
fish_add_path ~/.local/bin
if status is-interactive
    command -q starship; and starship init fish | source
end
""",
    )

    # 8. Asymmetric Bento Glass HUD + Frameless Wide Audio Spectrum (Conky + Cava, 0 Picom)
    write(
        cfg / "cava" / "raw.conf",
        """[general]
framerate = 25
bars = 64
autosens = 1
sleep_timer = 3
lower_cutoff_freq = 40
higher_cutoff_freq = 14000

[input]
method = pipewire
source = auto

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 100
bar_delimiter = 59
frame_delimiter = 10

[smoothing]
monstercat = 1
waves = 0
noise_reduction = 70
""",
    )

    net_iface = detect_net_iface()
    write(
        cfg / "conky" / "card.lua",
        f"""require "cairo"
pcall(require, "cairo_xlib")

local NET_IFACE = "{net_iface}"
local HOME = "{home}"

-- Live default-route interface (tracks Wi-Fi <-> Ethernet switches; read from /proc, no forks)
local net_cache = {{ t = 0, v = NET_IFACE }}
local function get_net_iface()
    local now = os.time()
    if now - net_cache.t < 10 then return net_cache.v end
    net_cache.t = now
    local f = io.open("/proc/net/route", "r")
    if f then
        f:read("*l")
        for line in f:lines() do
            local iface, dest = line:match("^(%S+)%s+(%S+)")
            if dest == "00000000" then net_cache.v = iface; break end
        end
        f:close()
    end
    return net_cache.v
end

local N_BARS = 64
local peaks = {{}}
local last_vals = {{}}
for i = 1, N_BARS do peaks[i] = 0; last_vals[i] = 0 end

local CPU_PTS = 32
local cpu_hist = {{}}
for i = 1, CPU_PTS do cpu_hist[i] = 0 end

-- Lightweight cached shell pollers (avoids spawning processes every frame)
local cache = {{}}
local function cached_cmd(key, ttl, cmd, fallback)
    local now = os.time()
    local c = cache[key]
    if c and (now - c.t) < ttl then return c.v end
    local f = io.popen(cmd)
    local v = fallback
    if f then
        local s = f:read("*l")
        f:close()
        if s and #s > 0 then v = s end
    end
    cache[key] = {{ t = now, v = v }}
    return v
end

local function trim(s)
    return (s or ""):gsub("^%s+", ""):gsub("%s+$", "")
end

local function rounded_rect(cr, x, y, w, h, r)
    local pi = math.pi
    r = math.min(r, w / 2, h / 2)
    cairo_new_sub_path(cr)
    cairo_arc(cr, x + w - r, y + r, r, -pi/2, 0)
    cairo_arc(cr, x + w - r, y + h - r, r, 0, pi/2)
    cairo_arc(cr, x + r, y + h - r, r, pi/2, pi)
    cairo_arc(cr, x + r, y + r, r, pi, 3*pi/2)
    cairo_close_path(cr)
end

local function draw_bento_tile(cr, x, y, w, h, r)
    -- Soft feathered ambient shadow (floating depth without Picom)
    for _, s in ipairs({{{{4.5, 0.04}}, {{2.5, 0.07}}, {{1.2, 0.11}}}}) do
        rounded_rect(cr, x - s[1] * 0.4, y + s[1] * 0.75, w + s[1] * 0.8, h + s[1] * 0.5, r + s[1] * 0.4)
        cairo_set_source_rgba(cr, 0.0, 0.0, 0.0, s[2])
        cairo_fill(cr)
    end

    -- Airy cool-obsidian translucent glass fill (unified layer 0 below 78% panels / 82% menus)
    rounded_rect(cr, x, y, w, h, r)
    local bg = cairo_pattern_create_linear(x, y, x + w * 0.25, y + h)
    cairo_pattern_add_color_stop_rgba(bg, 0.0, 0.047, 0.055, 0.078, 0.36)
    cairo_pattern_add_color_stop_rgba(bg, 1.0, 0.031, 0.039, 0.062, 0.48)
    cairo_set_source(cr, bg)
    cairo_fill_preserve(cr)
    cairo_pattern_destroy(bg)

    -- Subtle upper glass sheen
    cairo_save(cr)
    cairo_clip_preserve(cr)
    local sheen = cairo_pattern_create_linear(x, y, x, y + h * 0.45)
    cairo_pattern_add_color_stop_rgba(sheen, 0.0, 1.0, 1.0, 1.0, 0.075)
    cairo_pattern_add_color_stop_rgba(sheen, 1.0, 1.0, 1.0, 1.0, 0.0)
    cairo_set_source(cr, sheen)
    cairo_rectangle(cr, x, y, w, h * 0.45)
    cairo_fill(cr)
    cairo_pattern_destroy(sheen)
    cairo_restore(cr)

    -- Crisp directional specular rim border
    local rim = cairo_pattern_create_linear(x, y, x, y + h)
    cairo_pattern_add_color_stop_rgba(rim, 0.0, 1.0, 1.0, 1.0, 0.28)
    cairo_pattern_add_color_stop_rgba(rim, 0.45, 1.0, 1.0, 1.0, 0.12)
    cairo_pattern_add_color_stop_rgba(rim, 1.0, 1.0, 1.0, 1.0, 0.07)
    cairo_set_source(cr, rim)
    cairo_set_line_width(cr, 1.0)
    cairo_stroke(cr)
    cairo_pattern_destroy(rim)
end

local function draw_text(cr, x, y, text, size, bold, r, g, b, a, align)
    cairo_select_font_face(cr, "Inter", CAIRO_FONT_SLANT_NORMAL, bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(cr, size)
    local ext = cairo_text_extents_t:create()
    cairo_text_extents(cr, text, ext)
    local tx = x
    if align == "right" then
        tx = x - ext.width - ext.x_bearing
    elseif align == "center" then
        tx = x - (ext.width / 2) - ext.x_bearing
    end
    -- Micro dark legibility shadow for ultra-transparent glass over bright clouds
    cairo_move_to(cr, tx, y + 1.0)
    cairo_set_source_rgba(cr, 0.0, 0.0, 0.0, math.min(0.55, a * 0.65))
    cairo_show_text(cr, text)
    cairo_move_to(cr, tx, y)
    cairo_set_source_rgba(cr, r, g, b, a)
    cairo_show_text(cr, text)
    return ext.width
end

local function draw_pill_bar(cr, x, y, w, h, pct, r1, g1, b1)
    pct = math.max(0, math.min(100, pct or 0))
    local rad = h / 2
    rounded_rect(cr, x, y, w, h, rad)
    cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.12)
    cairo_fill(cr)
    local fw = (pct / 100.0) * w
    if fw > 0.5 then
        rounded_rect(cr, x, y, math.max(h, fw), h, rad)
        cairo_set_source_rgba(cr, r1 or 0.94, g1 or 0.95, b1 or 0.98, 0.92)
        cairo_fill(cr)
    end
end

local function draw_arc_gauge(cr, cx, cy, rad, lw, pct, r, g, b, a)
    local a0 = math.rad(135)
    local span = math.rad(270)
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND)
    cairo_set_line_width(cr, lw)
    cairo_new_path(cr)
    cairo_arc(cr, cx, cy, rad, a0, a0 + span)
    cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.12)
    cairo_stroke(cr)

    local p = math.max(0.02, math.min(1.0, (pct or 0) / 100.0))
    cairo_new_path(cr)
    cairo_arc(cr, cx, cy, rad, a0, a0 + span * p)
    cairo_set_source_rgba(cr, r, g, b, a)
    cairo_stroke(cr)
end

function conky_draw_bento_hud()
    if conky_window == nil then return end
    local cs = cairo_xlib_surface_create(conky_window.display, conky_window.drawable, conky_window.visual, conky_window.width, conky_window.height)
    local cr = cairo_create(cs)

    local cpu = tonumber(conky_parse("${{cpu cpu0}}")) or 0
    local mem_pct = tonumber(conky_parse("${{memperc}}")) or 0
    local dsk_pct = tonumber(conky_parse("${{fs_used_perc /}}")) or 0
    local mem_used = trim(conky_parse("${{mem}}")):gsub("iB", ""):gsub("B$", "")
    local mem_max  = trim(conky_parse("${{memmax}}")):gsub("iB", ""):gsub("B$", "")
    local dsk_used = trim(conky_parse("${{fs_used /}}")):gsub("iB", "")
    local dsk_max  = trim(conky_parse("${{fs_size /}}")):gsub("iB", "")
    local up_short = trim(conky_parse("${{uptime_short}}"))
    local net_dn   = trim(conky_parse("${{downspeed " .. get_net_iface() .. "}}")):gsub("iB", "")
    local net_up   = trim(conky_parse("${{upspeed " .. get_net_iface() .. "}}")):gsub("iB", "")

    local temp = cached_cmd("temp", 4, HOME .. "/.config/conky/cpu_temp.sh", "--")
    local gpu  = cached_cmd("gpu", 5, HOME .. "/.config/conky/gpu_status.sh", "NVIDIA D3")
    local temp_num = temp:gsub("°C", ""):gsub("[^0-9%-]", "")
    if #temp_num == 0 then temp_num = "--" end

    table.remove(cpu_hist, 1)
    cpu_hist[CPU_PTS] = math.max(0, math.min(100, cpu))

    -- =================================================================
    -- TILE 1: HERO DUAL-RING GAUGE (Top-Left of Bento, 176 x 174)
    -- =================================================================
    local t1x, t1y, t1w, t1h = 12, 12, 176, 174
    draw_bento_tile(cr, t1x, t1y, t1w, t1h, 20)
    draw_text(cr, t1x + 16, t1y + 25, "PULSE", 10.5, true, 1, 1, 1, 0.58, "left")
    draw_text(cr, t1x + t1w - 16, t1y + 25, up_short, 10.5, false, 1, 1, 1, 0.66, "right")

    local cx, cy = t1x + t1w / 2, t1y + 98
    draw_arc_gauge(cr, cx, cy, 47, 6.2, cpu, 0.96, 0.97, 1.00, 0.95)
    draw_arc_gauge(cr, cx, cy, 36, 4.6, mem_pct, 0.66, 0.72, 0.84, 0.88)

    draw_text(cr, cx, cy + 9, temp_num .. "°", 27.0, true, 1, 1, 1, 0.97, "center")
    draw_text(cr, cx, cy + 25, "TEMP", 9.0, true, 1, 1, 1, 0.50, "center")

    -- Clean bottom micro-legend (safe clearance even at 100%)
    cairo_arc(cr, t1x + 16, t1y + 156, 2.8, 0, 2 * math.pi)
    cairo_set_source_rgba(cr, 0.96, 0.97, 1.00, 0.95); cairo_fill(cr)
    draw_text(cr, t1x + 24, t1y + 160, string.format("CPU %d%%", cpu), 10.5, false, 1, 1, 1, 0.86, "left")

    cairo_arc(cr, t1x + 98, t1y + 156, 2.8, 0, 2 * math.pi)
    cairo_set_source_rgba(cr, 0.66, 0.72, 0.84, 0.90); cairo_fill(cr)
    draw_text(cr, t1x + 106, t1y + 160, string.format("MEM %d%%", mem_pct), 10.5, false, 1, 1, 1, 0.76, "left")

    -- =================================================================
    -- TILE 2: MEMORY & STORAGE (Top-Right Upper, 208 x 81)
    -- =================================================================
    local t2x, t2y, t2w, t2h = 200, 12, 208, 81
    draw_bento_tile(cr, t2x, t2y, t2w, t2h, 18)
    draw_text(cr, t2x + 16, t2y + 25, "RAM", 10.0, true, 1, 1, 1, 0.58, "left")
    draw_text(cr, t2x + t2w - 16, t2y + 25, mem_used .. " / " .. mem_max, 11.5, false, 1, 1, 1, 0.92, "right")
    draw_pill_bar(cr, t2x + 16, t2y + 33, t2w - 32, 4.6, mem_pct, 0.72, 0.78, 0.90)

    draw_text(cr, t2x + 16, t2y + 60, "DISK", 10.0, true, 1, 1, 1, 0.58, "left")
    draw_text(cr, t2x + t2w - 16, t2y + 60, dsk_used .. " / " .. dsk_max, 11.5, false, 1, 1, 1, 0.92, "right")
    draw_pill_bar(cr, t2x + 16, t2y + 68, t2w - 32, 4.6, dsk_pct, 0.94, 0.95, 0.98)

    -- =================================================================
    -- TILE 3: GPU & NETWORK (Top-Right Lower, 208 x 81)
    -- =================================================================
    local t3x, t3y, t3w, t3h = 200, 105, 208, 81
    draw_bento_tile(cr, t3x, t3y, t3w, t3h, 18)
    local is_sleep = not (gpu:find("%d+%%") or gpu:find("Active"))
    cairo_arc(cr, t3x + 20, t3y + 25, 3.6, 0, 2 * math.pi)
    if is_sleep then
        cairo_set_source_rgba(cr, 0.52, 0.84, 0.66, 0.90)
    else
        cairo_set_source_rgba(cr, 0.98, 0.80, 0.48, 0.95)
    end
    cairo_fill(cr)
    draw_text(cr, t3x + 30, t3y + 29, "GPU", 10.0, true, 1, 1, 1, 0.58, "left")
    local gpu_short = gpu:gsub("NVIDIA ", ""):gsub("Sleeping %(D3%)", "D3 SLEEP"):gsub("Idle", "IDLE")
    draw_text(cr, t3x + t3w - 16, t3y + 29, gpu_short, 11.5, true, 1, 1, 1, 0.94, "right")

    -- Subtle inner hairline
    cairo_set_source_rgba(cr, 1, 1, 1, 0.10)
    cairo_set_line_width(cr, 0.9)
    cairo_move_to(cr, t3x + 16, t3y + 43); cairo_line_to(cr, t3x + t3w - 16, t3y + 43); cairo_stroke(cr)

    -- Vector down/up arrows + speeds
    local ny = t3y + 65
    cairo_set_line_width(cr, 1.4); cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.66)
    cairo_move_to(cr, t3x + 20, ny - 8); cairo_line_to(cr, t3x + 20, ny - 1.5)
    cairo_move_to(cr, t3x + 17, ny - 4.5); cairo_line_to(cr, t3x + 20, ny - 1.5); cairo_line_to(cr, t3x + 23, ny - 4.5)
    cairo_stroke(cr)
    draw_text(cr, t3x + 29, ny, net_dn, 11.5, false, 1, 1, 1, 0.90, "left")

    local ux = t3x + 116
    cairo_set_source_rgba(cr, 1, 1, 1, 0.54)
    cairo_move_to(cr, ux, ny - 1.5); cairo_line_to(cr, ux, ny - 8)
    cairo_move_to(cr, ux - 3, ny - 4.5); cairo_line_to(cr, ux, ny - 8); cairo_line_to(cr, ux + 3, ny - 4.5)
    cairo_stroke(cr)
    draw_text(cr, ux + 9, ny, net_up, 11.5, false, 1, 1, 1, 0.74, "left")

    -- =================================================================
    -- TILE 4: WIDE BOTTOM STRIP — CPU WAVEFORM + TOP PROCESSES (396 x 126)
    -- =================================================================
    local t4x, t4y, t4w, t4h = 12, 198, 396, 126
    draw_bento_tile(cr, t4x, t4y, t4w, t4h, 20)

    -- Left: smooth frameless CPU area waveform
    draw_text(cr, t4x + 18, t4y + 26, "CPU WAVE", 10.0, true, 1, 1, 1, 0.58, "left")
    draw_text(cr, t4x + 198, t4y + 26, string.format("%d%%", cpu), 12.5, true, 1, 1, 1, 0.95, "right")

    local gx, gy, gw, gh = t4x + 18, t4y + 40, 180, 68
    local step = gw / (CPU_PTS - 1)
    local base = gy + gh
    local span = gh - 6
    local vmax = 25
    for i = 1, CPU_PTS do if cpu_hist[i] > vmax then vmax = cpu_hist[i] end end

    -- Subtle baseline
    cairo_set_source_rgba(cr, 1, 1, 1, 0.10)
    cairo_set_line_width(cr, 0.8)
    cairo_move_to(cr, gx, base); cairo_line_to(cr, gx + gw, base); cairo_stroke(cr)

    -- Area gradient fill
    cairo_new_path(cr)
    cairo_move_to(cr, gx, base)
    for i = 1, CPU_PTS do
        local px = gx + (i - 1) * step
        local py = base - (cpu_hist[i] / vmax) * span
        cairo_line_to(cr, px, py)
    end
    cairo_line_to(cr, gx + gw, base)
    cairo_close_path(cr)
    local area = cairo_pattern_create_linear(gx, gy, gx, base)
    cairo_pattern_add_color_stop_rgba(area, 0.0, 0.94, 0.96, 1.0, 0.32)
    cairo_pattern_add_color_stop_rgba(area, 1.0, 0.94, 0.96, 1.0, 0.00)
    cairo_set_source(cr, area)
    cairo_fill(cr)
    cairo_pattern_destroy(area)

    -- Crisp wave stroke
    cairo_new_path(cr)
    for i = 1, CPU_PTS do
        local px = gx + (i - 1) * step
        local py = base - (cpu_hist[i] / vmax) * span
        if i == 1 then cairo_move_to(cr, px, py) else cairo_line_to(cr, px, py) end
    end
    cairo_set_source_rgba(cr, 0.96, 0.97, 1.0, 0.95)
    cairo_set_line_width(cr, 1.8)
    cairo_stroke(cr)

    -- Glowing live endpoint dot
    local lx, ly = gx + gw, base - (cpu_hist[CPU_PTS] / vmax) * span
    cairo_arc(cr, lx, ly, 5.2, 0, 2 * math.pi)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.24); cairo_fill(cr)
    cairo_arc(cr, lx, ly, 2.6, 0, 2 * math.pi)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.98); cairo_fill(cr)

    -- Vertical subtle divider
    cairo_set_source_rgba(cr, 1, 1, 1, 0.11)
    cairo_set_line_width(cr, 0.9)
    cairo_move_to(cr, t4x + 214, t4y + 16); cairo_line_to(cr, t4x + 214, t4y + t4h - 16); cairo_stroke(cr)

    -- Right: Top 3 compact processes
    draw_text(cr, t4x + 230, t4y + 26, "TOP", 10.0, true, 1, 1, 1, 0.58, "left")
    draw_text(cr, t4x + t4w - 18, t4y + 26, "CPU", 10.0, true, 1, 1, 1, 0.46, "right")
    for i = 1, 3 do
        local pname = trim(conky_parse("${{top name " .. i .. "}}")):sub(1, 13)
        local pcpu  = trim(conky_parse("${{top cpu " .. i .. "}}")) .. "%"
        local ry = t4y + 32 + i * 24
        draw_text(cr, t4x + 230, ry, pname, 11.5, false, 1, 1, 1, i == 1 and 0.94 or 0.76, "left")
        draw_text(cr, t4x + t4w - 18, ry, pcpu, 11.0, false, 1, 1, 1, i == 1 and 0.90 or 0.60, "right")
    end

    cairo_destroy(cr)
    cairo_surface_destroy(cs)
end

-- Exact two-tone white-monochrome official fastfetch Void Linux ASCII art
-- (c=1 soft translucent white crescents, c=2 crisp luminous white 'void' wordmark)
local VOID_ASCII = {{
    {{{{1, "                __.;=====;.__"}}}},
    {{{{1, "            _.=+==++=++=+=+===;."}}}},
    {{{{1, "             -=+++=+===+=+=+++++=_"}}}},
    {{{{1, "        .     -=:``     `--==+=++==."}}}},
    {{{{1, "       _vi,    `            --+=++++:"}}}},
    {{{{1, "      .uvnvi.       _._       -==+==+."}}}},
    {{{{1, "     .vvnvnI`    .;==|==;.     :|=||=|."}}}},
    {{{{2, "+QmQQm"}}, {{1, "pvvnv;"}}, {{2, " _yYsyQQWUUQQQm #QmQ#"}}, {{1, ":"}}, {{2, "QQQWUV$QQm."}}}},
    {{{{2, " -QQWQW"}}, {{1, "pvvo"}}, {{2, "wZ?.wQQQE"}}, {{1, "==<"}}, {{2, "QWWQ/QWQW.QQWW"}}, {{1, "(: "}}, {{2, "jQWQE"}}}},
    {{{{2, "  -$QQQQmmU'  jQQQ"}}, {{1, "@+=<"}}, {{2, "QWQQ)mQQQ.mQQQC"}}, {{1, "+;"}}, {{2, "jWQQ@'"}}}},
    {{{{2, "   -$WQ8Y"}}, {{1, "nI:"}}, {{2, "   QWQQwgQQWV"}}, {{1, "`"}}, {{2, "mWQQ.jQWQQgyyWW@!"}}}},
    {{{{1, "     -1vvnvv.     `~+++`        ++|+++"}}}},
    {{{{1, "      +vnvnnv,                 `-|==="}}}},
    {{{{1, "       +vnvnvns.           .      :=-"}}}},
    {{{{1, "        -Invnvvnsi..___..=sv=.     `"}}}},
    {{{{1, "          +Invnvnvnnnnnnnnvvnn;."}}}},
    {{{{1, "            ~|Invnvnvvnvvvnnv}}+" .. "`"}}}},
    {{{{1, "               -~|{{*l}}*|~"}}}},
}}

function conky_draw_void_identity()
    if conky_window == nil then return end
    local cs = cairo_xlib_surface_create(conky_window.display, conky_window.drawable, conky_window.visual, conky_window.width, conky_window.height)
    local cr = cairo_create(cs)

    cairo_select_font_face(cr, "Fira Code", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD)
    cairo_set_font_size(cr, 13.0)
    local ext_ch = cairo_text_extents_t:create()
    cairo_text_extents(cr, "M", ext_ch)
    local cw_mono = ext_ch.x_advance
    local ox, oy, lh = 2, 14, 14.5

    for row, segs in ipairs(VOID_ASCII) do
        local x = ox
        local y = oy + (row - 1) * lh
        for _, seg in ipairs(segs) do
            local col, txt = seg[1], seg[2]
            -- Crisp shadow keeps pure-white ASCII legible even over bright clouds
            cairo_move_to(cr, x, y + 1.5)
            cairo_set_source_rgba(cr, 0, 0, 0, 0.62)
            cairo_show_text(cr, txt)
            cairo_move_to(cr, x, y)
            if col == 1 then
                cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.76)
            else
                cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.98)
            end
            cairo_show_text(cr, txt)
            x = x + #txt * cw_mono
        end
    end

    cairo_destroy(cr)
    cairo_surface_destroy(cs)
end

function conky_draw_spectrum()
    if conky_window == nil then return end
    local cs = cairo_xlib_surface_create(conky_window.display, conky_window.drawable, conky_window.visual, conky_window.width, conky_window.height)
    local cr = cairo_create(cs)
    local cw, ch = conky_window.width, conky_window.height

    -- Read 64-band Cava frame
    local f = io.open("/dev/shm/cava_bars", "r")
    if f then
        local line = f:read("*l")
        f:close()
        if line and #line > 0 then
            local idx = 0
            for num in string.gmatch(line, "%d+") do
                idx = idx + 1
                if idx <= N_BARS then last_vals[idx] = tonumber(num) or 0 end
            end
        end
    end

    -- Floating compact glass media pill ONLY when playing/paused (zero dead box when idle!)
    local status = cached_cmd("mstat", 2, HOME .. "/.config/conky/music_info.sh status", "IDLE")
    if status == "PLAYING" or status == "PAUSED" then
        local track = cached_cmd("mtrack", 2, HOME .. "/.config/conky/music_info.sh line", "")
        if #track > 0 then
            cairo_select_font_face(cr, "Inter", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD)
            cairo_set_font_size(cr, 10.0)
            local ext = cairo_text_extents_t:create()
            cairo_text_extents(cr, track, ext)
            local pw = math.min(cw - 16, ext.width + 40)
            draw_bento_tile(cr, 6, 6, pw, 26, 13)
            -- Vector play/pause glyph
            cairo_set_source_rgba(cr, 1, 1, 1, 0.90)
            if status == "PLAYING" then
                cairo_move_to(cr, 18, 14.5); cairo_line_to(cr, 25, 19.0); cairo_line_to(cr, 18, 23.5); cairo_close_path(cr); cairo_fill(cr)
            else
                cairo_rectangle(cr, 18, 14.5, 2.2, 9); cairo_rectangle(cr, 22, 14.5, 2.2, 9); cairo_fill(cr)
            end
            draw_text(cr, 32, 22.5, track, 10.0, true, 1, 1, 1, 0.92, "left")
        end
    end

    -- Frameless 64-bar wide mirrored audio equalizer (no box!)
    local pad_x, gap = 6, 5.5
    local area_w = cw - pad_x * 2
    local base_y, max_h = ch - 26, 68
    local bar_w = (area_w - gap * (N_BARS - 1)) / N_BARS

    -- Tapered luminous horizon hairline
    local hline = cairo_pattern_create_linear(pad_x, base_y, cw - pad_x, base_y)
    cairo_pattern_add_color_stop_rgba(hline, 0.0, 1, 1, 1, 0.0)
    cairo_pattern_add_color_stop_rgba(hline, 0.08, 1, 1, 1, 0.22)
    cairo_pattern_add_color_stop_rgba(hline, 0.92, 1, 1, 1, 0.22)
    cairo_pattern_add_color_stop_rgba(hline, 1.0, 1, 1, 1, 0.0)
    cairo_set_source(cr, hline)
    cairo_set_line_width(cr, 1.0)
    cairo_move_to(cr, pad_x, base_y + 1.5); cairo_line_to(cr, cw - pad_x, base_y + 1.5); cairo_stroke(cr)
    cairo_pattern_destroy(hline)

    for i = 1, N_BARS do
        local v = math.min(100, math.max(0, last_vals[i] or 0))
        local bh = (v > 0) and math.max(3.5, (v / 100.0) * max_h) or 2.5
        if bh > peaks[i] then peaks[i] = bh else peaks[i] = math.max(2.5, peaks[i] - 1.5) end
        local bx = pad_x + (i - 1) * (bar_w + gap)
        local by = base_y - bh

        -- Primary upward bar
        local pat = cairo_pattern_create_linear(bx, base_y, bx, base_y - max_h)
        if v > 0 then
            cairo_pattern_add_color_stop_rgba(pat, 0.0, 0.72, 0.76, 0.86, 0.45)
            cairo_pattern_add_color_stop_rgba(pat, 0.5, 0.92, 0.94, 0.98, 0.82)
            cairo_pattern_add_color_stop_rgba(pat, 1.0, 1.00, 1.00, 1.00, 0.96)
        else
            cairo_pattern_add_color_stop_rgba(pat, 0.0, 1, 1, 1, 0.26)
            cairo_pattern_add_color_stop_rgba(pat, 1.0, 1, 1, 1, 0.26)
        end
        cairo_set_source(cr, pat)
        rounded_rect(cr, bx, by, bar_w, bh, math.min(bar_w / 2, bh / 2))
        cairo_fill(cr)
        cairo_pattern_destroy(pat)

        -- Subtle mirrored reflection below horizon
        if bh > 3.5 then
            local rh = math.min(18, bh * 0.28)
            local ref = cairo_pattern_create_linear(bx, base_y + 3, bx, base_y + 3 + rh)
            cairo_pattern_add_color_stop_rgba(ref, 0.0, 0.90, 0.93, 0.98, 0.22)
            cairo_pattern_add_color_stop_rgba(ref, 1.0, 0.90, 0.93, 0.98, 0.00)
            cairo_set_source(cr, ref)
            rounded_rect(cr, bx, base_y + 3, bar_w, rh, math.min(bar_w / 2, rh / 2))
            cairo_fill(cr)
            cairo_pattern_destroy(ref)
        end

        -- Floating gravity peak cap
        if peaks[i] > 5.0 then
            cairo_set_source_rgba(cr, 1, 1, 1, 0.88)
            rounded_rect(cr, bx, base_y - peaks[i] - 3.5, bar_w, 1.6, 0.8)
            cairo_fill(cr)
        end
    end

    cairo_destroy(cr)
    cairo_surface_destroy(cs)
end
""",
    )

    write(
        cfg / "conky" / "telemetry.conf",
        f"""conky.config = {{
    alignment = "bottom_right",
    background = true,
    double_buffer = true,
    update_interval = 2.0,
    use_xft = true,
    font = "{ty['sans']}:size=8",
    border_inner_margin = 0,
    border_outer_margin = 0,
    gap_x = 4,
    gap_y = 6,
    minimum_width = 420,
    maximum_width = 420,
    minimum_height = 336,
    own_window = true,
    own_window_type = "desktop",
    own_window_class = "Conky",
    own_window_transparent = true,
    own_window_argb_visual = true,
    own_window_argb_value = 0,
    own_window_hints = "undecorated,below,sticky,skip_taskbar,skip_pager",
    draw_shades = false,
    draw_outline = false,
    draw_borders = false,
    lua_load = "{home}/.config/conky/card.lua",
    lua_draw_hook_pre = "draw_bento_hud",
}};

conky.text = [[]];
""",
    )

    write(
        cfg / "conky" / "void_ascii.conf",
        f"""conky.config = {{
    alignment = "top_left",
    background = true,
    double_buffer = true,
    update_interval = 3600.0,
    use_xft = true,
    font = "{ty['mono']}:size=8",
    border_inner_margin = 0,
    border_outer_margin = 0,
    gap_x = 14,
    gap_y = 58,
    minimum_width = 390,
    maximum_width = 390,
    minimum_height = 274,
    own_window = true,
    own_window_type = "desktop",
    own_window_class = "Conky",
    own_window_transparent = true,
    own_window_argb_visual = true,
    own_window_argb_value = 0,
    own_window_hints = "undecorated,below,sticky,skip_taskbar,skip_pager",
    draw_shades = false,
    draw_outline = false,
    draw_borders = false,
    lua_load = "{home}/.config/conky/card.lua",
    lua_draw_hook_pre = "draw_void_identity",
}};

conky.text = [[]];
""",
    )

    write(
        cfg / "conky" / "spectrum.conf",
        f"""conky.config = {{
    alignment = "bottom_left",
    background = true,
    double_buffer = true,
    update_interval = 0.05,
    use_xft = true,
    font = "{ty['sans']}:size=8",
    border_inner_margin = 0,
    border_outer_margin = 0,
    gap_x = 10,
    gap_y = 18,
    minimum_width = 680,
    maximum_width = 680,
    minimum_height = 128,
    own_window = true,
    own_window_type = "desktop",
    own_window_class = "Conky",
    own_window_transparent = true,
    own_window_argb_visual = true,
    own_window_argb_value = 0,
    own_window_hints = "undecorated,below,sticky,skip_taskbar,skip_pager",
    draw_shades = false,
    draw_outline = false,
    draw_borders = false,
    lua_load = "{home}/.config/conky/card.lua",
    lua_draw_hook_pre = "draw_spectrum",
}};

conky.text = [[]];
""",
    )

    write(
        cfg / "conky" / "gpu_status.sh",
        """#!/bin/sh
# GPU status. A discrete NVIDIA GPU in D3cold is never woken up just to be polled.
NV_DEV=""
for d in /sys/bus/pci/devices/*; do
    [ "$(cat "$d/vendor" 2>/dev/null)" = "0x10de" ] || continue
    case "$(cat "$d/class" 2>/dev/null)" in
        0x030000|0x030200) NV_DEV="$d"; break ;;
    esac
done
if [ -z "$NV_DEV" ]; then
    for d in /sys/bus/pci/devices/*; do
        case "$(cat "$d/class" 2>/dev/null)" in 0x03*) ;; *) continue ;; esac
        case "$(cat "$d/vendor" 2>/dev/null)" in
            0x8086) echo "Intel iGPU"; exit 0 ;;
            0x1002) echo "AMD GPU"; exit 0 ;;
        esac
    done
    echo "Integrated GPU"; exit 0
fi
[ "$(cat "$NV_DEV/power/runtime_status" 2>/dev/null)" = "suspended" ] && { echo "NVIDIA Sleeping (D3)"; exit 0; }
if command -v lsof >/dev/null 2>&1; then
    busy=$(lsof -t /dev/nvidia0 /dev/dri/renderD129 2>/dev/null | xargs -r ps -o comm= -p 2>/dev/null | grep -vE '^(Xorg|nvidia-smi)$' | head -n1)
    [ -z "$busy" ] && { echo "NVIDIA Idle"; exit 0; }
fi
out=$(nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null | head -n1)
if [ -n "$out" ]; then
    u=$(echo "$out" | cut -d, -f1 | tr -d " ")
    t=$(echo "$out" | cut -d, -f2 | tr -d " ")
    m=$(echo "$out" | cut -d, -f3 | tr -d " ")
    if [ "${m:-0}" -ge 1000 ] 2>/dev/null; then
        ms=$(awk -v m="$m" 'BEGIN{printf "%.1fG", m/1024}')
    else
        ms="${m}M"
    fi
    echo "NVIDIA ${u}% · ${t}° · ${ms}"
else
    echo "NVIDIA Active"
fi
""",
        mode=0o755,
    )
    write(
        cfg / "conky" / "cpu_temp.sh",
        """#!/bin/sh
# CPU package temperature: Intel (x86_pkg_temp / coretemp), AMD (k10temp / zenpower), generic fallback
for z in /sys/class/thermal/thermal_zone*; do
    [ "$(cat "$z/type" 2>/dev/null)" = "x86_pkg_temp" ] && { awk '{printf "%.0f°C", $1/1000}' "$z/temp"; exit 0; }
done
for h in /sys/class/hwmon/hwmon*; do
    case "$(cat "$h/name" 2>/dev/null)" in
        coretemp|k10temp|zenpower) [ -f "$h/temp1_input" ] && { awk '{printf "%.0f°C", $1/1000}' "$h/temp1_input"; exit 0; } ;;
    esac
done
[ -r /sys/class/thermal/thermal_zone0/temp ] && { awk '{printf "%.0f°C", $1/1000}' /sys/class/thermal/thermal_zone0/temp; exit 0; }
echo "--°C"
""",
        mode=0o755,
    )
    write(
        cfg / "conky" / "music_info.sh",
        """#!/bin/sh
st=$(playerctl status 2>/dev/null)
if [ "$1" = "status" ]; then
    case "$st" in
        Playing) echo "PLAYING" ;;
        Paused)  echo "PAUSED" ;;
        *)       echo "IDLE" ;;
    esac
    exit 0
fi
[ -z "$st" ] && { echo "Audio Spectrum"; exit 0; }
trunc() {
    awk -v n="$2" '{ if (length($0) > n) printf "%s…", substr($0, 1, n - 1); else printf "%s", $0 }' <<EOF
$1
EOF
}
raw_title=$(playerctl metadata title 2>/dev/null)
raw_artist=$(playerctl metadata artist 2>/dev/null | sed 's/ - Topic$//')
title=$(trunc "$raw_title" 42)
artist=$(trunc "$raw_artist" 24)
if [ -n "$title" ] && [ -n "$artist" ]; then
    printf '%s  ·  %s\\n' "$title" "$artist"
elif [ -n "$title" ]; then
    printf '%s\\n' "$title"
else
    echo "Audio Spectrum"
fi
""",
        mode=0o755,
    )
    write(
        cfg / "conky" / "cava_feeder.sh",
        """#!/bin/sh
# Zero-Python, zero-fork-per-frame Cava ASCII pipe into tmpfs
RAW_CONF="$HOME/.config/cava/raw.conf"
DST="/dev/shm/cava_bars"
printf '0\\n' > "$DST"

while true; do
    cava -p "$RAW_CONF" 2>/dev/null | while IFS= read -r line; do
        [ -n "$line" ] && printf '%s\\n' "$line" > "$DST"
    done
    sleep 2
done
""",
        mode=0o755,
    )
    write(
        cfg / "conky" / "start.sh",
        f"""#!/bin/sh
export XDG_RUNTIME_DIR="${{XDG_RUNTIME_DIR:-/run/user/$(id -u)}}"
pkill -u "$(id -u)" -x conky 2>/dev/null || true
pkill -u "$(id -u)" -f '[c]ava_feeder.sh' 2>/dev/null || true
pkill -u "$(id -u)" -x cava 2>/dev/null || true
sleep 0.3
nohup {home}/.config/conky/cava_feeder.sh >/dev/null 2>&1 </dev/null &
sleep 0.2
conky -q -c {home}/.config/conky/telemetry.conf  >/dev/null 2>&1 </dev/null &
conky -q -c {home}/.config/conky/void_ascii.conf >/dev/null 2>&1 </dev/null &
conky -q -c {home}/.config/conky/spectrum.conf   >/dev/null 2>&1 </dev/null &
""",
        mode=0o755,
    )

    # 8. Firefox: leave Firefox's own built-in theme untouched (clean up any legacy CSS overlays)
    ff_globs = (
        glob.glob(str(home / ".config" / "mozilla" / "firefox" / "*.*"))
        + glob.glob(str(home / ".mozilla" / "firefox" / "*.*"))
    )
    for prof in ff_globs:
        p = Path(prof)
        if p.is_dir():
            for rel in ("chrome/userChrome.css", "chrome/userContent.css", "user.js"):
                target = p / rel
                if target.exists():
                    target.unlink()

    # 11. XFCE Default Helpers, Docklike Pins & Session Environment
    write(
        cfg / "xfce4" / "panel" / "docklike-2.rc",
        f"""[user]
pinned=thunar;xfce4-terminal;firefox;
inactiveIndicatorStyle=1
forceIconSize=true
iconSize={g['dock_icon_size']}
""",
    )
    write(
        cfg / "xfce4" / "panel" / "launcher-10" / "power-menu.desktop",
        f"""[Desktop Entry]
Name=Power
Comment=Log Out, Suspend, Reboot, Shutdown
Exec={home}/.config/rofi/powermenu.sh
Icon=system-shutdown-symbolic
Terminal=false
Type=Application
""",
    )
    write(
        cfg / "xfce4" / "helpers.rc",
        "TerminalEmulator=xfce4-terminal\nWebBrowser=firefox\nFileManager=thunar\n",
    )
    write(
        home / ".xprofile",
        "export QT_QPA_PLATFORMTHEME=qt5ct\nexport XCURSOR_THEME=Bibata-Modern-Classic\nexport XCURSOR_SIZE=22\nexport NO_AT_BRIDGE=1\n",
    )
    write(
        home / ".local" / "bin" / "wifi-status.sh",
        f"""#!/bin/sh
# Passive network status for xfce4-genmon: sysfs + nl80211 reads only. It never scans and
# never talks to NetworkManager, so polling it cannot disturb the radio or add latency.
ip4() {{ ip -4 -o addr show dev "$1" 2>/dev/null | awk '{{split($4, a, "/"); print a[1]; exit}}'; }}

ETH="" WDEV=""
for d in /sys/class/net/*; do
    n=${{d##*/}}
    [ "$n" = lo ] && continue
    if [ -d "$d/wireless" ] || [ -d "$d/phy80211" ]; then
        WDEV=$n
    elif [ "$(cat "$d/operstate" 2>/dev/null)" = up ]; then
        case "$n" in en*|eth*) ETH=$n ;; esac
    fi
done

BLOCKED=0
for r in /sys/class/rfkill/rfkill*; do
    [ "$(cat "$r/type" 2>/dev/null)" = wlan ] || continue
    if [ "$(cat "$r/soft" 2>/dev/null)" = 1 ] || [ "$(cat "$r/hard" 2>/dev/null)" = 1 ]; then BLOCKED=1; fi
done

ICON="network-wireless-offline-symbolic"
TOOL="Network: disconnected (click to connect)"
if [ -n "$ETH" ]; then
    IP=$(ip4 "$ETH")
    ICON="network-wired-symbolic"
    TOOL="Ethernet: $ETH${{IP:+ · $IP}}"
elif [ "$BLOCKED" = 1 ]; then
    ICON="network-wireless-disabled-symbolic"
    TOOL="Wi-Fi: disabled (click to enable)"
elif [ -n "$WDEV" ] && [ "$(cat "/sys/class/net/$WDEV/operstate" 2>/dev/null)" = up ]; then
    LINK=$(iw dev "$WDEV" link 2>/dev/null)
    SSID=$(printf '%s\\n' "$LINK" | sed -n 's/^[[:space:]]*SSID: //p')
    DBM=$(printf '%s\\n' "$LINK" | awk '/signal:/{{print $2; exit}}')
    SIG=$(( ( ${{DBM:--70}} + 90 ) * 2 ))
    [ "$SIG" -gt 100 ] && SIG=100
    [ "$SIG" -lt 0 ] && SIG=0
    if [ "$SIG" -ge 80 ]; then ICON="network-wireless-signal-excellent-symbolic"
    elif [ "$SIG" -ge 55 ]; then ICON="network-wireless-signal-good-symbolic"
    elif [ "$SIG" -ge 30 ]; then ICON="network-wireless-signal-ok-symbolic"
    elif [ "$SIG" -gt 0 ]; then ICON="network-wireless-signal-weak-symbolic"
    else ICON="network-wireless-signal-none-symbolic"
    fi
    IP=$(ip4 "$WDEV")
    TOOL="Wi-Fi: ${{SSID:-connected}} (${{SIG}}%)${{IP:+ · $IP}}"
fi

printf '<icon>%s</icon>\\n<iconclick>%s/.config/rofi/wifi-menu.sh</iconclick>\\n<tool>%s</tool>\\n' "$ICON" "{home}" "$TOOL"
""",
        mode=0o755,
    )
    write(
        cfg / "rofi" / "wifi-menu.sh",
        """#!/bin/sh
# Frosted Noir Glass Rofi Wi-Fi manager. Opens without scanning; "Rescan" scans on demand.
RADIO=$(nmcli radio wifi 2>/dev/null || echo "disabled")
nm_edit() { nohup nm-connection-editor >/dev/null 2>&1 </dev/null & }
note() { notify-send -a "Network" "Wi-Fi" "$1"; }

if [ "$RADIO" = "enabled" ]; then
    NETWORKS=$(nmcli -g IN-USE,SIGNAL,SECURITY,SSID dev wifi list --rescan no 2>/dev/null \
        | awk -F: 'NF>=4 {
            ssid=$4; for (i=5; i<=NF; i++) ssid=ssid ":" $i
            if (ssid=="" || seen[ssid]++) next
            printf "%s%-28s  %3s%%  %s\\n", ($1=="*") ? "✓ " : "  ", ssid, $2, ($3!="" && $3!="--") ? "🔒" : "  "
        }')
    MENU=$(printf 'Disable Wi-Fi\\nRescan Networks\\nNetwork Settings...\\n%s' "$NETWORKS" | sed '/^$/d')
else
    MENU=$(printf 'Enable Wi-Fi\\nNetwork Settings...')
fi

CHOSEN=$(printf '%s\\n' "$MENU" | rofi -dmenu -i -p "Wi-Fi" \
    -theme-str 'window { width: 420px; } listview { columns: 1; lines: 8; } entry { placeholder: "Search networks..."; }')
[ -z "$CHOSEN" ] && exit 0

case "$CHOSEN" in
    "Enable Wi-Fi")  nmcli radio wifi on && note "Wi-Fi enabled" ;;
    "Disable Wi-Fi") nmcli radio wifi off && note "Wi-Fi disabled" ;;
    "Rescan Networks")
        nmcli dev wifi rescan >/dev/null 2>&1 || true
        sleep 3
        exec "$0" ;;
    "Network Settings...") nm_edit ;;
    *)
        SSID=$(printf '%s' "$CHOSEN" | sed -E 's/^(✓ |  )//; s/[[:space:]]+[0-9]+%.*$//')
        [ -z "$SSID" ] && exit 0
        if printf '%s' "$CHOSEN" | grep -q '^✓ '; then
            ACT=$(printf 'Disconnect\\nReconnect\\nNetwork Settings...' | rofi -dmenu -i -p "$SSID" \
                -theme-str 'window { width: 340px; } listview { columns: 1; lines: 3; }')
            case "$ACT" in
                Disconnect) nmcli con down id "$SSID" >/dev/null 2>&1 && note "Disconnected from $SSID" ;;
                Reconnect)
                    nmcli con down id "$SSID" >/dev/null 2>&1
                    nmcli con up id "$SSID" >/dev/null 2>&1 && note "Reconnected to $SSID" || note "Failed to reconnect to $SSID" ;;
                "Network Settings...") nm_edit ;;
            esac
            exit 0
        fi
        if nmcli -g NAME con show 2>/dev/null | grep -Fxq "$SSID"; then
            nmcli con up id "$SSID" >/dev/null 2>&1 && note "Connected to $SSID" || note "Failed to connect to $SSID"
        else
            PASS=$(rofi -dmenu -password -p "Password ($SSID)" \
                -theme-str 'window { width: 380px; } listview { lines: 0; } entry { placeholder: "Enter Wi-Fi password..."; }')
            [ -z "$PASS" ] && exit 0
            nmcli dev wifi connect "$SSID" password "$PASS" >/dev/null 2>&1 && note "Connected to $SSID" || note "Connection failed for $SSID"
        fi
        ;;
esac
""",
        mode=0o755,
    )
    # Hide standalone nm-applet, clipman & unused accessibility daemons (keeps boot RAM < 600 MB)
    write(
        cfg / "autostart" / "nm-applet.desktop",
        """[Desktop Entry]
Type=Application
Name=Network
Hidden=true
""",
    )
    write(
        cfg / "autostart" / "xfce4-clipman-plugin-autostart.desktop",
        """[Desktop Entry]
Type=Application
Name=Clipman
Hidden=true
""",
    )
    write(
        cfg / "autostart" / "at-spi-dbus-bus.desktop",
        """[Desktop Entry]
Type=Application
Name=AT-SPI D-Bus Bus
Hidden=true
""",
    )
    write(
        cfg / "autostart" / "picom.desktop",
        """[Desktop Entry]
Type=Application
Name=Picom
Hidden=true
""",
    )
    write(
        cfg / "autostart" / "conky-widgets.desktop",
        f"""[Desktop Entry]
Type=Application
Name=Noir Glass Widgets
Exec={home}/.config/conky/start.sh
Hidden=false
X-GNOME-Autostart-enabled=true
""",
    )
    write(
        home / ".local" / "bin" / "auto-compositor.sh",
        """#!/bin/sh
# Event-driven XFWM4 compositor toggle (0% idle CPU): OFF while a fullscreen game has focus,
# ON for everything else (Alt+Tab, Super+D, close). Compositing is always restored on exit.
# shortcut: fullscreen windows with _NET_WM_BYPASS_COMPOSITOR=1 or a known game WM_CLASS; add patterns below if a game misses both.
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/auto-compositor.pid"
if [ -r "$PIDFILE" ] && [ "$(cat "$PIDFILE")" != "$$" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    exit 0
fi
echo $$ > "$PIDFILE"
cleanup() {
    pkill -P $$ -x xprop 2>/dev/null
    xfconf-query -c xfwm4 -p /general/use_compositing -s true 2>/dev/null
    rm -f "$PIDFILE"
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
pkill -u "$(id -u)" -f '[x]prop -spy -root _NET_ACTIVE_WINDOW' 2>/dev/null || true

STATE=$(xfconf-query -c xfwm4 -p /general/use_compositing 2>/dev/null || echo "true")
CUR_WID=""
SHOW_DESK="0"

xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST_STACKING _NET_SHOWING_DESKTOP 2>/dev/null | while IFS= read -r line; do
    case "$line" in
        _NET_ACTIVE_WINDOW*)
            CUR_WID=$(printf '%s' "$line" | sed -n 's/.*# \\(0x[0-9a-fA-F]*\\).*/\\1/p')
            ;;
        _NET_SHOWING_DESKTOP*)
            SHOW_DESK=$(printf '%s' "$line" | awk '{print $NF}')
            ;;
    esac
    WANT="true"
    if [ "$SHOW_DESK" != "1" ] && [ -n "$CUR_WID" ] && [ "$CUR_WID" != "0x0" ]; then
        PROPS=$(xprop -id "$CUR_WID" _NET_WM_STATE _NET_WM_BYPASS_COMPOSITOR WM_CLASS 2>/dev/null) || PROPS=""
        case "$PROPS" in
            *_NET_WM_STATE_HIDDEN*) ;;
            *_NET_WM_STATE_FULLSCREEN*)
                case "$PROPS" in
                    *"_NET_WM_BYPASS_COMPOSITOR(CARDINAL) = 1"*|*'"steam_app_'*|*'"cs2"'*|*'"dota2"'*|*'"hl2_linux"'*|*'"gamescope"'*|*'.exe"'*)
                        WANT="false"
                        ;;
                esac
                ;;
        esac
    fi
    if [ "$WANT" != "$STATE" ]; then
        xfconf-query -c xfwm4 -p /general/use_compositing -s "$WANT" 2>/dev/null
        STATE="$WANT"
    fi
done
""",
        mode=0o755,
    )
    write(
        cfg / "autostart" / "auto-compositor.desktop",
        f"""[Desktop Entry]
Type=Application
Name=Auto Compositor Toggle
Exec={home}/.local/bin/auto-compositor.sh
Hidden=false
X-GNOME-Autostart-enabled=true
""",
    )
    write(
        cfg / "autostart" / "dunst.desktop",
        """[Desktop Entry]
Type=Application
Name=Dunst Notifications
Exec=dunst
Hidden=false
X-GNOME-Autostart-enabled=true
""",
    )
    write(
        cfg / "autostart" / "xcape.desktop",
        """[Desktop Entry]
Type=Application
Name=Xcape Super Tap
Exec=xcape -e "Super_L=Alt_L|F1"
Hidden=false
X-GNOME-Autostart-enabled=true
""",
    )

    # 12. LightDM Greeter (1:1 continuity)
    if system_root:
        write(
            system_root / "etc" / "lightdm" / "lightdm-gtk-greeter.conf",
            f"""[greeter]
background = {a['wallpapers']['primary']['file']}
user-background = false
theme-name = {t['name']}
icon-theme-name = {a['icon_theme']}
cursor-theme-name = {a['cursor_theme']}
cursor-theme-size = {a['cursor_size']}
font-name = {ty['sans']} {ty['ui_size']}
xft-antialias = true
xft-dpi = 96
xft-hintstyle = hintslight
xft-rgba = rgb
indicators = ~host;~spacer;~clock;~spacer;~power
clock-format = %a, %b %d   %H:%M
position = 50%,center 50%,center
default-user-image = #avatar-default-symbolic
hide-user-image = false
""",
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--home", required=True)
    ap.add_argument("--system-root", default="/")
    ap.add_argument("--base-gresource", default="/usr/share/themes/Arc-Dark/gtk-3.0/gtk.gresource")
    args = ap.parse_args()

    t = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    home = Path(args.home)
    sys_root = Path(args.system_root)

    user_theme = home / ".themes" / t["name"]
    cached_base = Path(args.tokens).parent / "base-dark.css"
    generate_xfwm4(user_theme, t)
    generate_gtk3_theme(user_theme, t, args.base_gresource, cached_base)
    generate_user_configs(home, t, sys_root)
    print(f"Generated Noir Glass OS ({t['preset']}) into {home} and {sys_root}")


if __name__ == "__main__":
    main()
