"""Voice-chat moment detection and its merge with kill clips, on hand-built events.

Run: venv\\Scripts\\python -m unittest discover tests
"""

import copy
import unittest

from chaos_lib import correlator, moments

VIDEO = 'clip.mp4'

CONFIG = {
    'data_folder': './data',
    'clip_pre_buffer_seconds': 10,
    'clip_post_buffer_seconds': 6,
    'scoring_weights': {'kill': 10, 'multi_kill_bonus': 15, 'team_hype_voice': 20, 'enemy_rage_chat': 25,
                        'audio_spike': 5, 'headshot_bonus': 50, 'smoke_kill_bonus': 40, 'banter': 20},
    'moments': {'mode': 'conversations'},
}

# The exchange from imthehokagebitch.mp4, as Whisper segments
NARUTO = [
    (55.0, 58.6, "Naruto Uzumaki, you're my best friend, I love you bro."),
    (59.0, 60.4, "Do you have a mic? Please."),
    (62.2, 63.6, "No, he doesn't have a mic."),
    (64.0, 66.5, "Well that's not good. That's not good at all."),
    (67.0, 68.6, "Yeah, not very Naruto, honestly."),
    (69.0, 71.8, "Nah, I feel like Naruto would definitely have a mic."),
    (72.0, 72.8, "For sure!"),
    (73.0, 74.0, "Believe it!"),
    (78.0, 80.6, "Naruto! Me and you died to the same guy, bruh."),
    (81.0, 84.9, "Only difference is I killed two, right? I'm the hokage, bitch."),
    (85.5, 87.4, "And I'm the kazekage, bitch."),
]

# Plain chatter: enough back-and-forth to be a conversation, nothing funny about it
CHATTER = [
    (300.0 + i * 3.5, 302.8 + i * 3.5, text) for i, text in enumerate([
        "So what are you doing this weekend.",
        "Probably going to visit my parents.",
        "Oh nice, where do they live.",
        "About two hours north of the city.",
        "That sounds pleasant enough.",
        "Yeah the drive is easy.",
    ])
]

CALLOUTS = [
    (500.0 + i * 3.0, 502.5 + i * 3.0, text) for i, text in enumerate([
        "One B site, he's low.",
        "Rotate, rotate, they're pushing ramp.",
        "Flash mid, I'm holding A site.",
        "He's one, he's B, planting.",
        "Molly the bomb, defuse is on.",
        "Last one, AWP connector.",
    ])
]


def voice(segments, speaker=None):
    return [{'source_video': VIDEO, 'timestamp_seconds': s, 'type': 'voice',
             'details': {'text': t, 'start': s, 'end': e, 'speaker': speaker, 'words': []}}
            for s, e, t in segments]


def info(duration):
    return [{'source_video': VIDEO, 'timestamp_seconds': 0.0, 'type': 'audio_info',
             'details': {'version': 2, 'duration': duration, 'tracks': 1, 'laughter': True}}]


def laugh(start, end):
    return [{'source_video': VIDEO, 'timestamp_seconds': start, 'type': 'laughter',
             'details': {'start': start, 'end': end, 'peak': start, 'confidence': 0.08, 'weight': end - start}}]


def kill(ts):
    return [{'source_video': VIDEO, 'timestamp_seconds': ts, 'type': 'kill',
             'details': {'raw_text': 'me AK victim', 'detected_player': 'me', 'assister': None,
                         'victim': 'victim', 'isHeadshot': False, 'throughSmoke': False}}]


def config(mode='conversations'):
    c = copy.deepcopy(CONFIG)
    c['moments']['mode'] = mode
    return c


def covers(clip, start, end):
    return clip['clip_start'] <= start and clip['clip_end'] >= end


class FindMomentsTest(unittest.TestCase):

    def test_naruto_bit_with_laughter_is_funny(self):
        events = info(900) + voice(NARUTO) + laugh(84.5, 85.5)
        timeline = []
        found = moments.find_moments(VIDEO, events, config('funny'), timeline)
        funny = [m for m in found if m['kind'] == 'funny']
        self.assertTrue(funny)
        self.assertTrue(any(covers(m, 81, 87) for m in funny), funny)
        self.assertIn('laughter', funny[0]['tags'] + funny[-1]['tags'])
        # "Naruto" four times in the bit, nowhere else in the file
        self.assertTrue(any(r['repeats'] > 0 for r in timeline))

    def test_conversation_without_laughter(self):
        events = info(900) + voice(CHATTER)
        conv = moments.find_moments(VIDEO, events, config('conversations'))
        self.assertEqual([m['kind'] for m in conv], ['conversation'])
        self.assertTrue(covers(conv[0], 301, 318))
        self.assertEqual(moments.find_moments(VIDEO, events, config('funny')), [])

    def test_callouts_are_not_a_moment(self):
        events = info(900) + voice(CALLOUTS)
        self.assertEqual(moments.find_moments(VIDEO, events, config('conversations')), [])

    def test_mode_off(self):
        events = info(900) + voice(NARUTO) + laugh(84.5, 85.5)
        self.assertEqual(moments.find_moments(VIDEO, events, config('off')), [])

    def test_short_replay_always_gets_its_best_stretch(self):
        # Two quiet lines in a 2-minute instant replay: below every threshold,
        # but the player saved this file for a reason.
        events = info(120) + voice([(90.0, 92.0, "Wait, what was that."), (93.0, 94.5, "No idea.")])
        found = moments.find_moments(VIDEO, events, config('funny'))
        self.assertEqual(len(found), 1)
        self.assertIn('best_guess', found[0]['tags'])
        # ...unless it has kills, which already make its clips
        self.assertEqual(moments.find_moments(VIDEO, events + kill(30), config('funny')), [])

    def test_clip_bounds(self):
        events = info(900) + voice(NARUTO) + laugh(84.5, 85.5)
        for m in moments.find_moments(VIDEO, events, config()):
            self.assertGreaterEqual(m['clip_end'] - m['clip_start'], 8)
            self.assertLessEqual(m['clip_end'] - m['clip_start'], 60)


class CorrelateTest(unittest.TestCase):

    def test_kill_and_funny_moment_merge(self):
        events = info(900) + voice(NARUTO) + laugh(84.5, 85.5) + kill(83)
        clips = correlator.correlate_video_events(VIDEO, events, config('funny'))
        merged = [c for c in clips if c['clip_start'] < 83 < c['clip_end']]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['kind'], 'kill')
        self.assertIn('funny', merged[0]['tags'])
        # Merged clips carry every source window's events (subtitles need them)
        types = {e['type'] for e in merged[0]['events_in_window']}
        self.assertTrue({'kill', 'voice', 'laughter'} <= types)

    def test_conversation_dropped_where_a_clip_exists(self):
        events = info(900) + voice(CHATTER) + kill(310)
        clips = correlator.correlate_video_events(VIDEO, events, config('conversations'))
        self.assertEqual([c['kind'] for c in clips], ['kill'])


if __name__ == '__main__':
    unittest.main()
