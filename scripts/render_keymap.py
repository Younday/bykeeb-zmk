#!/usr/bin/env python3
"""Render this keymap without third-party packages. Fail on unsupported syntax."""
import argparse
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
KEYMAP = ROOT / "boards/shields/bykeeb/bykeeb.keymap"
LAYOUT = ROOT / "boards/shields/bykeeb/bykeeb-layouts.dtsi"
ARITY = {"kp": 1, "hml": 2, "hmr": 2, "lt": 2, "trans": 0,
         "caps_word": 0, "bootloader": 0, "sys_reset": 0, "bt": 1,
         "ext_power": 1, "out": 1, "mkp": 1, "studio_unlock": 0}
LABELS = {
    "LCTL": "Ctrl", "RCTL": "Ctrl", "LGUI": "GUI", "RGUI": "GUI",
    "LALT": "Alt", "RALT": "AltGr", "LSHIFT": "Shift", "RSHIFT": "Shift",
    "SEMI": ";", "COMMA": ",", "DOT": ".", "FSLH": "/", "SQT": "'",
    "DEL": "Delete", "RET": "Enter", "TAB": "Tab", "BSPC": "Bksp",
    "SPACE": "Space", "ESC": "Esc", "PG_UP": "PgUp", "PG_DN": "PgDn",
    "HOME": "Home", "END": "End", "UP": "↑", "DOWN": "↓", "LEFT": "←",
    "RIGHT": "→", "ASTRK": "*", "MINUS": "−", "PLUS": "+", "EQUAL": "=",
    "EXCL": "!", "AT": "@", "HASH": "#", "DLLR": "$", "PRCNT": "%",
    "CARET": "^", "AMPS": "&", "UNDER": "_", "LBKT": "[", "RBKT": "]",
    "LBRC": "{", "RBRC": "}", "LPAR": "(", "RPAR": ")", "LT": "<",
    "GT": ">", "CAPS": "Caps Lock", "GRAVE": "`", "BSLH": "\\",
    "C_PLAY_PAUSE": "Play/Pause", "K_VOL_UP": "Vol +", "K_VOL_DN": "Vol −",
    "C_MUTE": "Mute", "LCLK": "Left click", "RCLK": "Right click",
    "MCLK": "Mid click", "BT_PRV": "BT prev", "BT_NXT": "BT next",
    "BT_CLR": "BT clear", "EP_TOG": "Power toggle", "EP_ON": "Power on",
    "EP_OFF": "Power off", "OUT_USB": "USB", "OUT_BLE": "Bluetooth",
}


def label(code):
    if code in LABELS:
        return LABELS[code]
    if re.fullmatch(r"N\d", code):
        return code[1:]
    for prefix, name in [("LC", "Ctrl"), ("LS", "Shift"), ("LG", "GUI"), ("LA", "Alt")]:
        if code.startswith(prefix + "(") and code.endswith(")"):
            return name + "+" + label(code[len(prefix) + 1:-1])
    return code


def parse():
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", KEYMAP.read_text(), flags=re.S)
    constants = {name: int(n) for name, n in re.findall(r"#define\s+(\w+)\s+(\d+)", source)}
    layers = {}
    raw_layers = {}
    for name, body in re.findall(r"(\w+)_layer\s*\{\s*bindings\s*=\s*<(.*?)>;", source, re.S):
        raw = [b.strip() for b in re.findall(r"&[^&]+", body)]
        if len(raw) != 36:
            raise ValueError(f"{name}: expected 36 bindings, got {len(raw)}")
        keys = []
        for binding in raw:
            parts = binding[1:].split()
            behavior, args = parts[0], parts[1:]
            arity = 2 if behavior == "bt" and args and args[0] == "BT_SEL" else ARITY.get(behavior)
            if arity is None or len(args) != arity:
                raise ValueError(f"Unsupported binding: {binding}")
            if behavior in ("hml", "hmr", "lt"):
                if behavior == "lt" and args[0] not in constants:
                    raise ValueError(f"Unknown layer {args[0]}")
                key = {"t": label(args[1]), "h": label(args[0])}
            elif behavior == "trans":
                key = {"t": "▽", "type": "trans"}
            elif behavior == "bt" and args[0] == "BT_SEL":
                key = {"t": f"BT {int(args[1]) + 1}"}
            elif behavior in ("kp", "bt", "out", "mkp", "ext_power"):
                key = {"t": label(args[0])}
            else:
                key = {"t": {"caps_word": "Caps Word", "bootloader": "Bootloader",
                             "sys_reset": "Reset", "studio_unlock": "Unlock Studio"}[behavior]}
            keys.append(key)
        layers[name] = keys
        raw_layers[name] = raw
    if len(layers) != 7 or list(layers)[0] != "default":
        raise ValueError("Expected the seven Bykeeb layers, starting with default")
    positions = []
    for body in re.findall(r"<&key_physical_attrs\s+([^>]+)>", LAYOUT.read_text()):
        values = [int(n) for n in re.findall(r"-?\d+", body)]
        if len(values) != 7:
            raise ValueError("Invalid physical key attributes")
        positions.append(values)
    if len(positions) != 36:
        raise ValueError("Expected 36 physical key positions")
    return layers, raw_layers, positions


def reference_metadata(layers, raw):
    """Read the settings referenced by the generated instructions, or fail closed."""
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", KEYMAP.read_text(), flags=re.S)
    constants = {name: int(n) for name, n in re.findall(r"#define\s+(\w+)\s+(\d+)", source)}
    names = list(layers)
    combos = []
    combo_timings = []
    settings = {}
    for node, body in re.findall(r"(\w+)\s*\{([^{}]*)\};", source, re.S):
        match = re.search(r"^\s*key-positions\s*=\s*<([^>]+)>;", body, re.M)
        if match:
            positions = [int(n) for n in match[1].split()]
            if not positions or any(p < 0 or p >= 36 for p in positions):
                raise ValueError(f"Invalid combo positions: {node}")
            binding = re.search(r"bindings\s*=\s*<\s*&kp\s+(\S+)\s*>;", body)
            if not binding:
                raise ValueError(f"Unsupported combo binding: {node}")
            scope = re.search(r"layers\s*=\s*<([^>]+)>;", body)
            combo = {"p": positions, "k": label(binding[1])}
            if scope:
                indices = [constants[s] if s in constants else int(s) for s in scope[1].split()]
                if any(i < 0 or i >= len(names) for i in indices):
                    raise ValueError(f"Invalid combo layers: {node}")
                combo["l"] = [names[i] for i in indices]
            combos.append(combo)
            timing = []
            for prop, text in (("timeout-ms", "chord window"), ("require-prior-idle-ms", "prior idle")):
                match = re.search(rf"{prop}\s*=\s*<(\d+)>;", body)
                if match:
                    timing.append(f"{text} {match[1]} ms")
            combo_timings.append(timing)
        if node in ("homerow_mod_left", "homerow_mod_right"):
            values = {}
            for prop in ("tapping-term-ms", "require-prior-idle-ms", "quick-tap-ms"):
                match = re.search(rf"{prop}\s*=\s*<(\d+)>;", body)
                if not match:
                    raise ValueError(f"Missing {prop} in {node}")
                values[prop] = int(match[1])
            settings[node] = values
    if set(settings) != {"homerow_mod_left", "homerow_mod_right"}:
        raise ValueError("Expected left and right home-row behaviors")
    summaries = []
    for combo, details in zip(combos, combo_timings):
        keys = " + ".join(layers['default'][p]['t'] for p in combo['p'])
        scope = ", ".join(combo.get('l', names))
        scope = '; '.join([scope, *details])
        summaries.append(f"{keys} → {combo['k']} ({scope})")
    timing = "; ".join(
        f"{side}: hold {settings[node]['tapping-term-ms']} ms, "
        f"prior idle {settings[node]['require-prior-idle-ms']} ms, "
        f"quick tap {settings[node]['quick-tap-ms']} ms"
        for side, node in (("Left", "homerow_mod_left"), ("Right", "homerow_mod_right")))
    unlocks = []
    for index, (name, bindings) in enumerate(raw.items()):
        for pos, binding in enumerate(bindings):
            if binding != '&studio_unlock':
                continue
            activators = [layers['default'][p]['t'] for p, b in enumerate(raw['default'])
                          if b.startswith('&lt ') and constants[b.split()[1]] == index]
            target = layers['default'][pos]['t']
            prefix = f"Hold {' or '.join(activators)} and press" if activators else f"On {name}, press"
            unlocks.append(f"{prefix} {target} to unlock editing.")
    return combos, summaries, timing, ' '.join(unlocks) or 'No Studio unlock binding is defined.'


def draw_layer(name, keys, raw, positions, offset):
    out = [f'<g class="layer" data-layer="{name}" transform="translate(24 {offset})">',
           f'<text class="layer-title" x="0" y="24">{name.upper()}</text>']
    for i, (key, binding, pos) in enumerate(zip(keys, raw, positions)):
        w, h, x, y, angle, rx, ry = pos
        x, y, w, h, rx, ry = [v * .64 for v in (x, y, w, h, rx, ry)]
        y += 48
        ry += 48
        cls = "key transparent" if key.get("type") == "trans" else "key"
        if "h" in key:
            cls += " dual"
        out.extend([f'<g class="{cls}" data-position="{i}" transform="rotate({angle/100} {rx} {ry})">',
                    f'<title>{html.escape(binding)}</title>',
                    f'<rect x="{x+2}" y="{y+2}" width="{w-4}" height="{h-4}" rx="7"/>',
                    ])
        text = key["t"]
        lines = [text]
        if len(text) > 9:
            separator = '+' if '+' in text else ' '
            if separator in text:
                first, rest = text.split(separator, 1)
                lines = [first + ('+' if separator == '+' else ''), rest]
        center = y + h / 2 - (3 if "h" in key else 0)
        for line_index, line in enumerate(lines):
            size = min(12, 52 / max(1, len(line) * .6))
            text_y = center + (line_index - (len(lines) - 1) / 2) * 14
            out.append(f'<text style="font-size:{size:.2f}px" x="{x+w/2}" y="{text_y}">{html.escape(line)}</text>')
        if "h" in key:
            out.append(f'<text class="hold" x="{x+w/2}" y="{y+h-10}">{html.escape(key["h"])}</text>')
        out.append('</g>')
    out.append('</g>')
    return '\n'.join(out)


STYLE = """
svg {font:12px system-ui,sans-serif;background:#fafaf7;color:#182b34}
rect {fill:white;stroke:#bbc6c8;stroke-width:1.2}
text {fill:currentColor;text-anchor:middle;dominant-baseline:middle}
.layer-title {font-size:18px;font-weight:700;text-anchor:start}
.hold {font-size:10px;fill:#176957}
.dual rect {fill:#eaf6ef;stroke:#75a995}
.transparent {opacity:.43}
"""


def outputs():
    layers, raw, positions = parse()
    combos, summaries, timing, studio = reference_metadata(layers, raw)
    combo_text = '; '.join(summaries) or 'None'
    panels = [draw_layer(name, keys, raw[name], positions, 12 + i * 418)
              for i, (name, keys) in enumerate(layers.items())]
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="944" height="2980" '
           'viewBox="0 0 944 2980" role="img" aria-label="Bykeeb seven-layer keymap">\n'
           f'<style>{STYLE}</style>\n<rect width="944" height="2980" style="fill:#fafaf7;stroke:none"/>\n' + '\n'.join(panels) +
           '<text x="24" y="2960" style="text-anchor:start">'
           'Tap: main label · Hold: green label · ▽: underlying layer · Combos: ' + html.escape(combo_text) +
           '</text>\n</svg>\n')
    options = ''.join(f'<option value="{name}">{name.upper()}</option>' for name in layers)
    single_svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 944 420" '
                  'role="img" aria-label="Selected keyboard layer">' +
                  f'<style>{STYLE}</style>' +
                  ''.join(draw_layer(name, keys, raw[name], positions, 0) for name, keys in layers.items()) + '</svg>')
    page = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bykeeb layout reference</title>
<style>
body{max-width:1150px;margin:36px auto;padding:0 20px;background:#fafaf7;color:#182b34;font:16px/1.6 system-ui,sans-serif}
h1{font-size:34px;margin-bottom:4px}select{font:inherit;padding:8px 16px;border:1px solid #bbc6c8;border-radius:6px;background:white}
svg{width:100%;height:auto;margin-top:24px}.layer{display:none}.layer.active{display:block}
aside{border-top:1px solid #bbc6c8;margin-top:20px;padding-top:18px}code{background:#eaf6ef;padding:2px 5px}
@media print{select{display:none}.layer{display:block}svg{display:none}}
</style>
<h1>Bykeeb</h1><p>Seven layers, one keyboard. Choose a layer to explore its bindings.</p>
<label for="layer">Layer </label><select id="layer">OPTIONS</select>
__LAYER_SVG__
<p>Tap the main label; hold for the green label. ▽ falls through to an underlying active layer.
Hover a key to see its ZMK binding. Hold labels on the base layer show how to reach other layers.</p>
<aside><p><strong>Home-row modifiers:</strong> use the modifier on the opposite hand to your target key.
After typing, pause briefly before a shortcut. Same-hand shortcuts need a deliberate hold.
Tap then quickly hold a letter to repeat it.</p>
<p><strong>Configured timings:</strong> __TIMING__.</p>
<p><strong>Combos (base key labels):</strong> __COMBOS__.</p>
<p><strong>Studio:</strong> __STUDIO__</p>
<p>This reference shows the firmware defaults. Changes saved in ZMK Studio are stored on the keyboard
and are not reflected here. Use the SVG file for printing all layers.</p></aside>
<script>
const selector=document.getElementById('layer');
function showLayer(){document.querySelectorAll('.layer').forEach(layer=>layer.classList.toggle('active',layer.dataset.layer===selector.value));}
selector.addEventListener('change',showLayer);showLayer();
</script></html>
'''.replace('OPTIONS', options).replace('__LAYER_SVG__', single_svg).replace(
        '__TIMING__', html.escape(timing)).replace('__COMBOS__', html.escape(combo_text)).replace(
        '__STUDIO__', html.escape(studio))
    data = {"layers": layers, "combos": combos}
    return {"keymap-drawer/bykeeb.svg": svg,
            "keymap-drawer/bykeeb.yaml": json.dumps(data, ensure_ascii=False, indent=2) + '\n',
            "docs/layout.html": page}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if generated files need updating')
    args = parser.parse_args()
    stale = []
    for path, content in outputs().items():
        target = ROOT / path
        if args.check:
            if not target.exists() or target.read_text() != content:
                stale.append(path)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    if stale:
        parser.exit(1, 'Regenerate with python3 scripts/render_keymap.py: ' + ', '.join(stale) + '\n')
    print('Layout references are current.' if args.check else 'Rendered seven 36-key layers.')


if __name__ == '__main__':
    main()
