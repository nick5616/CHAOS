"""
Every model file CHAOS downloads, so they can all be fetched up front (by setup
or the app at startup) instead of the first time you press Run.

Each file is saved exactly where the library that loads it looks, and checked
against that library's own checksum, so loading it later finds it in place
and never downloads.

    python -m chaos_lib.models    # download whatever the current config.yaml needs
"""

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass


@dataclass
class Model:
    label: str          # shown to the user
    url: str
    path: str           # where the loading library expects the file
    approx_mb: int      # for progress totals before the server reports a size
    algo: str           # checksum the loading library uses: 'sha256' or 'md5'
    digest: str
    zip_member: str | None = None   # EasyOCR ships each .pth inside a .zip

    def ready(self) -> bool:
        return os.path.exists(self.path)


_WHISPER_MB = {'tiny': 75, 'base': 142, 'small': 466, 'medium': 1460,
               'large-v1': 2950, 'large-v2': 2950, 'large-v3': 2950, 'large': 2950,
               'large-v3-turbo': 1550, 'turbo': 1550}


def whisper_model(name: str) -> Model:
    import whisper
    url = whisper._MODELS[name]
    # Same default location and checksum (the hash in the URL) as whisper.load_model.
    root = os.path.join(os.getenv('XDG_CACHE_HOME', os.path.join(os.path.expanduser('~'), '.cache')), 'whisper')
    return Model(f"Whisper speech model ({name})", url, os.path.join(root, os.path.basename(url)),
                 _WHISPER_MB.get(name.removesuffix('.en'), 500), 'sha256', url.split('/')[-2])


def easyocr_models() -> list:
    """The detector and English recognizer that easyocr.Reader(['en']) loads."""
    from easyocr.config import MODULE_PATH, detection_models, recognition_models
    out = []
    for label, spec, mb in [("Killfeed text detector", detection_models['craft'], 79),
                            ("Killfeed text reader", recognition_models['gen2']['english_g2'], 14)]:
        out.append(Model(label, spec['url'], os.path.join(MODULE_PATH, 'model', spec['filename']),
                         mb, 'md5', spec['md5sum'], zip_member=spec['filename']))
    return out


def laughter_model(data_folder: str) -> Model:
    from chaos_lib import laughter
    return Model("Laughter detector", laughter.CHECKPOINT_URL, laughter.checkpoint_path(data_folder),
                 360, 'sha256', laughter.CHECKPOINT_SHA256)


def required(config: dict) -> list:
    """Every model a pipeline run with this config will load."""
    from chaos_lib import moments, subtitles
    models = easyocr_models() + [whisper_model(config.get('whisper_model', 'base'))]
    caption = subtitles.caption_model_name(config)
    if caption:
        models.append(whisper_model(caption))
    if moments.enabled(config):
        models.append(laughter_model(config['data_folder']))
    return models


def missing(config: dict) -> list:
    return [m for m in required(config) if not m.ready()]


def fetch(model: Model, progress=None) -> str:
    """Download `model` if it isn't there yet and return its path.
    `progress(done_bytes, total_bytes)` is called while downloading. Downloads
    to a temp file and checks the checksum before moving it into place, so an
    interrupted or tampered download is never used."""
    if model.ready():
        return model.path
    folder = os.path.dirname(model.path)
    os.makedirs(folder, exist_ok=True)
    fd, part = tempfile.mkstemp(suffix='.part', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as f, urllib.request.urlopen(model.url, timeout=60) as resp:
            total = int(resp.headers.get('Content-Length') or 0) or model.approx_mb << 20
            done = 0
            while chunk := resp.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if model.zip_member:
            with zipfile.ZipFile(part) as zf, zf.open(model.zip_member) as src:
                data = src.read()
            with open(part, 'wb') as f:
                f.write(data)
        digest = hashlib.new(model.algo)
        with open(part, 'rb') as f:
            while chunk := f.read(1 << 20):
                digest.update(chunk)
        if digest.hexdigest() != model.digest:
            raise RuntimeError(f"{model.label} download is corrupt (checksum mismatch)")
        os.replace(part, model.path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return model.path


def main() -> int:
    import yaml
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    todo = missing(config)
    if not todo:
        print("     All models already downloaded.")
        return 0
    for model in todo:
        last = [-1]

        def progress(done, total, model=model):
            pct = min(100, done * 100 // total)
            if pct != last[0]:
                last[0] = pct
                print(f"\r     {model.label}: {pct:3d}% of {total >> 20} MB", end='', flush=True)
        try:
            fetch(model, progress)
            print()
        except Exception as e:
            print(f"\n     Failed: {e}")
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
