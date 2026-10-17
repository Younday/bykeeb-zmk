#!/usr/bin/env python3
"""Render this keymap without third-party packages. Fail on unsupported syntax."""
import argparse
import html
import json
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
KEYMAP = ROOT / "boards/shields/bykeeb/bykeeb.keymap"
LAYOUT = ROOT / "boards/shields/bykeeb/bykeeb-layouts.dtsi"
ARITY = {"kp": 1, "hml": 2, "hmr": 2, "lt": 2, "trans": 0,
         "caps_word": 0, "bootloader": 0, "sys_reset": 0, "bt": 1,
         "ext_power": 1, "out": 1, "mkp": 1, "studio_unlock": 0, "to": 1,
         "nml": 2, "nmr": 2, "bsp": 2, "skq": 1, "tog": 1, "num_word": 1,
         "num_off": 1, "select_word": 0, "select_line": 0, "clear_line": 0, "num_exit": 0}
LAYER_TAPS = {"lt", "nml", "nmr", "bsp"}
LAYER_LABELS = {"default": "QWERTY", "colemak": "Colemak-DH",
                "numlft": "NUM left", "numrht": "NUM right", "numword": "Numword"}
ACTION_LABELS = {"caps_word": "Caps Word", "bootloader": "Bootloader",
                 "sys_reset": "Reset", "studio_unlock": "Unlock Studio",
                 "select_word": "Select word", "select_line": "Select line",
                 "clear_line": "Clear term line", "num_exit": "Esc / exit NUM"}
HOLD_NODES = {"homerow_mod_left": "Left", "homerow_mod_right": "Right",
              "backspace_media": "Backspace/MEDIA", "number_hold_left": "Left letter/NUM",
              "number_hold_right": "Right letter/NUM"}
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


def layer_label(name):
    return LAYER_LABELS.get(name, name.upper())


def binding_key(binding, constants, names):
    """Validate and label a layer or combo binding using the same rules."""
    parts = binding[1:].split()
    behavior, args = parts[0], parts[1:]
    arity = 2 if behavior == "bt" and args and args[0] == "BT_SEL" else ARITY.get(behavior)
    if arity is None or len(args) != arity:
        raise ValueError(f"Unsupported binding: {binding}")
    if behavior in LAYER_TAPS | {"to", "tog", "num_word", "num_off"}:
        if args[0] not in constants or not 0 <= constants[args[0]] < len(names):
            raise ValueError(f"Unknown layer {args[0]}")
        target = layer_label(names[constants[args[0]]])
        if behavior in LAYER_TAPS:
            return {"t": label(args[1]), "h": target}
        prefix = {"to": "Use ", "tog": "Lock ", "num_word": "Auto ", "num_off": "Exit "}[behavior]
        return {"t": prefix + target}
    if behavior in ("hml", "hmr"):
        return {"t": label(args[1]), "h": label(args[0])}
    if behavior == "trans":
        return {"t": "▽", "type": "trans"}
    if behavior == "skq":
        return {"t": label(args[0]), "h": "Sticky on tap"}
    if behavior == "bt" and args[0] == "BT_SEL":
        return {"t": f"BT {int(args[1]) + 1}"}
    if behavior in ("kp", "bt", "out", "mkp", "ext_power"):
        return {"t": label(args[0])}
    return {"t": ACTION_LABELS[behavior]}


def parse():
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", KEYMAP.read_text(), flags=re.S)
    constants = {name: int(n) for name, n in re.findall(r"#define\s+(\w+)\s+(\d+)", source)}
    layers = {}
    raw_layers = {}
    definitions = re.findall(r"(\w+)_layer\s*\{\s*bindings\s*=\s*<(.*?)>;", source, re.S)
    names = [name for name, _ in definitions]
    for name, body in definitions:
        raw = [b.strip() for b in re.findall(r"&[^&]+", body)]
        if len(raw) != 36:
            raise ValueError(f"{name}: expected 36 bindings, got {len(raw)}")
        keys = [binding_key(binding, constants, names) for binding in raw]
        layers[name] = keys
        raw_layers[name] = raw
    if not layers or list(layers)[0] != "default":
        raise ValueError("Expected Bykeeb layers starting with default")
    names = list(layers)
    for index, name in enumerate(names):
        if constants.get(name.upper()) != index:
            raise ValueError(f"Layer index mismatch for {name}")
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
            binding = re.search(r"bindings\s*=\s*<\s*(&[^>]+)\s*>;", body)
            if not binding:
                raise ValueError(f"Unsupported combo binding: {node}")
            scope = re.search(r"layers\s*=\s*<([^>]+)>;", body)
            combo = {"p": positions, "k": binding_key(binding[1].strip(), constants, names)['t']}
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
        if node in HOLD_NODES:
            values = {}
            for prop in ("tapping-term-ms", "require-prior-idle-ms", "quick-tap-ms"):
                match = re.search(rf"{prop}\s*=\s*<(\d+)>;", body)
                if not match:
                    if prop == "require-prior-idle-ms" and node == "backspace_media":
                        continue
                    raise ValueError(f"Missing {prop} in {node}")
                values[prop] = int(match[1])
            settings[node] = values
        if node == "sticky_shift":
            timeout = re.search(r"release-after-ms\s*=\s*<(\d+)>;", body)
            if not timeout:
                raise ValueError("Missing sticky Shift timeout")
            settings[node] = {"timeout": int(timeout[1]),
                              "quick-release": bool(re.search(r"\bquick-release\s*;", body))}
    if set(settings) != set(HOLD_NODES) | {"sticky_shift"}:
        raise ValueError("Expected configured hold-taps and sticky Shift")
    summaries = []
    for combo, details in zip(combos, combo_timings):
        keys = " + ".join(layers['default'][p]['t'] for p in combo['p'])
        scope = ", ".join(combo.get('l', names))
        scope = '; '.join([scope, *details])
        summaries.append(f"{keys} → {combo['k']} ({scope})")
    timings = []
    for node, side in HOLD_NODES.items():
        values = settings[node]
        parts = [f"hold {values['tapping-term-ms']} ms"]
        if 'require-prior-idle-ms' in values:
            parts.append(f"prior idle {values['require-prior-idle-ms']} ms")
        parts.append(f"quick tap {values['quick-tap-ms']} ms")
        timings.append(f"{side}: " + ', '.join(parts))
    sticky = settings['sticky_shift']
    timings.append(f"Sticky Shift: timeout {sticky['timeout']} ms, " +
                   ('release on next press' if sticky['quick-release'] else 'release on next release'))
    timing = '; '.join(timings)
    unlocks = []
    switches = []
    for index, (name, bindings) in enumerate(raw.items()):
        for pos, binding in enumerate(bindings):
            if binding != '&studio_unlock' and not binding.startswith('&to '):
                continue
            activators = [layers['default'][p]['t'] for p, b in enumerate(raw['default'])
                          if b.split()[0][1:] in LAYER_TAPS and constants[b.split()[1]] == index]
            target = layers['default'][pos]['t']
            prefix = f"Hold {' or '.join(activators)} and press" if activators else f"On {name}, press"
            if binding == '&studio_unlock':
                unlocks.append(f"{prefix} {target} to unlock editing.")
            else:
                selected = names[constants[binding.split()[1]]]
                switches.append(f"{prefix} {target} to select {layer_label(selected)}.")
    return (combos, summaries, timing,
            ' '.join(unlocks) or 'No Studio unlock binding is defined.', ' '.join(switches))


def draw_layer(name, keys, raw, positions, offset):
    out = [f'<g class="layer" data-layer="{name}" transform="translate(24 {offset})">',
           f'<text class="layer-title" x="0" y="24">{html.escape(layer_label(name))}</text>']
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
    combos, summaries, timing, studio, switches = reference_metadata(layers, raw)
    combo_text = '; '.join(summaries) or 'None'
    panels = [draw_layer(name, keys, raw[name], positions, 12 + i * 418)
              for i, (name, keys) in enumerate(layers.items())]
    footer = textwrap.wrap('Tap: main label · Hold: green label · ▽: underlying layer · Combos: ' + combo_text, 120)
    height = len(layers) * 418 + 54 + (len(footer) - 1) * 18
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="944" height="{height}" '
           f'viewBox="0 0 944 {height}" role="img" aria-label="Bykeeb {len(layers)}-layer keymap">\n'
           f'<style>{STYLE}</style>\n<rect width="944" height="{height}" style="fill:#fafaf7;stroke:none"/>\n' + '\n'.join(panels) +
           ''.join(f'<text x="24" y="{len(layers)*418+34+i*18}" style="text-anchor:start">{html.escape(line)}</text>\n'
                   for i, line in enumerate(footer)) + '</svg>\n')
    options = ''.join(f'<option value="{name}">{html.escape(layer_label(name))}</option>' for name in layers)
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
<h1>Bykeeb</h1><p>__COUNT__ layers, one keyboard. Choose a layer to explore its bindings.</p>
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
<p><strong>Base layout:</strong> __SWITCHES__ QWERTY is selected at startup.
The diagram selector only changes this reference; use the keyboard shortcuts to switch the actual keyboard.</p>
<p><strong>Numbers:</strong> the top inner letter on either half holds the opposite numpad.
Enter + Space locks/unlocks the right numpad. Tab + Space toggles Numword, which exits on
Space, Enter, Tab or other non-number input. Numeric thumbs are plain keys; Backspace repeats.
Esc / exit NUM sends Escape and leaves numeric modes, keeping your chosen base layout.
Lock and Numword combos are scoped to exclude each other's mode.</p>
<p><strong>Editing:</strong> hold Enter for right-hand arrows and plain left-hand modifiers.
Word/line selection uses Linux/Windows application shortcuts; Clear term line sends Ctrl+E, Ctrl+U.
The outer right thumb is sticky Shift (or normal Shift while held); quote is on that thumb under SYM.
Tap Backspace then quickly hold it for repetition; a normal hold still activates MEDIA.</p>
<p>This reference shows the firmware defaults. Changes saved in ZMK Studio are stored on the keyboard
and are not reflected here. Use the SVG file for printing all layers.</p></aside>
<script>
const selector=document.getElementById('layer');
function showLayer(){document.querySelectorAll('.layer').forEach(layer=>layer.classList.toggle('active',layer.dataset.layer===selector.value));}
selector.addEventListener('change',showLayer);showLayer();
</script></html>
'''.replace('OPTIONS', options).replace('__LAYER_SVG__', single_svg).replace(
        '__TIMING__', html.escape(timing)).replace('__COMBOS__', html.escape(combo_text)).replace(
        '__STUDIO__', html.escape(studio)).replace('__SWITCHES__', html.escape(switches)).replace('__COUNT__', str(len(layers)))
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
    print('Layout references are current.' if args.check else f'Rendered {len(parse()[0])} 36-key layers.')


if __name__ == '__main__':
    main()
