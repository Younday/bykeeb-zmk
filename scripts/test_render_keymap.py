"""Regression tests for references that previously stayed stale after config edits."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import render_keymap as renderer


class ReferenceChanges(unittest.TestCase):
    def setUp(self):
        self.source = renderer.KEYMAP.read_text()

    def changed_outputs(self, pattern, replacement):
        source, count = re.subn(pattern, replacement, self.source, count=1, flags=re.M)
        self.assertEqual(count, 1, 'Test must change a source property')
        with tempfile.TemporaryDirectory() as directory:
            keymap = Path(directory) / 'changed.keymap'
            keymap.write_text(source)
            with patch.object(renderer, 'KEYMAP', keymap):
                output = renderer.outputs()
                # Existing checked-in references must be rejected after an edit.
                with patch('sys.argv', ['render_keymap.py', '--check']), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        renderer.main()
                self.assertEqual(error.exception.code, 1)
                return output

    def test_combo_positions(self):
        output = self.changed_outputs(r'^(\s*key-positions\s*=\s*<)[^>]+>', r'\g<1>21 22>')
        self.assertEqual(json.loads(output['keymap-drawer/bykeeb.yaml'])['combos'][0]['p'], [21, 22])
        self.assertIn('X + C → Ctrl+Z', output['docs/layout.html'])

    def test_combo_action(self):
        output = self.changed_outputs(r'(&kp\s+)LC\(Z\)', r'\g<1>LC(Y)')
        self.assertIn('Z + X → Ctrl+Y', output['docs/layout.html'])

    def test_combo_scope(self):
        output = self.changed_outputs(r'^(\s*layers\s*=\s*<)[^>]+>', r'\g<1>NAV>')
        self.assertEqual(json.loads(output['keymap-drawer/bykeeb.yaml'])['combos'][0]['l'], ['nav'])

    def test_combo_prior_idle(self):
        output = self.changed_outputs(r'(require-prior-idle-ms\s*=\s*<)\d+', r'\g<1>199')
        self.assertIn('prior idle 199 ms', output['docs/layout.html'])

    def test_home_row_timing(self):
        output = self.changed_outputs(r'(hml: homerow_mod_left\s*\{[\s\S]*?tapping-term-ms\s*=\s*<)\d+', r'\g<1>320')
        self.assertIn('Left: hold 320 ms', output['docs/layout.html'])

    def test_backspace_timing(self):
        output = self.changed_outputs(r'(bsp: backspace_media\s*\{[\s\S]*?quick-tap-ms\s*=\s*<)\d+', r'\g<1>225')
        self.assertIn('Backspace/MEDIA: hold 200 ms, quick tap 225 ms', output['docs/layout.html'])

    def test_sticky_shift_timeout(self):
        output = self.changed_outputs(r'(release-after-ms\s*=\s*<)\d+', r'\g<1>1800')
        self.assertIn('Sticky Shift: timeout 1800 ms', output['docs/layout.html'])

    def test_studio_unlock_position(self):
        output = self.changed_outputs(r'&studio_unlock\s+&num_word NUMWORD', '&num_word NUMWORD &studio_unlock')
        self.assertIn('Hold Bksp and press W', output['docs/layout.html'])

    def test_numeric_entry_instructions_follow_bindings(self):
        output = self.changed_outputs(r'&num_word NUMWORD\s+&tog NUMRHT', '&tog NUMRHT &num_word NUMWORD')
        self.assertIn('Hold Bksp and press E / Colemak F: Auto Numword.', output['docs/layout.html'])

    def test_macro_sequences_in_reference_follow_source(self):
        output = self.changed_outputs(r'(<&kp )LC\(E\)(>, <&kp LC\(U\)>)', r'\g<1>LC(A)\g<2>')
        self.assertIn('Clear Terminal Line: Ctrl+A then Ctrl+U', output['docs/layout.html'])

    def test_macro_timing_in_reference_follows_source(self):
        output = self.changed_outputs(r'(select_word: select_word\s*\{[\s\S]*?wait-ms\s*=\s*<)\d+', r'\g<1>60')
        self.assertIn('tap 40 ms, wait 60 ms', output['docs/layout.html'])


class ColemakLayout(unittest.TestCase):
    def setUp(self):
        self.layers, self.raw, _ = renderer.parse()
        self.names = list(self.layers)

    def test_matrix_colemak_dh_letters(self):
        expected = ['Q', 'W', 'F', 'P', 'B', 'J', 'L', 'U', 'Y', ';',
                    'A', 'R', 'S', 'T', 'G', 'M', 'N', 'E', 'I', 'O',
                    'Z', 'X', 'C', 'D', 'V', 'K', 'H', ',', '.', '/']
        self.assertEqual([key['t'] for key in self.layers['colemak'][:30]], expected)

    def test_modifier_and_layer_holds_stay_on_the_same_fingers(self):
        for position in [4, 5, 10, 11, 12, 13, 16, 17, 18, 19]:
            self.assertEqual(self.raw['default'][position].split()[:-1],
                             self.raw['colemak'][position].split()[:-1])
        self.assertEqual(self.raw['default'][30:], self.raw['colemak'][30:])

    def test_shared_layers_override_both_bases_and_fall_through_correctly(self):
        self.assertEqual(self.names[:2], ['default', 'colemak'])
        self.assertLess(self.names.index('colemak'), min(self.names.index(name) for name in
                        ['nav', 'sym', 'func', 'media', 'numlft', 'numrht', 'numword']))

        def resolve(position, active):
            return next(self.raw[name][position] for name in reversed(self.names)
                        if name in active and self.raw[name][position] != '&trans')

        self.assertEqual(resolve(16, ['default', 'colemak', 'nav']), '&kp LEFT')
        self.assertEqual(resolve(23, ['default', 'colemak', 'numword']), '&kp D')
        self.assertEqual(resolve(23, ['default', 'numword']), '&kp V')

    def test_media_can_select_both_bases(self):
        self.assertEqual(self.raw['media'][20:22], ['&to COLEMAK', '&to DEFAULT'])
        page = renderer.outputs()['docs/layout.html']
        self.assertIn('Hold Bksp and press Z to select Colemak-DH.', page)
        self.assertIn('Hold Bksp and press X to select QWERTY.', page)

    def test_undo_applies_to_both_base_layouts(self):
        output = json.loads(renderer.outputs()['keymap-drawer/bykeeb.yaml'])
        self.assertEqual(output['combos'][0]['l'], ['default', 'colemak'])

    def test_all_layers_are_visible_in_the_references(self):
        output = renderer.outputs()
        self.assertEqual(output['docs/layout.html'].count('<option '), len(self.names))
        self.assertEqual(output['keymap-drawer/bykeeb.svg'].count('data-position='), len(self.names) * 36)


class ErgonomicLayers(unittest.TestCase):
    def setUp(self):
        self.layers, self.raw, _ = renderer.parse()
        self.source = renderer.KEYMAP.read_text()

    def node(self, label):
        match = re.search(rf'\b{label}:\s*\w+\s*\{{([^{{}}]*)\}};', self.source, re.S)
        self.assertIsNotNone(match)
        return match[1]

    def test_number_holds_use_opposite_hand_and_preserve_base_letters(self):
        for name, letters in [('default', ('T', 'Y')), ('colemak', ('B', 'J'))]:
            self.assertEqual(self.raw[name][4], f'&nml NUMRHT {letters[0]}')
            self.assertEqual(self.raw[name][5], f'&nmr NUMLFT {letters[1]}')
        for node, expected in [('nml', set(range(5, 10)) | set(range(15, 20)) | set(range(25, 36))),
                               ('nmr', set(range(0, 5)) | set(range(10, 15)) | set(range(20, 25)) | set(range(30, 36)))]:
            positions = re.search(r'hold-trigger-key-positions\s*=\s*<([^>]+)>', self.node(node))[1]
            self.assertEqual(set(map(int, positions.split())), expected)
            self.assertIn('hold-trigger-on-release;', self.node(node))

    def test_navigation_has_opposite_hand_arrows_and_plain_modifiers(self):
        self.assertEqual(self.raw['default'][31], '&lt NAV RET')
        self.assertEqual(self.raw['nav'][10:14], ['&kp LCTL', '&kp LGUI', '&kp LALT', '&kp LSHIFT'])
        for position, key in [(7, 'UP'), (16, 'LEFT'), (17, 'DOWN'), (18, 'RIGHT')]:
            self.assertEqual(self.raw['nav'][position], '&kp ' + key)

    def test_numeric_modes_have_direct_entry_lock_and_exit(self):
        self.assertEqual(self.raw['media'][1:3], ['&num_word NUMWORD', '&tog NUMRHT'])
        self.assertEqual(self.raw['numrht'][1], '&tog NUMRHT')
        self.assertEqual(self.raw['numword'][1], '&num_word NUMWORD')
        # Never turn newline + indentation into a mode-switching combo.
        combos = json.loads(renderer.outputs()['keymap-drawer/bykeeb.yaml'])['combos']
        self.assertTrue(all(not set(combo['p']) & set(range(30, 36)) for combo in combos))
        # Numeric thumbs are plain, so MEDIA entry is unavailable until exit.
        for name in ['numlft', 'numrht', 'numword']:
            self.assertEqual(self.raw[name][33], '&kp BSPC')
        self.assertEqual(len(self.layers), 9)

    def test_exit_clears_auto_state_and_locks_without_changing_base(self):
        body = self.node('num_exit')
        bindings = re.search(r'bindings\s*=\s*(.*?);', body, re.S)[1]
        self.assertEqual(re.findall(r'<([^>]+)>', bindings),
                         ['&macro_press', '&num_off NUMLFT', '&num_off NUMRHT',
                          '&num_off NUMWORD', '&macro_tap', '&kp ESC'])
        self.assertIn('wait-ms = <0>;', body)
        self.assertIn('tap-ms = <40>;', body)
        self.assertIn('toggle-mode = "off";', self.node('num_off'))
        self.assertIn('locking;', self.node('num_off'))
        self.assertEqual(self.raw['numword'][0], '&num_exit')
        self.assertEqual(self.raw['numrht'][0], '&num_exit')
        self.assertEqual(self.raw['numlft'][9], '&num_exit')

    def test_numbers_have_repeatable_editing_and_space_to_exit_numword(self):
        expected = ['&kp DEL', '&kp RET', '&kp TAB', '&kp BSPC', '&kp SPACE', '&kp DOT']
        for name in ['numlft', 'numrht', 'numword']:
            self.assertEqual(self.raw[name][30:], expected)
        self.assertEqual(self.raw['numrht'][15:30], self.raw['numword'][15:30])
        self.assertEqual(self.raw['nav'][33], '&kp BSPC')

    def test_sticky_shift_and_quote_are_reachable_on_both_bases(self):
        for name in ['default', 'colemak']:
            self.assertEqual(self.raw[name][35], '&skq LSHIFT')
            self.assertEqual(self.raw[name][34], '&lt SYM SPACE')
        self.assertEqual(self.raw['sym'][20], '&kp SQT')
        self.assertEqual(self.raw['sym'][30], '&kp DQT')
        self.assertEqual(self.raw['sym'][35], '&skq LSHIFT')
        self.assertEqual(self.raw['media'][3], '&kp CAPS')
        self.assertIn('quick-release;', self.node('skq'))
        self.assertIn('ignore-modifiers;', self.node('skq'))

    def test_backspace_repeat_is_local_to_backspace_and_preserves_system_access(self):
        self.assertIn('quick-tap-ms = <200>;', self.node('bsp'))
        self.assertIn('bindings = <&mo>, <&kp>;', self.node('bsp'))
        for name in ['default', 'colemak']:
            self.assertEqual(self.raw[name][33], '&bsp MEDIA BSPC')
        self.assertNotIn('&lt {', self.source)
        self.assertEqual(self.raw['media'][0], '&studio_unlock')
        self.assertEqual(self.raw['media'][15], '&bt BT_CLR')

    def test_editing_macros_send_only_expected_shortcuts(self):
        for node, expected in [
                ('select_word', ['LC(RIGHT)', 'LC(LEFT)', 'LC(LS(RIGHT))']),
                ('select_line', ['HOME', 'LS(END)']),
                ('clear_line', ['LC(E)', 'LC(U)'])]:
            self.assertEqual(re.findall(r'<&kp (\S+)>', self.node(node)), expected)
        self.assertEqual(self.raw['nav'][24], '&clear_line')
        self.assertEqual(self.raw['nav'][26:28], ['&select_word', '&select_line'])

    def test_host_shortcut_macros_use_ble_safe_pacing(self):
        # ZMK recommends >=30 ms wait and tap to avoid grouped/reordered BLE notifications.
        for node in ['select_word', 'select_line', 'clear_line']:
            for prop in ['wait-ms', 'tap-ms']:
                value = int(re.search(rf'{prop}\s*=\s*<(\d+)>;', self.node(node))[1])
                self.assertGreaterEqual(value, 30)

    def test_hrm_defaults_are_preserved(self):
        for node in ['hml', 'hmr']:
            body = self.node(node)
            for value in ['flavor = "balanced";', 'tapping-term-ms = <280>;',
                          'quick-tap-ms = <175>;', 'require-prior-idle-ms = <150>;',
                          'hold-trigger-on-release;']:
                self.assertIn(value, body)

    def test_layer_actions_reject_unknown_targets(self):
        for behavior in ['tog', 'num_word', 'num_off', 'to']:
            with self.assertRaisesRegex(ValueError, 'Unknown layer'):
                renderer.binding_key(f'&{behavior} MISSING', {}, list(self.layers))


if __name__ == '__main__':
    unittest.main()
