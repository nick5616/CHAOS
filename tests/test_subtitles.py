"""Cue building and subtitle file formats.

Run: venv\\Scripts\\python -m unittest discover tests
"""

import os
import tempfile
import unittest
from pathlib import Path

from chaos_lib import subtitles


def seg(text, start, speaker=None, word_s=0.3):
    words = [[w, round(start + i * word_s, 2), round(start + (i + 1) * word_s, 2)]
             for i, w in enumerate(text.split())]
    return {'text': text, 'start': start, 'end': words[-1][2], 'speaker': speaker, 'words': words}


class CueTest(unittest.TestCase):

    def test_times_are_relative_to_the_clip(self):
        cues = subtitles.build_cues([seg("I'm the hokage, bitch.", 113.2)], clip_start=100.0, clip_len=19.0)
        self.assertEqual(len(cues), 1)
        self.assertAlmostEqual(cues[0].start, 13.2, places=2)
        self.assertEqual(cues[0].text, "I'm the hokage, bitch.")

    def test_long_speech_splits_into_short_cues(self):
        text = ("Naruto Uzumaki, you're my best friend, I love you bro. Do you have a mic? "
                "Please, because that would be really really good for all of us on this team right now")
        cues = subtitles.build_cues([seg(text, 0.0)], 0.0, 60.0)
        self.assertGreater(len(cues), 2)
        for cue in cues:
            self.assertLessEqual(len(cue.text), subtitles.MAX_LINE_CHARS * subtitles.MAX_LINES)
            self.assertLessEqual(cue.end - cue.start, subtitles.MAX_CUE_S + 0.5)
        # Sentences end cues: no cue runs on past "bro."
        self.assertTrue(any(c.text.endswith('bro.') for c in cues))

    def test_speakers_keep_separate_cues(self):
        cues = subtitles.build_cues([seg("Do you have a mic?", 1.0, 'others'),
                                     seg("No he doesn't", 1.5, 'me')], 0.0, 10.0)
        self.assertEqual(sorted(c.speaker for c in cues), ['me', 'others'])

    def test_cues_outside_the_clip_are_dropped(self):
        cues = subtitles.build_cues([seg("before", 1.0), seg("inside", 12.0), seg("after", 40.0)], 10.0, 20.0)
        self.assertEqual([c.text for c in cues], ['inside'])

    def test_segments_without_word_timestamps(self):
        segment = {'text': 'old cached line without words', 'start': 5.0, 'end': 7.0}
        cues = subtitles.build_cues([segment], 0.0, 10.0)
        self.assertEqual(' '.join(c.text for c in cues), segment['text'])

    def test_caption_transcript_preferred_for_its_window(self):
        events = [
            {'type': 'voice', 'details': {'text': 'hotel gay bitch', 'start': 113.0, 'end': 115.0}},
            {'type': 'caption', 'details': {'text': 'hokage, bitch', 'start': 113.0, 'end': 115.0,
                                            'window': [100.0, 119.0]}},
        ]
        self.assertEqual([s['text'] for s in subtitles.segments_for_clip(events, 100.0, 119.0)], ['hokage, bitch'])
        # A clip whose window the captions weren't made for falls back to the voice transcript
        self.assertEqual([s['text'] for s in subtitles.segments_for_clip(events, 110.0, 140.0)], ['hotel gay bitch'])

    def test_wrap_balances_two_lines(self):
        lines = subtitles.wrap("No, I feel like Naruto would definitely have a mic.")
        self.assertEqual(len(lines), 2)
        self.assertLess(abs(len(lines[0]) - len(lines[1])), 10)


class FormatTest(unittest.TestCase):

    def test_srt_and_ass(self):
        cues = [subtitles.Cue(1.5, 3.25, "I'm the {hokage}, bitch.", 'me'),
                subtitles.Cue(3661.0, 3662.0, 'And I\'m the kazekage', None)]
        with tempfile.TemporaryDirectory() as tmp:
            srt, ass = os.path.join(tmp, 'a.srt'), os.path.join(tmp, 'a.ass')
            subtitles.write_srt(cues, srt)
            subtitles.write_ass(cues, ass, 1920, 1080)
            srt_text = Path(srt).read_text(encoding='utf-8')
            ass_text = Path(ass).read_text(encoding='utf-8')
        self.assertIn('00:00:01,500 --> 00:00:03,250', srt_text)
        self.assertIn('01:01:01,000 --> 01:01:02,000', srt_text)
        self.assertIn('Dialogue: 0,0:00:01.50,0:00:03.25,Me,', ass_text)
        self.assertNotIn('{hokage}', ass_text)  # braces would be read as override tags


class OptionsTest(unittest.TestCase):

    def test_caption_model(self):
        self.assertIsNone(subtitles.caption_model_name({'subtitles': {'enabled': False}}))
        self.assertEqual(subtitles.caption_model_name({'subtitles': {'enabled': True}, 'whisper_model': 'base'}),
                         'small')
        # Same model as the whole-file pass: nothing to redo
        self.assertIsNone(subtitles.caption_model_name(
            {'subtitles': {'enabled': True, 'model': 'base'}, 'whisper_model': 'base'}))


if __name__ == '__main__':
    unittest.main()
