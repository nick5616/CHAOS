# CHAOS: The CounterStrike Highlight Analysis & Organization System

<img width="1279" height="479" alt="CHAOS Banner" src="https://github.com/user-attachments/assets/c53bc962-1c9b-43b3-8b65-645d2435f55e" />

**Finding the signal in the noise of 700GB of Counter-Strike 2 footage.**

---

## The Problem: Apathy in the Face of Absurdity

I've been playing Counter-Strike and making videos for over a decade. But with CS2, something felt... off. The motivation to create wasn't there. The game felt different, almost absurd, and the idea of sifting through a mountain of footage—over 700GB of raw, unfiltered gameplay captures—felt less like a creative process and more like an impossible chore. My library was a digital monument to my own procrastination.

This project is the answer to that feeling.

**CHAOS (CounterStrike Highlight Analysis & Organization System)** is a tool born from a need to bypass the grind and reconnect with the game's moments of brilliance. It's a system designed to embrace the chaotic, unstructured nature of my raw footage and impose order upon it. It uses AI to do the one thing I couldn't find the motivation to do: watch everything.

This repository documents my attempt to fight creative burnout with code, turning a terabyte of digital chaos into a curated library of meaningful highlights.

## 🔧 Setup & Installation

CHAOS is designed to work on both **Windows (with NVIDIA GPUs)** and **macOS (with Apple Silicon)**. The setup scripts will automatically handle the platform-specific dependencies for you.

### 🚀 Getting Started

**1. Clone the Repository:**
First, get the code onto your local machine.

```bash
git clone https://github.com/your-username/CHAOS.git
cd CHAOS
```

**2. Run the Setup Script for Your OS:**
The script will create a virtual environment (venv) and install all necessary dependencies, including the correct, hardware-accelerated version of PyTorch for your system.

On Windows:
Simply double-click the setup.bat file. A command window will open and handle the entire installation.

On macOS / Linux:
Open a terminal in the CHAOS folder, make the script executable, and then run it:

```bash
chmod +x setup.sh
./setup.sh
```

After the script finishes, your environment is ready.

### 🏃‍♀️ Usage

#### 1. Activate the Virtual Environment:

Before running any commands, you must activate the virtual environment in your terminal. You'll know it's active when you see (venv) at the start of your prompt.

On Windows:

```bash
.\venv\Scripts\activate
```

On macOS / Linux:

```bash
source venv/bin/activate
```

#### 2. Configure the System:

Open the config.yaml file and edit the settings, especially the captures_folder path, to match your system.

#### 3. Run the Pipeline:

Now you can execute the different stages of the CHAOS pipeline. On macOS/Linux, you may need to use python3 instead of python.

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
