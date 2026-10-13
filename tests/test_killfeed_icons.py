"""Reading a killfeed row's structure and icons from its pixels.

Fixtures are red-bordered rows cropped from 1080p CS2 footage, plus one
higher-resolution screenshot carrying every modifier icon at once.

Run: venv\\Scripts\\python -m unittest discover tests
"""

import os
import unittest

import cv2

from chaos_lib.analyzers import _row_layout

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'killfeed_rows')


def flags(fixture):
    layout = _row_layout(cv2.imread(os.path.join(FIXTURES, fixture)))
    return {k for k, v in layout['flags'].items() if v}


class KillfeedIcons(unittest.TestCase):

    def test_headshot_only(self):
        # "McCree from Overwatch [revolver][headshot] A": was also flagged as through smoke
        self.assertEqual(flags('headshot.png'), {'isHeadshot'})

    def test_no_modifiers(self):
        self.assertEqual(flags('plain.png'), set())

    def test_wallbang(self):
        self.assertEqual(flags('wallbang.png'), {'wallbang'})
        self.assertEqual(flags('wallbang_headshot.png'), {'wallbang', 'isHeadshot'})

    def test_assist_row(self):
        # "killer + [GG] assister [revolver] victim": the '+' is not an icon,
        # but it does split the killer from the assister
        self.assertEqual(flags('assist.png'), set())
        layout = _row_layout(cv2.imread(os.path.join(FIXTURES, 'assist.png')))
        self.assertIsNotNone(layout['assister_img'])
        self.assertIsNone(_row_layout(cv2.imread(os.path.join(FIXTURES, 'headshot.png')))['assister_img'])

    def test_every_modifier(self):
        self.assertEqual(flags('blind_noscope_smoke_headshot.png'),
                         {'attackerBlind', 'noScope', 'throughSmoke', 'isHeadshot'})

    def test_killer_and_victim_crops_exclude_the_icons(self):
        layout = _row_layout(cv2.imread(os.path.join(FIXTURES, 'headshot.png')))
        # The victim is the single letter "A": a narrow crop, not the icons before it
        self.assertLess(layout['victim_img'].shape[1], 25)
        self.assertGreater(layout['killer_img'].shape[1], 100)


if __name__ == '__main__':
    unittest.main()
