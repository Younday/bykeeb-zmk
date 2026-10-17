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


if __name__ == '__main__':
    unittest.main()
