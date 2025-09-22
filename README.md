# CHAOS: The CounterStrike Highlight Analysis & Organization System

<img width="1279" height="479" alt="Screenshot 2025-09-21 at 8 41 03 PM" src="https://github.com/user-attachments/assets/c53bc962-1c9b-43b3-8b65-645d2435f55e" />
<!-- Optional: A glitchy, chaotic banner would fit perfectly -->

**Finding the signal in the noise of 700GB of Counter-Strike 2 footage.**

---

---

## The Problem: Apathy in the Face of Absurdity

I've been playing Counter-Strike and making videos for over a decade. But with CS2, something felt... off. The motivation to create wasn't there. The game felt different, almost absurd, and the idea of sifting through a mountain of footage—over 700GB of raw, unfiltered gameplay captures—felt less like a creative process and more like an impossible chore. My library was a digital monument to my own procrastination.

This project is the answer to that feeling.

**CHAOS (CounterStrike Highlight Analysis & Organization System)** is a tool born from a need to bypass the grind and reconnect with the game's moments of brilliance. It's a system designed to embrace the chaotic, unstructured nature of my raw footage and impose order upon it. It uses AI to do the one thing I couldn't find the motivation to do: watch everything.

This repository documents my attempt to fight creative burnout with code, turning a terabyte of digital chaos into a curated library of meaningful highlights.

## 🔧 Setup & Installation

This project relies on a set of specific Python packages. To avoid conflicts with other Python projects on your system, we **strongly recommend** using a virtual environment. This creates an isolated "sandbox" for all of CHAOS's dependencies.

### 🚀 Automated Setup on Windows (Recommended)

For a simple, one-click setup on Windows, just run the `setup.bat` script included in the repository.

1.  **Double-click `setup.bat`**.
2.  A command window will open and guide you through the process:
    *   It will verify you have Python installed.
    *   It will create the virtual environment folder (`venv`).
    *   It will automatically install the required packages from `requirements.txt`.
3.  Once it's finished, you're ready to go!

### 💻 Manual Setup Instructions

If you prefer to set up the project manually or are not on Windows, follow these steps in your terminal.

**1. Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/CHAOS.git
   cd CHAOS
2. Create the Virtual Environment:

bash
python -m venv venv
3. Activate the Virtual Environment:

On Windows (Command Prompt or PowerShell):
bash
.\venv\Scripts\activate
On macOS/Linux:
bash
source venv/bin/activate
You'll know it worked when you see (venv) at the beginning of your terminal prompt.

4. Install Dependencies:

bash
pip install -r requirements.txt
This installs the base packages. See the next step for enabling GPU support.

5. 🚀 Activating GPU Acceleration (for NVIDIA Users)
The analysis process is 10-20x faster with a compatible NVIDIA GPU. If the setup script installed a CPU-only version, follow these steps to enable GPU support.

A. Check Your CUDA Driver Version:
Open a terminal and run this command:

bash
nvidia-smi
Look in the top-right corner for the CUDA Version (e.g., 12.1). This is the maximum version your driver supports.

B. Get the Correct PyTorch Command:
Go to the official PyTorch website: https://pytorch.org/get-started/locally/

Select the options that match your system (Stable, Windows, Pip, Python).
For "Compute Platform," choose the CUDA version that is less than or equal to the version from nvidia-smi. For example, if you have 12.1, choose CUDA 12.1.
The website will generate the correct installation command.
C. Install the GPU Version:
In your activated (venv) terminal, run the command from the PyTorch website. It will look like this (your URL may be different!):

bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
D. Verify:
Run this command to confirm your GPU is detected:

bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
If it prints CUDA available: True, you are ready to go!

🏃‍♀️ Usage
Before running the main script, always make sure your virtual environment is active! (You should see (venv) in your terminal prompt).

Fill out your specific paths and settings in the config.yaml file first. Then, run the stages of the pipeline:

Run the entire pipeline from start to finish
bash
python main.py all
Or run stages individually
bash
python main.py ingest
python main.py analyze
python main.py correlate
python main.py summary
python main.py clip
Debugging on a Single File
Use the --debug flag to run a stage on only the first video in your manifest. This is essential for testing.

bash
python main.py analyze --debug
text

---

This provides a much more robust and user-friendly experience, guiding you directly to the GPU fix without leaving the project's documentation.
Gemini 2.5 Pro

(Additional setup for PyTorch with CUDA may be required depending on your system)
