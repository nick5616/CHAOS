"""Working out the local player's name from their red killfeed rows.

Run: venv\\Scripts\\python -m unittest discover tests
"""

import unittest

from chaos_lib.analyzers import infer_player_name, _is_player_kill


def row(killer, victim, assister=None):
    return {'killer': killer, 'assister': assister, 'victim': victim}


def is_kill(r, name):
    return _is_player_kill(r, [name])


class InferPlayerName(unittest.TestCase):

    def test_multi_word_name_among_kills_deaths_and_assists(self):
        rows = [
            row("hot dog dog", "TheGoldenBoy"),
            row("hot dog dog", "JakeFromStateFarm"),
            row("hot dog dog", "ENKI559"),
            row("ENKI559", "hot dog dog"),                 # death
            row("Teammate", "Villain", "hot dog dog"),     # assist
        ]
        name = infer_player_name(rows)
        self.assertEqual(name, "hot dog dog")
        self.assertEqual([is_kill(r, name) for r in rows], [True, True, True, False, False])

    def test_tolerates_ocr_noise(self):
        rows = [row("excellent mage", "Bob"), row("excel1ent mage", "Alice"),
                row("excellent mage.", "Carol"), row("Dave", "excellent mage")]
        self.assertEqual(infer_player_name(rows).replace('.', ''), "excellent mage")

    def test_victim_name_does_not_join_the_players(self):
        # Seen with word-span matching: "McCree from Overwatch sky" matched
        # every row fuzzily and won for being longer.
        rows = [row("McCree from Overwatch", "sky"), row("McCree from Overwatch", "Floki"),
                row("McCree from Overwatch", "Xderlin")]
        self.assertEqual(infer_player_name(rows), "McCree from Overwatch")

    def test_bot_victims(self):
        rows = [row("hot dog dog", "BOT Hastings"), row("hot dog dog", "BOT Mayer"), row("hot dog dog", "BOT Opie")]
        self.assertEqual(infer_player_name(rows), "hot dog dog")

    def test_mostly_deaths(self):
        rows = [row("Alice", "mage"), row("Bob", "mage"), row("Carol", "mage"), row("mage", "Dave")]
        name = infer_player_name(rows)
        self.assertEqual(name, "mage")
        self.assertEqual([is_kill(r, name) for r in rows], [False, False, False, True])

    def test_too_few_rows(self):
        self.assertIsNone(infer_player_name([row("mage", "Bob"), row("mage", "Alice")]))

    def test_no_common_name(self):
        self.assertIsNone(infer_player_name([row("Alice", "Bob"), row("Carol", "Dave"),
                                             row("Erin", "Frank"), row("Gina", "Hank")]))

    def test_unknown_name_trusts_the_red_border(self):
        self.assertTrue(is_kill(row("Someone", "Victim"), "configured name"))


if __name__ == '__main__':
    unittest.main()
