#!/usr/bin/env bash
# CHAOS setup for macOS / Linux. Re-run any time to repair or update.
# Finds Python 3.10+, then hands off to scripts/install.py (arguments are passed through).

cd "$(dirname "$0")" || exit 1

find_python() {
    # 3.12 first: it's what CHAOS is developed against and every dependency has wheels for it.
    for cmd in python3.12 python3.11 python3.13 python3.10 python3; do
        if command -v "$cmd" >/dev/null 2>&1 &&
           [ "$("$cmd" -c 'import sys; print(sys.version_info >= (3, 10))' 2>/dev/null)" = "True" ]; then
            echo "$cmd"
            return
        fi
    done
}

PYTHON="$(find_python)"
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ not found."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Install it with Homebrew (brew install python@3.12) or from https://www.python.org/downloads/"
    else
        echo "Install it with your package manager, e.g.: sudo apt install python3 python3-venv"
    fi
    exit 1
fi

# Debian/Ubuntu ship venv separately from python3.
if ! "$PYTHON" -c 'import ensurepip, venv' >/dev/null 2>&1; then
    echo "ERROR: $PYTHON is missing the venv module."
    echo "On Debian/Ubuntu: sudo apt install python3-venv"
    exit 1
fi

exec "$PYTHON" scripts/install.py "$@"
