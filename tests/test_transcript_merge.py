"""Merging the window and per-chunk caption transcripts.

Run: venv\\Scripts\\python -m unittest discover tests
"""

import unittest

from chaos_lib.analyzers import _best_transcript, _speech_chunks


def line(text, start, step=0.4):
    words = [[w, round(start + i * step, 2), round(start + (i + 1) * step, 2)] for i, w in enumerate(text.split())]
    return {'type': 'caption', 'timestamp_seconds': start,
            'details': {'text': text, 'start': start, 'end': words[-1][2], 'speaker': None, 'words': words}}


class MergeTest(unittest.TestCase):

    def test_each_chunk_takes_the_pass_that_heard_more(self):
        chunks = [[0.0, 5.0], [10.0, 15.0]]
        window = [line("I", 0.5), line("I'm the hokage, bitch.", 10.5)]
        chunked = [line("Naruto, you're my best friend bro.", 0.5), line("hotel", 10.5)]
        texts = [e['details']['text'] for e in _best_transcript(window, chunked, chunks)]
        self.assertEqual(texts, ["Naruto, you're my best friend bro.", "I'm the hokage, bitch."])

    def test_run_on_line_is_not_repeated(self):
        # The window pass ran two bursts together into one line; the chunk
        # pass heard the second burst better. Only the first burst's words of
        # the run-on line survive.
        chunks = [[0.0, 2.5], [2.5, 7.0]]
        window = [line("do you have a mic well that's not", 0.5)]
        chunked = [line("Well, that's not good. That's not good at all.", 3.0)]
        texts = [e['details']['text'] for e in _best_transcript(window, chunked, chunks)]
        self.assertEqual(texts, ["do you have a mic", "Well, that's not good. That's not good at all."])

    def test_speech_chunks_merge_and_split(self):
        runs = [{'start': 1.0, 'end': 3.0}, {'start': 4.0, 'end': 6.0}, {'start': 20.0, 'end': 50.0}]
        chunks = _speech_chunks(runs, 0.0, 60.0)
        self.assertEqual(chunks[0], [0.7, 6.3])
        self.assertTrue(all(b - a <= 12.0 + 1e-9 for a, b in chunks))
        self.assertAlmostEqual(chunks[-1][1], 50.3)


if __name__ == '__main__':
    unittest.main()
