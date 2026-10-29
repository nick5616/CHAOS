# CHAOS: The CounterStrike Highlight Analysis & Organization System

<img width="1279" height="479" alt="CHAOS Banner" src="https://github.com/user-attachments/assets/c53bc962-1c9b-43b3-8b65-645d2435f55e" />

**Finding the signal in the noise of 700GB of Counter-Strike 2 footage.**

---

## The Problem: Apathy in the Face of Absurdity

I've been playing Counter-Strike and making videos for over a decade. But with CS2, something felt... off. The motivation to create wasn't there. The game felt different, almost absurd, and the idea of sifting through a mountain of footage—over 700GB of raw, unfiltered gameplay captures—felt less like a creative process and more like an impossible chore. My library was a digital monument to my own procrastination.

This project is the answer to that feeling.

**CHAOS (CounterStrike Highlight Analysis & Organization System)** is a tool born from a need to bypass the grind and reconnect with the game's moments of brilliance. It's a system designed to embrace the chaotic, unstructured nature of my raw footage and impose order upon it. It uses AI to do the one thing I couldn't find the motivation to do: watch everything.

This repository documents my attempt to fight creative burnout with code, turning a terabyte of digital chaos into a curated library of meaningful highlights.

## Install

Get the code, then run one script.

```bash
git clone https://github.com/your-username/CHAOS.git
cd CHAOS
```

| | |
|---|---|
| **Windows** | Double-click `setup.bat` |
| **macOS / Linux** | `./setup.sh` |

That's it. Setup will:

1. Find Python 3.10+ (on Windows, it installs Python 3.12 for you if needed).
2. Create a `venv` in the CHAOS folder.
3. Install the right PyTorch for your hardware: a CUDA build matched to your NVIDIA driver, Apple Silicon (MPS) on a Mac, or CPU-only otherwise.
4. Install the rest of the Python packages.
5. Install FFmpeg if it's missing (winget, Homebrew or your Linux package manager; on Windows it falls back to a portable copy in `bin\`).
6. Check that everything imports, and report whether you're running on GPU or CPU.
7. Add CHAOS to the Start Menu (Windows) or your applications menu (Linux).

The first run downloads a few GB, mostly PyTorch. Setup is safe to re-run: it skips anything already done, so run it again if something failed or after you install an NVIDIA driver to switch to the GPU build. On Windows, `setup.bat --desktop-shortcut` also puts a shortcut on the Desktop.

## Usage

Launch CHAOS from the Start Menu, or from the CHAOS folder:

```bash
venv\Scripts\python run_desktop_app.py     # Windows
venv/bin/python run_desktop_app.py         # macOS / Linux
```

On first launch, a setup wizard walks you through pointing CHAOS at your captures folder.

### Command line

The pipeline can also run headless. Activate the venv first (`venv\Scripts\activate` on Windows, `source venv/bin/activate` elsewhere), and set `captures_folder` in `config.yaml`.

Run the entire pipeline from start to finish:

```bash
python main.py all
```

Or run stages individually:

```bash
python main.py ingest
python main.py analyze
python main.py correlate
python main.py summary
python main.py clip
```

Debugging on a Single File:
Use the `--debug` flag to run a stage on only the first video in your manifest. This is essential for testing and tuning your settings.

```bash
python main.py analyze --debug
```
