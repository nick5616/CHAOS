# CHAOS: The CounterStrike Highlight Analysis & Organization System

<img width="1279" height="479" alt="Screenshot 2025-09-21 at 8 41 03 PM" src="https://github.com/user-attachments/assets/c53bc962-1c9b-43b3-8b65-645d2435f55e" />
<!-- Optional: A glitchy, chaotic banner would fit perfectly -->

**Finding the signal in the noise of 700GB of Counter-Strike 2 footage.**

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
    *   It will automatically install all the required packages from `requirements.txt`.
3.  Once it's finished, you're ready to go!

### 💻 Manual Setup Instructions

If you prefer to set up the project manually or are not on Windows, follow these steps in your terminal.

**1. Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/CHAOS.git
   cd CHAOS
   ```

**2. Create the Virtual Environment:**

```bash
python -m venv venv
```
3. Activate the Virtual Environment:

On Windows (Command Prompt or PowerShell):
```bash
.\venv\Scripts\activate
```
On macOS/Linux:
```bash
source venv/bin/activate
```
You'll know it worked when you see (venv) at the beginning of your terminal prompt.

4. Install Dependencies:

```bash
pip install -r requirements.txt
```
### 🏃‍♀️ Usage
Before running the main script, always make sure your virtual environment is active! (You should see (venv) in your terminal prompt).

Fill out your specific paths and settings in the config.yaml file first. Then, run the stages of the pipeline:

#### Run the entire pipeline from start to finish
```bash
python main.py all
```
#### Or run stages individually
```bash python main.py ingest
python main.py analyze
python main.py correlate
python main.py summary
python main.py clip
```

(Additional setup for PyTorch with CUDA may be required depending on your system)
