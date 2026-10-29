"""
Display formatting shared by the views.
"""

import os
import re

# CS2 / ShadowPlay recordings are named "Counter-strike 2 2024.01.07 - 14.12.05.13.DVR.mp4";
# the date and time are the only part that tells two recordings apart.
_RECORDING_STAMP = re.compile(r"(\d{4})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})")


def recording_title(path: str) -> str:
    """'2024-01-07  14:12' for a dated recording, else the file name."""
    name = os.path.splitext(os.path.basename(path))[0]
    m = _RECORDING_STAMP.search(name)
    if m:
        y, mo, d, h, mi = m.groups()
        return f"{y}-{mo}-{d}  {h}:{mi}"
    return name


def fmt_clock(secs: float) -> str:
    """Seconds as m:ss, or h:mm:ss from an hour up."""
    secs = int(round(secs))
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"
