"""
Laughter, excitement (shouting, yelling, cheering) and speech detection.

Uses PANNs Cnn14_16k (Kong et al. 2020, https://github.com/qiuqiangkong/audioset_tagging_cnn,
MIT license), an AudioSet tagger trained on 527 sound classes. The model class
below is a trimmed copy of `Cnn14_16k` from that repo's pytorch/models.py. The
log-mel front end is rebuilt with torch.stft plus the mel matrix stored in the
checkpoint, instead of depending on torchlibrosa; it computes the same features.

The model takes 16 kHz audio, the same rate we already decode for Whisper, so
it runs on that array with no second decode. It scores overlapping 2 s
windows; contiguous runs of windows above a threshold become one event.

Thresholds are low on purpose: AudioSet probabilities for a laugh mixed under
gunfire and teammates talking are small (a real giggle in a ShadowPlay
recording scored 0.08), but silence and plain speech sit near 0.001.

Its Speech class doubles as a voice activity detector that is steadier than
Whisper's segments (Whisper drops or invents lines from run to run on noisy
game audio): talking scores 0.4-0.9, gameplay without talking ~0.03.

The checkpoint (~360 MB) is downloaded once into <data_folder>/models/.
"""

import os
import time

import numpy as np

SAMPLE_RATE = 16000
CHECKPOINT_NAME = 'Cnn14_16k_mAP=0.438.pth'
CHECKPOINT_URL = 'https://zenodo.org/record/3987831/files/Cnn14_16k_mAP%3D0.438.pth?download=1'
# The checkpoint pickles numpy arrays, so it can't load with torch's
# weights_only mode; pinning its hash is what makes the full unpickle safe.
CHECKPOINT_SHA256 = 'e2ee543a27919542c2ea03eabaa70b24dcd4e6c8e05621de6b67a94e4c5058e6'

# AudioSet class indices (metadata/class_labels_indices.csv in the PANNs repo).
LAUGH_CLASSES = (16, 17, 18, 19, 20, 21)   # Laughter, Baby laughter, Giggle, Snicker, Belly laugh, Chuckle/chortle
EXCITE_CLASSES = (8, 10, 11, 14, 66)       # Shout, Whoop, Yell, Screaming, Cheering
SPEECH_CLASSES = (0, 1, 2, 4)              # Speech, Male speech, Female speech, Conversation
SPEECH_THRESHOLD = 0.3

WINDOW_S = 2.0
_BATCH = 8  # measured on CUDA: 683 MB total at 8 vs 828 MB at 32, and no slower


def checkpoint_path(data_folder: str) -> str:
    return os.path.join(data_folder, 'models', CHECKPOINT_NAME)


def ensure_checkpoint(data_folder: str, progress=None) -> str:
    """Download the checkpoint if it isn't there yet. `progress(done_bytes, total_bytes)`
    is called while downloading. Writes to a .part file and checks its hash
    first, so an interrupted or tampered download is never used."""
    from chaos_lib import models
    return models.fetch(models.laughter_model(data_folder), progress)


def _build_model():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class ConvBlock(nn.Module):
        def __init__(self, in_channels, out_channels):
            super().__init__()
            self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False)
            self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False)
            self.bn1 = nn.BatchNorm2d(out_channels)
            self.bn2 = nn.BatchNorm2d(out_channels)

        def forward(self, x, pool_size):
            x = F.relu_(self.bn1(self.conv1(x)))
            x = F.relu_(self.bn2(self.conv2(x)))
            return F.avg_pool2d(x, kernel_size=pool_size)

    class Cnn14_16k(nn.Module):
        n_fft, hop, mel_bins = 512, 160, 64

        def __init__(self):
            super().__init__()
            self.register_buffer('window', torch.hann_window(self.n_fft))
            self.register_buffer('melW', torch.zeros(self.n_fft // 2 + 1, self.mel_bins))
            self.bn0 = nn.BatchNorm2d(64)
            self.conv_block1 = ConvBlock(1, 64)
            self.conv_block2 = ConvBlock(64, 128)
            self.conv_block3 = ConvBlock(128, 256)
            self.conv_block4 = ConvBlock(256, 512)
            self.conv_block5 = ConvBlock(512, 1024)
            self.conv_block6 = ConvBlock(1024, 2048)
            self.fc1 = nn.Linear(2048, 2048)
            self.fc_audioset = nn.Linear(2048, 527)

        def forward(self, wav):
            # (batch, samples) -> log-mel (batch, 1, frames, 64), as torchlibrosa computes it
            spec = torch.stft(wav, self.n_fft, self.hop, self.n_fft, self.window,
                              center=True, pad_mode='reflect', return_complex=True).abs() ** 2
            mel = torch.matmul(spec.transpose(1, 2), self.melW)
            x = (10.0 * torch.log10(torch.clamp(mel, min=1e-10))).unsqueeze(1)
            x = self.bn0(x.transpose(1, 3)).transpose(1, 3)
            for block, pool in ((self.conv_block1, (2, 2)), (self.conv_block2, (2, 2)),
                                (self.conv_block3, (2, 2)), (self.conv_block4, (2, 2)),
                                (self.conv_block5, (2, 2)), (self.conv_block6, (1, 1))):
                x = block(x, pool)
            x = torch.mean(x, dim=3)
            x = torch.max(x, dim=2)[0] + torch.mean(x, dim=2)
            x = F.relu_(self.fc1(x))
            return torch.sigmoid(self.fc_audioset(x))

    return Cnn14_16k()


def load_model(data_folder: str, device: str = 'cpu'):
    """Load the tagger, downloading the checkpoint first if needed."""
    import torch
    state = torch.load(ensure_checkpoint(data_folder), map_location='cpu', weights_only=False)['model']
    model = _build_model()
    # The checkpoint's STFT conv weights are replaced by torch.stft; its mel
    # matrix and every learned layer load as-is.
    state = {k.replace('logmel_extractor.', ''): v for k, v in state.items()
             if not k.startswith(('spectrogram_extractor.', 'spec_augmenter.'))}
    missing = set(model.load_state_dict(state, strict=False).missing_keys) - {'window'}
    if missing:
        raise RuntimeError(f"Laughter model checkpoint is missing {sorted(missing)[:5]}")
    return model.to(device).eval()


def score_windows(model, audio: np.ndarray, hop_s: float, yield_fn=None) -> tuple:
    """(centers, laugh, excite, speech): window centers in seconds and the
    highest laughter / excitement / speech class probability in each 2 s window."""
    import torch
    win = int(WINDOW_S * SAMPLE_RATE)
    hop = int(hop_s * SAMPLE_RATE)
    if len(audio) < win:
        audio = np.pad(audio, (0, win - len(audio)))
    starts = np.arange(0, len(audio) - win + 1, hop)
    device = next(model.parameters()).device
    laugh, excite, speech = [], [], []
    with torch.inference_mode():
        for i in range(0, len(starts), _BATCH):
            t0 = time.perf_counter()
            batch = np.stack([audio[s:s + win] for s in starts[i:i + _BATCH]])
            probs = model(torch.from_numpy(batch).float().to(device)).cpu().numpy()
            laugh.append(probs[:, LAUGH_CLASSES].max(axis=1))
            excite.append(probs[:, EXCITE_CLASSES].max(axis=1))
            speech.append(probs[:, SPEECH_CLASSES].max(axis=1))
            if yield_fn:
                yield_fn(time.perf_counter() - t0)
    centers = (starts + win / 2) / SAMPLE_RATE
    return centers, np.concatenate(laugh), np.concatenate(excite), np.concatenate(speech)


def contiguous_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index pairs of each run of True values."""
    edges = np.flatnonzero(np.diff(np.concatenate(([0], mask.astype(np.int8), [0]))))
    return list(zip(edges[::2], edges[1::2]))


def detect(model, audio: np.ndarray, video_path: str, laugh_threshold: float = 0.05,
           excite_threshold: float = 0.2, hop_s: float = 0.5, yield_fn=None) -> list:
    """`laughter`, `excitement` and `speech` events, one per run of windows above threshold."""
    centers, laugh, excite, speech = score_windows(model, audio, hop_s, yield_fn)
    events = []
    for kind, probs, threshold in (('laughter', laugh, laugh_threshold),
                                   ('excitement', excite, excite_threshold),
                                   ('speech', speech, SPEECH_THRESHOLD)):
        for a, b in contiguous_runs(probs >= threshold):
            peak = a + int(np.argmax(probs[a:b]))
            events.append({
                "source_video": video_path,
                "timestamp_seconds": float(centers[a] - hop_s / 2),
                "type": kind,
                "details": {
                    "start": float(centers[a] - hop_s / 2),
                    "end": float(centers[b - 1] + hop_s / 2),
                    "peak": float(centers[peak]),
                    "confidence": float(probs[peak]),
                    # Seconds of the run. Not weighted by probability: under game
                    # audio real laughs score only ~0.05-0.1 (silence ~0.001).
                    "weight": float((b - a) * hop_s),
                },
            })
    return events
