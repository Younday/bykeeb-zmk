# Bykeeb ZMK configuration

36-key split QWERTY for two Seeed XIAO nRF52840 controllers, with upstream ZMK,
USB Studio support and positional home-row modifiers.

![All seven layers](keymap-drawer/bykeeb.svg)

Download and open [the interactive layer reference](docs/layout.html) in a browser,
or zoom and print [the SVG](keymap-drawer/bykeeb.svg). Display geometry follows
the previous diagram's approximation; matrix wiring and key ordering are unchanged.

## Build and flash

1. Open **Actions → Build firmware** and select the run for your branch/commit.
2. Wait for both halves to succeed, then download the `firmware` artifact.
3. Extract `bykeeb_left.uf2` and `bykeeb_right.uf2`.
4. Connect one half by USB and double-press its physical RESET button.
5. Copy that half's matching UF2 to its bootloader drive.
6. Repeat for the other half. Update **both halves** together for this migration.

Save your old working firmware before upgrading. Roll back by flashing the old
matching pair. This repository does not contain your previously flashed binaries;
old source alone cannot reconstruct dependencies that used moving branches.

If Bluetooth fails, remove the host pairing, clear the relevant keyboard profile
and pair again. If the halves no longer connect, follow
[ZMK connection troubleshooting](https://zmk.dev/docs/troubleshooting/connection-issues).
Settings-reset firmware is a recovery step, not part of a normal upgrade.
The artifact also includes `recovery_settings_reset.uf2`. Flash it only when a
settings reset is needed, then immediately reflash the normal matching firmware.
It clears saved settings and Bluetooth bonds on whichever half receives it.

## Your layout

Tap for the main legend; hold for the second action.
Thumbs, left to right: Delete, Enter/NAV, Tab/FUNC, Backspace/MEDIA, Space/SYM, quote.
T and Y access the left and right number layers respectively.

| A | S | D | F | J | K | L | ; |
|---|---|---|---|---|---|---|---|
| Ctrl | GUI | Alt | Shift | Shift | Right Alt/AltGr | GUI | Ctrl |

Original letters, layer contents, shortcuts and mouse buttons are retained.
On MEDIA, **Q now unlocks Studio**. Z + X Undo is restricted to the base layer
and requires 150 ms prior idle to reduce accidental activation during typing.

## Home-row modifier tuning

The `hml` and `hmr` behaviors use the upstream-supported
[timeless approach](https://zmk.dev/docs/keymaps/behaviors/hold-tap#custom-hold-tap-examples):

- `balanced` recognizes a chord when the target key is pressed and released.
- Opposite-hand keys and all thumbs can trigger early modifier chords.
- `hold-trigger-on-release` permits stacking held modifiers on the same hand.
- `tapping-term-ms = <280>` retains deliberate same-hand shortcuts after a hold.
- `require-prior-idle-ms = <150>` makes home-row presses during typing become letters.
- `quick-tap-ms = <175>` supports tap-then-hold letter repetition.

For Copy, hold right Ctrl (`;`) and tap C. After typing a word, pause briefly
before starting a modifier chord. For a same-hand shortcut, first hold the modifier
past 280 ms.

Edit both behaviors in
[`boards/shields/bykeeb/bykeeb.keymap`](boards/shields/bykeeb/bykeeb.keymap):

| Symptom | First adjustment |
|---|---|
| Cross-hand typing produces modifiers | Increase prior idle in small steps |
| Shortcuts become letters just after typing | Decrease prior idle |
| Same-hand shortcuts feel slow | Decrease tapping term cautiously |
| Mid-word Shift is missed | Give Shift a separate behavior with less prior idle, or consider dedicated/sticky thumb Shift |

These defaults need real typing validation. Shift has the same protection as other
modifiers; fast mid-word capitals may require tuning. No thumb is reassigned.
Mouse modifier clicks require waiting for the hold threshold; eager modifiers
(`hold-while-undecided`) are not enabled.

## ZMK Studio

1. Connect the **left half** by USB. If needed, select USB output by holding
   Backspace/MEDIA and pressing the key at the `.` position.
2. Open [ZMK Studio](https://zmk.studio/) in Chrome/Edge or its native app.
3. Hold **Backspace/MEDIA and press Q** to unlock, then connect and edit bindings.

Studio can assign built-in behaviors and the compiled `Home Row Left` and
`Home Row Right` behaviors. USB Studio is enabled on the central/left half only.
BLE Studio is not enabled; ordinary Bluetooth keyboard use is retained.

Timings, new behaviors and combos require source edits and a rebuild.
Studio mappings persist on the keyboard: after changing mappings in source and
flashing, use **Restore Stock Settings** to load compiled defaults. Record wanted
Studio edits first, because restoring replaces the saved mapping.
Diagrams show firmware defaults, not runtime Studio changes.

## Editing and layout references

The only firmware keymap is `boards/shields/bykeeb/bykeeb.keymap`.
Display geometry is in `boards/shields/bykeeb/bykeeb-layouts.dtsi`.
After editing either, run:

```sh
python3 scripts/render_keymap.py
python3 scripts/render_keymap.py --check
```

This generates the SVG, interactive HTML and JSON-compatible YAML directly from
the firmware keymap using only Python's standard library. Layout CI rejects stale
diagrams. Add parser/label support when introducing a new behavior.
The renderer checks the seven 36-key layers; it does not replace a firmware build.

## Firmware dependencies

`config/west.yml` pins upstream ZMK to
`4dd95d7840eb3d5a3f59bb29fbf1ab054715ef85` (2026-10-09) and Zephyr to
`10ba6d0cb38bc3d258775d27982f707599320085`.
This is a development snapshot, not a claim that v0.4 has been released.
The build workflow uses the same ZMK revision; imported modules use the revisions
in those pinned manifests.

The old pointer fork, chiptuner and Fingerpunch dependencies are removed. This
shield uses ordinary GPIO matrix scanning and upstream mouse buttons; no attached
trackpad or trackball is defined. `CONFIG_ZMK_POINTING=y` enables upstream pointing.
The new `xiao_ble//zmk` target includes upstream battery sensing and bootloader
support. The original 30-minute deep sleep remains in `config/bykeeb.conf`.

Future upgrades should deliberately update the ZMK/Zephyr pins and matching
workflow revision, then build both halves and check the layout references.

