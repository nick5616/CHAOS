"""
Voice-chat moments worth clipping, found without an LLM.

Every second of a video gets cheap signals from events the analysis already
produced: how much of it is speech and how many separate lines start in it
(Whisper segments, and the tagger's speech runs, which stay put when Whisper
drops lines), laughter and yelling (PANNs tagger), loudness spikes, and
what the words look like: ! and ?, "haha", slang, words that keep coming back
in one stretch but are rare in the rest of the file (a running bit: "Naruto"
four times in twenty seconds), and CS callouts, which mean tactical talk
rather than banter. A sliding window sums them into a banter score.

Two kinds of moment come out:
  conversation  sustained back-and-forth (enough lines, enough of the window
                spoken, not mostly callouts). Needs no laughter or keywords:
                plenty of funny exchanges are deadpan. Meant to be skimmed.
  funny         a conversation-or-reaction whose banter score clears min_score.

Mode `off` finds neither, `funny` only the second, `conversations` both.

ShadowPlay instant replays are saved *because* something just happened, so a
short file with no kills always yields its best-scoring stretch (leaning
toward the end of the file) even below the threshold.
"""

import math
import re

from thefuzz import fuzz

MODES = ('off', 'funny', 'conversations')

DEFAULTS = {
    'mode': 'conversations',
    'min_score': 1.0,
    'min_turns': 4,
    'min_speech_coverage': 0.4,
    'window_seconds': 20,
    'short_file_seconds': 300,
    'min_clip_seconds': 8,
    'max_clip_seconds': 60,
    'laughter_threshold': 0.05,
    'excitement_threshold': 0.2,
    'slang_words': ['bro', 'bruh', 'dude', 'yo', 'bitch', 'fuck', 'fucking', 'shit', 'damn', 'holy',
                    'crazy', 'insane', 'no way', 'oh my god', 'what the', 'wtf', 'believe it', 'lmao', 'lol'],
    'callout_words': ['a site', 'b site', 'mid', 'ramp', 'connector', 'catwalk', 'banana', 'apps', 'heaven',
                      'pit', 'jungle', 'palace', 'rotate', 'rotating', 'flash', 'flashing', 'smoke', 'molly',
                      'nade', 'one hp', 'he\'s low', 'he\'s one', 'lit', 'tagged', 'planting', 'defusing',
                      'defuse', 'eco', 'force buy', 'bomb', 'rush', 'pushing', 'holding', 'peek', 'awp',
                      'last one', 'two left', 'three left', 'he\'s b', 'he\'s a'],
}

# What each signal is worth in banter points. min_score 1.0 is about a
# second of laughter, or a running bit plus a few exclamations.
W_LAUGH = 1.0     # per second of laughter
W_EXCITE = 0.4    # per second of shouting/yelling/cheering
W_SPIKE = 0.1     # per loudness spike (at most three count)
W_REPEAT = 0.3    # per repeat, past the second, of a running-bit word
W_LEX = 0.15      # per !, ?, laugh word or slang word
W_LAUGH_WORD = 0.3
W_CALLOUT = 0.25  # per callout: tactical talk, not banter
W_CROSS = 0.3     # the player and others both talking (separate mic track only)
W_TURN = 0.05     # per line spoken

SPEECH_GAP_S = 4.0    # silence this long ends a conversation (mid-round replies often take 3-4 s)
PAD_BEFORE_S = 1.0
PAD_AFTER_S = 1.5
REPLAY_END_BIAS = 0.25  # short files: the end of the file scores up to 25% higher
CONVERSATIONS_PER_MINUTE = 1 / 3

_LAUGH_WORD = re.compile(r"\b(?:a?ha(?:ha)+h?|he(?:he)+h?|hah|lol|lmao|lmfao|rofl)\b")
_TOKEN = re.compile(r"[a-z][a-z']+")

# Function words and filler that repeat in any conversation, so their
# repetition says nothing about a running bit.
_STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each
few for from further get got gotta gonna had hadn't has hasn't have haven't having he he'd he'll he's her here
here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself just
let's like me more most mustn't my myself no nor not now of off oh ok okay on once one only or other ought our
ours ourselves out over own really right same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they they'd they'll they're they've this
those through to too under until up uh um very wanna was wasn't we we'd we'll we're we've well were weren't what
what's when when's where where's which while who who's whom why why's will with won't would wouldn't yeah yes
yep you you'd you'll you're you've your yours yourself yourselves guy guys man go going gone know think thing
things see look want say said come came make made take good nice way time actually literally kind sort mean
something anything everything nothing even still back there'll alright hey hmm huh nah wait
""".split())


def mode(config: dict) -> str:
    m = (config.get('moments') or {}).get('mode', DEFAULTS['mode'])
    return m if m in MODES else DEFAULTS['mode']


def enabled(config: dict) -> bool:
    return mode(config) != 'off'


def _settings(config: dict) -> dict:
    return {**DEFAULTS, **(config.get('moments') or {})}


def _phrase_pattern(phrases: list) -> re.Pattern | None:
    phrases = [p.strip().lower() for p in phrases if p and p.strip()]
    if not phrases:
        return None
    return re.compile(r"\b(?:" + '|'.join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + r")\b")


def _group_tokens(tokens: set) -> dict:
    """token -> group id. Near-identical spellings (Whisper isn't consistent:
    "naruto"/"narutos") and words sharing a distinctive ending ("hokage" /
    "kazekage") count as the same word."""
    groups: dict = {}
    reps: list = []
    for tok in sorted(tokens, key=len):
        for gid, rep in enumerate(reps):
            if len(tok) >= 4 and len(rep) >= 4 and (
                    fuzz.ratio(tok, rep) >= 85
                    or (len(rep) >= 6 and len(tok) >= 6 and tok[-4:] == rep[-4:]
                        and tok[-4:] not in ('tion', 'ment', 'ness', 'ally', 'ting', 'ning', 'ying'))):
                groups[tok] = gid
                break
        else:
            groups[tok] = len(reps)
            reps.append(tok)
    return groups


def _duration(events: list) -> float:
    info = next((e['details'] for e in events if e.get('type') == 'audio_info'), None)
    if info and info.get('duration'):
        return float(info['duration'])
    ends = [e['details'].get('end', e['timestamp_seconds']) if isinstance(e.get('details'), dict)
            else e['timestamp_seconds'] for e in events]
    return float(max(ends, default=0.0))


def _spread(arr: list, start: float, end: float, total: float) -> None:
    """Add `total` to arr spread over the seconds [start, end) cover."""
    a, b = max(0, int(start)), min(len(arr), max(int(start) + 1, math.ceil(end)))
    if b <= a:
        return
    for t in range(a, b):
        arr[t] += total / (b - a)


def find_moments(video_path: str, events: list, config: dict, timeline: list | None = None) -> list:
    """Highlight specs (same shape the correlator makes, plus `kind` and
    `banter`) for this video's voice-chat moments. `timeline`, if given, gets
    one row of signals per window position, for tuning."""
    m = mode(config)
    if m == 'off':
        return []
    s = _settings(config)
    duration = _duration(events)
    T = int(math.ceil(duration))
    W = int(s['window_seconds'])
    if T <= 0:
        return []
    W = min(W, T)

    voice = sorted((e['details'] for e in events if e.get('type') == 'voice' and e['details'].get('text')),
                   key=lambda d: d['start'])
    laughs = [e['details'] for e in events if e.get('type') == 'laughter']
    speech_runs = sorted((e['details'] for e in events if e.get('type') == 'speech'), key=lambda d: d['start'])
    # Everything known to be talking, for growing a clip out to where talking stops
    talk = sorted([{'start': d['start'], 'end': d.get('end', d['start'] + 1)} for d in voice + speech_runs],
                  key=lambda d: d['start'])
    excites = [e['details'] for e in events if e.get('type') == 'excitement']
    spikes = [e['timestamp_seconds'] for e in events if e.get('type') == 'audio_spike']
    has_kills = any(e.get('type') == 'kill' for e in events)
    if not talk and not laughs:
        return []

    slang = _phrase_pattern(s['slang_words'])
    callouts = _phrase_pattern(s['callout_words'])

    # ---- per-second signals
    speech = [0.0] * T
    turns = [0] * T
    run_starts = [0] * T
    lex = [0.0] * T
    callout = [0] * T
    laugh = [0.0] * T
    excite = [0.0] * T
    spike = [0] * T
    me = [False] * T
    others = [False] * T
    seg_tokens = []  # (second, [tokens])

    for d in voice:
        start, end = d['start'], d.get('end', d['start'] + 1)
        sec = min(T - 1, max(0, int(start)))
        for t in range(max(0, int(start)), min(T, math.ceil(end))):
            speech[t] = min(1.0, speech[t] + max(0.0, min(end, t + 1) - max(start, t)))
            if d.get('speaker') == 'me':
                me[t] = True
            elif d.get('speaker') == 'others':
                others[t] = True
        turns[sec] += 1
        text = d['text'].lower()
        laugh_words = len(_LAUGH_WORD.findall(text))
        lex[sec] += W_LEX * (text.count('!') + text.count('?') + (len(slang.findall(text)) if slang else 0)) \
            + W_LAUGH_WORD * laugh_words
        callout[sec] += len(callouts.findall(text)) if callouts else 0
        seg_tokens.append((sec, [t for t in _TOKEN.findall(text) if t not in _STOPWORDS and len(t) >= 3]))
    for d in speech_runs:
        for t in range(max(0, int(d['start'])), min(T, math.ceil(d['end']))):
            speech[t] = max(speech[t], min(1.0, min(d['end'], t + 1) - max(d['start'], t)))
        run_starts[min(T - 1, max(0, int(d['start'])))] += 1
    for d in laughs:
        _spread(laugh, d['start'], d['end'], d.get('weight', d['end'] - d['start']))
    for d in excites:
        _spread(excite, d['start'], d['end'], d.get('weight', d['end'] - d['start']))
    for t in spikes:
        if 0 <= int(t) < T:
            spike[int(t)] += 1

    groups = _group_tokens({tok for _, toks in seg_tokens for tok in toks})
    file_counts: dict = {}
    for _, toks in seg_tokens:
        for tok in toks:
            file_counts[groups[tok]] = file_counts.get(groups[tok], 0) + 1

    # ---- sliding window
    windows = []
    for w0 in range(0, T - W + 1):
        w1 = w0 + W
        # Whisper lines, or separate bursts of speech if Whisper missed lines
        n_turns = max(sum(turns[w0:w1]), sum(run_starts[w0:w1]))
        counts: dict = {}
        for sec, toks in seg_tokens:
            if w0 <= sec < w1:
                for tok in toks:
                    counts[groups[tok]] = counts.get(groups[tok], 0) + 1
        # A running bit: said 3+ times here, and mostly here rather than all game long
        repeats = sum(c - 2 for g, c in counts.items() if c >= 3 and c >= 0.5 * file_counts[g])
        laugh_s, excite_s = sum(laugh[w0:w1]), sum(excite[w0:w1])
        n_callouts = sum(callout[w0:w1])
        cross = any(me[w0:w1]) and any(others[w0:w1])
        banter = (W_LAUGH * laugh_s + W_EXCITE * excite_s + W_SPIKE * min(3, sum(spike[w0:w1]))
                  + W_REPEAT * repeats + sum(lex[w0:w1]) + W_CROSS * cross + W_TURN * n_turns
                  - W_CALLOUT * n_callouts)
        coverage = sum(speech[w0:w1]) / W
        row = {
            'start': w0, 'end': w1, 'coverage': round(coverage, 2), 'turns': n_turns,
            'laugh': round(laugh_s, 2), 'excite': round(excite_s, 2), 'repeats': repeats,
            'lexical': round(sum(lex[w0:w1]), 2), 'callouts': n_callouts, 'banter': round(banter, 2),
            'conversation': (n_turns >= s['min_turns'] and coverage >= s['min_speech_coverage']
                             and n_callouts <= 0.5 * n_turns),
        }
        # Instant replays: the moment that made the player hit save is usually near the end
        bias = 1 + REPLAY_END_BIAS * ((w0 + W / 2) / T) if T <= s['short_file_seconds'] else 1.0
        row['rank'] = banter * bias
        windows.append(row)
        if timeline is not None:
            timeline.append(row)

    picked: list = []

    def expand(row) -> tuple[float, float]:
        """Grow a window out to where the talking around it stops."""
        a, b = float(row['start']), float(row['end'])
        inside = [d for d in talk if d['end'] > a and d['start'] < b]
        if inside:
            a, b = min(a, min(d['start'] for d in inside)), max(d['end'] for d in inside)
            for d in reversed(talk):
                if d['start'] < a and d['end'] >= a - SPEECH_GAP_S:
                    a = d['start']
            for d in talk:
                if d['start'] > b + SPEECH_GAP_S:
                    break
                b = max(b, d['end'])
        for d in laughs:  # let the laugh finish
            if d['start'] <= b + SPEECH_GAP_S and d['end'] > b:
                b = d['end']
        a, b = a - PAD_BEFORE_S, b + PAD_AFTER_S
        lo, hi = float(s['min_clip_seconds']), float(s['max_clip_seconds'])
        if b - a > hi:  # too long: keep the part around the window that scored
            centre = (row['start'] + row['end']) / 2
            a = max(a, min(centre - hi / 2, b - hi))
            b = a + hi
        if b - a < lo:
            pad = (lo - (b - a)) / 2
            a, b = a - pad, b + pad
        return max(0.0, a), min(float(duration), b)

    def take(row, kind, tags) -> bool:
        a, b = expand(row)
        if any(a < pb and pa < b for pa, pb, _ in picked):
            return False
        picked.append((a, b, (row, kind, tags)))
        return True

    by_rank = sorted(windows, key=lambda r: r['rank'], reverse=True)
    for row in by_rank:
        if row['banter'] >= s['min_score']:
            take(row, 'funny', [])

    if not picked and not has_kills and T <= s['short_file_seconds']:
        for row in by_rank:
            if row['turns'] >= 2 or row['laugh'] > 0:
                take(row, 'funny', ['best_guess'])
                break

    if m == 'conversations':
        cap = max(1, math.ceil(T / 60 * CONVERSATIONS_PER_MINUTE))
        n = 0
        for row in by_rank:
            if n >= cap:
                break
            if row['conversation'] and take(row, 'conversation', []):
                n += 1

    weight = (config.get('scoring_weights') or {}).get('banter', 20)
    out = []
    for a, b, (row, kind, tags) in sorted(picked, key=lambda p: p[0]):
        tags = list(tags) + (['funny'] if kind == 'funny' else ['conversation'])
        if row['laugh'] >= 0.5:
            tags.append('laughter')
        if row['repeats']:
            tags.append('running_bit')
        if row['excite'] >= 1:
            tags.append('yelling')
        out.append({
            'source_video': video_path,
            'clip_start': round(a, 2),
            'clip_end': round(b, 2),
            'score': round(weight * max(row['banter'], 0.0), 1),
            'banter': round(row['banter'], 2),
            'kind': kind,
            'tags': tags,
            'events_in_window': [e for e in events if not e.get('type', '').endswith('_info')
                                 and a <= e['timestamp_seconds'] <= b],
        })
    return out
