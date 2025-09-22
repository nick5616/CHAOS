# CHAOS: The CounterStrike Highlight Analysis & Organization System

![Project Banner](https://your-image-host.com/chaos_banner.png) <!-- Optional: A glitchy, chaotic banner would fit perfectly -->

**Finding the signal in the noise of 700GB of Counter-Strike 2 footage.**

---

## The Problem: Apathy in the Face of Absurdity

I've been playing Counter-Strike and making videos for over a decade. But with CS2, something felt... off. The motivation to create wasn't there. The game felt different, almost absurd, and the idea of sifting through a mountain of footage—over 700GB of raw, unfiltered gameplay captures—felt less like a creative process and more like an impossible chore. My library was a digital monument to my own procrastination.

This project is the answer to that feeling.

**CHAOS (CounterStrike Highlight Analysis & Organization System)** is a tool born from a need to bypass the grind and reconnect with the game's moments of brilliance. It's a system designed to embrace the chaotic, unstructured nature of my raw footage and impose order upon it. It uses AI to do the one thing I couldn't find the motivation to do: watch everything.

This repository documents my attempt to fight creative burnout with code, turning a terabyte of digital chaos into a curated library of meaningful highlights.

## ✨ The Method to the Madness

CHAOS is a multi-layered system that analyzes gameplay footage from different angles to build a complete picture of what happened in a clip, both on-screen and off.

-   **Deconstructing the Killfeed:** Uses OpenCV and EasyOCR to perform Optical Character Recognition on the killfeed, logging every kill and identifying killstreaks with cold, machine-like efficiency.
-   **Reading the Room (and the Rage):** The same OCR engine is pointed at the chat box. It then runs sentiment analysis on the text to find the moments of hype, praise from teammates, and—most importantly—salt from the enemy.
-   **Translating the Comms:** All audio is stripped from the videos and fed into OpenAI's Whisper, which generates a complete, time-stamped transcript of every voice communication. No funny comment or panicked callout is missed.
-   **Detecting the Pandemonium:** Beyond words, the system analyzes the audio waveform itself using `librosa`. It finds the moments of pure chaos—the shouting, the laughter, the keyboard smashes—by detecting sudden spikes in volume and pitch.
-   **The Order Engine:** This is the heart of CHAOS. A central script takes all these disparate data streams—kills, chat messages, transcripts, and audio spikes—and fuses them. It finds the correlations, boosting the score of a clip where a slick double-kill is followed by enemy rage in the chat and your teammates screaming in voice comms.
-   **Exporting the Order:** The final output is a clean, structured JSON file—a perfect map of the chaos, pointing to the exact start and end times of every highlight worth watching. This file becomes the blueprint for an FFmpeg script to automatically cut the final clips.

## 🛠️ Tech Stack

-   **Language:** Python
-   **Core Libraries:**
    -   **OpenCV:** For video frame processing.
    -   **EasyOCR:** For robust, GPU-accelerated text recognition.
    -   **Whisper (OpenAI):** For state-of-the-art audio transcription.
    -   **Librosa:** For audio feature extraction (detecting screams and laughter).
    -   **Pandas:** For managing and correlating the large datasets of events.
-   **Tooling:**
    -   **FFmpeg:** The command-line workhorse for all video/audio manipulation.
    -   **Git & GitHub:** For versioning the descent into madness.

## 📈 The Workflow: From Chaos to Clarity

1.  **Phase 1: Triage:** The system makes a quick first pass on all 700GB, using the most efficient analysis (killfeed OCR) to identify any video that contains a hint of action. This creates a "shortlist" of clips that deserve a closer look.
2.  **Phase 2: Deep Analysis:** The shortlisted videos are subjected to the full, computationally-expensive suite of tools: audio transcription, chat analysis, and waveform scanning.
3.  **Phase 3: Synthesis:** The Order Engine runs, correlating all events and assigning a `composite_score` to each potential highlight. The true gems—the moments of pure, unadulterated Counter-Strike—bubble to the top.
4.  **Phase 4: Execution:** The final, sorted JSON is used as a command list for FFmpeg, which executes the batch job of cutting every single highlight into its own file, ready for the final edit.

## 🔧 Setup & Installation

**Prerequisites:**
*   Python 3.9+
*   FFmpeg installed and available in your system's PATH.
*   An NVIDIA GPU with CUDA is strongly recommended. This isn't a job for a CPU.

**Installation:**

```bash
# Clone the madness
git clone https://github.com/your-username/CHAOS.git
cd CHAOS

# Create a virtual environment and install dependencies
pip install -r requirements.txt

# (Additional setup for PyTorch with CUDA may be required depending on your system)
