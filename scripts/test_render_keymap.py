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
        output = self.changed_outputs(r'(tapping-term-ms\s*=\s*<)\d+', r'\g<1>320')
        self.assertIn('Left: hold 320 ms', output['docs/layout.html'])

    def test_studio_unlock_position(self):
        output = self.changed_outputs(r'&studio_unlock\s+&trans', '&trans &studio_unlock')
        self.assertIn('Hold Bksp and press W', output['docs/layout.html'])


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
                        ['nav', 'sym', 'func', 'media', 'numlft', 'numrht']))

        def resolve(position, active):
            return next(self.raw[name][position] for name in reversed(self.names)
                        if name in active and self.raw[name][position] != '&trans')

        self.assertEqual(resolve(11, ['default', 'colemak', 'nav']), '&kp LEFT')
        self.assertEqual(resolve(23, ['default', 'colemak', 'nav']), '&kp D')
        self.assertEqual(resolve(23, ['default', 'nav']), '&kp V')

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


if __name__ == '__main__':
    unittest.main()
