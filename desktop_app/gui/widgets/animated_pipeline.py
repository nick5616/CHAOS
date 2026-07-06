"""
Live job-board pipeline widget.

Shows one row per in-flight video. Each row displays the video's current
stage (ANALYZE / CORRELATE / CLIP) as a coloured pill, the filename, and a
shimmer sweep that indicates active work.  Rows fade out when the video
finishes.  An overall progress bar at the top tracks completed vs. total.
"""

import math

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
    QPainterPath, QLinearGradient,
)

# ---- stage styling -------------------------------------------------------
_STAGE_COLOR = {
    "analyze":   QColor("#3B82F6"),   # blue
    "correlate": QColor("#8B5CF6"),   # purple
    "clip":      QColor("#F97316"),   # orange
    "done":      QColor("#22C55E"),   # green
    "failed":    QColor("#EF4444"),   # red
    "ingest":    QColor("#6B7280"),   # gray
    "summary":   QColor("#6B7280"),
}
_STAGE_LABEL = {
    "analyze":   "ANALYZE",
    "correlate": "CORRELATE",
    "clip":      "CLIP",
    "done":      "DONE",
    "failed":    "FAILED",
    "ingest":    "INGEST",
    "summary":   "SUMMARY",
}
# shimmer sweep speed (fraction of row width per 16 ms tick)
_STAGE_SHIMMER_SPEED = {
    "analyze":   0.006,
    "correlate": 0.022,
    "clip":      0.013,
}

# ---- layout constants ----------------------------------------------------
_ROW_H    = 42
_PAD_X    = 14
_PAD_Y    = 10
_BAR_H    = 6
_PILL_W   = 80
_PILL_H   = 22
_PILL_R   = 5
_FADE_STEP = 0.04    # alpha reduction per tick when fading


# --------------------------------------------------------------------------

class _JobRow:
    __slots__ = ("name", "stage", "shimmer", "alpha", "fading")

    def __init__(self, name: str, stage: str):
        self.name     = name
        self.stage    = stage
        self.shimmer  = 0.0    # 0.0–1.0, wraps
        self.alpha    = 1.0    # 1.0 = opaque, fades to 0 when done
        self.fading   = False


# --------------------------------------------------------------------------

class AnimatedPipelineWidget(QWidget):
    """
    Live job board.  One row per in-flight video; rows fade out on completion.

    Signals to connect (from PipelineWorker):
        worker.job_started    → on_job_started(name, stage)
        worker.job_updated    → on_job_updated(name, stage)
        worker.job_finished   → on_job_finished(name, success)
        worker.pipeline_count → on_count_updated(done, total)
    """

    _BG          = QColor("#0d1117")
    _ROW_BG      = QColor("#161b22")
    _ROW_BORDER  = QColor("#21262d")
    _TEXT        = QColor("#c9d1d9")
    _TEXT_DIM    = QColor("#484f58")
    _BAR_TRACK   = QColor("#21262d")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows:    list[_JobRow] = []
        self._done:    int = 0
        self._total:   int = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self.setMinimumWidth(320)
        self._update_size()

    # ------------------------------------------------------------------ public

    def set_video_count(self, n: int) -> None:
        """Backward-compat alias."""
        self._total = n
        self._update_size()
        self.update()

    def set_total(self, n: int) -> None:
        self._total = n
        self._update_size()
        self.update()

    def on_job_started(self, name: str, stage: str) -> None:
        # Replace existing row for same video if present (re-run)
        self._rows = [r for r in self._rows if r.name != name]
        self._rows.append(_JobRow(name, stage))
        self._update_size()
        self.update()

    def on_job_updated(self, name: str, stage: str) -> None:
        for row in self._rows:
            if row.name == name:
                row.stage   = stage
                row.shimmer = 0.0
                break
        self.update()

    def on_job_finished(self, name: str, success: bool) -> None:
        for row in self._rows:
            if row.name == name:
                row.stage  = "done" if success else "failed"
                row.fading = True
                break
        self.update()

    def on_count_updated(self, done: int, total: int) -> None:
        self._done  = done
        self._total = total
        self._update_size()
        self.update()

    # Keep old widget API so existing home_view code doesn't crash
    def on_stage_started(self, stage: str) -> None:
        pass

    def on_stage_completed(self, stage: str, success: bool) -> None:
        pass

    def set_stage_total(self, stage: str, total: int) -> None:
        if self._total == 0:
            self._total = total
            self._update_size()
            self.update()

    def on_item_completed(self, stage: str) -> None:
        pass

    def reset(self) -> None:
        self._rows.clear()
        self._done  = 0
        self._total = 0
        self._update_size()
        self.update()

    # ------------------------------------------------------------------ tick

    def _tick(self) -> None:
        changed = False
        live = []
        for row in self._rows:
            if row.fading:
                row.alpha = max(0.0, row.alpha - _FADE_STEP)
                if row.alpha <= 0:
                    changed = True
                    continue          # remove from list
            speed = _STAGE_SHIMMER_SPEED.get(row.stage, 0.0)
            if speed > 0:
                row.shimmer = (row.shimmer + speed) % 1.3
            live.append(row)
            changed = True
        if len(live) != len(self._rows):
            self._rows = live
            self._update_size()
        if changed:
            self.update()

    # ------------------------------------------------------------------ layout

    def _update_size(self) -> None:
        n = max(len(self._rows), 0)
        h = _PAD_Y + _BAR_H + _PAD_Y + n * (_ROW_H + _PAD_Y // 2) + _PAD_Y
        self.setFixedHeight(max(h, 80))

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = float(self.width()), float(self.height())
        p.fillRect(0, 0, int(W), int(H), self._BG)

        self._draw_progress_bar(p, W)
        self._draw_rows(p, W)
        p.end()

    def _draw_progress_bar(self, p: QPainter, W: float) -> None:
        x, y = float(_PAD_X), float(_PAD_Y)
        bw = W - _PAD_X * 2

        # Track
        track = QRectF(x, y, bw, _BAR_H)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._BAR_TRACK))
        p.drawRoundedRect(track, _BAR_H / 2, _BAR_H / 2)

        # Fill
        if self._total > 0:
            frac = min(self._done / self._total, 1.0)
            fill_w = bw * frac
            if fill_w > 0:
                stage_col = _STAGE_COLOR["done"]
                fill = QRectF(x, y, fill_w, _BAR_H)
                p.setBrush(QBrush(stage_col))
                p.drawRoundedRect(fill, _BAR_H / 2, _BAR_H / 2)

        # Label  "3 / 10"
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        p.setPen(QPen(self._TEXT_DIM))
        label = f"{self._done} / {self._total}" if self._total else ""
        p.drawText(
            QRectF(x, y - 1, bw, _BAR_H),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

    def _draw_rows(self, p: QPainter, W: float) -> None:
        y = _PAD_Y + _BAR_H + _PAD_Y

        for row in self._rows:
            alpha_i = int(row.alpha * 255)
            self._draw_one_row(p, W, y, row, alpha_i)
            y += _ROW_H + _PAD_Y // 2

    def _draw_one_row(self, p: QPainter, W: float, y: float,
                      row: _JobRow, alpha: int) -> None:
        x = float(_PAD_X)
        rw = W - _PAD_X * 2
        rh = float(_ROW_H)

        # Row background
        bg = QColor(self._ROW_BG)
        bg.setAlpha(alpha)
        border = QColor(self._ROW_BORDER)
        border.setAlpha(alpha)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(x, y, rw, rh), 6, 6)

        # Shimmer sweep (active stages only)
        speed = _STAGE_SHIMMER_SPEED.get(row.stage, 0.0)
        if speed > 0 and row.shimmer < 1.15:
            sx = x + rw * (row.shimmer - 0.15)
            sw = rw * 0.18
            shim_grad = QLinearGradient(sx, y, sx + sw, y)
            shim_col = QColor(255, 255, 255, int(28 * row.alpha))
            shim_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            shim_grad.setColorAt(0.5, shim_col)
            shim_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(x, y, rw, rh), 6, 6)
            p.setClipPath(clip)
            p.setBrush(QBrush(shim_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(sx, y, sw, rh))
            p.restore()

        # Stage pill
        stage_col = QColor(_STAGE_COLOR.get(row.stage, _STAGE_COLOR["analyze"]))
        stage_col.setAlpha(alpha)
        pill_x = x + 10
        pill_y = y + (rh - _PILL_H) / 2
        pill_rect = QRectF(pill_x, pill_y, _PILL_W, _PILL_H)

        pill_bg = QColor(stage_col)
        pill_bg.setAlpha(int(alpha * 0.25))
        p.setBrush(QBrush(pill_bg))
        p.setPen(QPen(stage_col, 1))
        p.drawRoundedRect(pill_rect, _PILL_R, _PILL_R)

        font = QFont()
        font.setPointSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QPen(stage_col))
        p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter,
                   _STAGE_LABEL.get(row.stage, row.stage.upper()))

        # Filename
        name_x = pill_x + _PILL_W + 10
        name_w = rw - (_PILL_W + 10 + 10 + 10)  # leave right padding
        name_rect = QRectF(name_x, y, name_w, rh)

        font = QFont()
        font.setPointSize(10)
        p.setFont(font)
        text_col = QColor(self._TEXT)
        text_col.setAlpha(alpha)
        p.setPen(QPen(text_col))

        fm = p.fontMetrics()
        elided = fm.elidedText(row.name, Qt.TextElideMode.ElideRight, int(name_w))
        p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        # Done checkmark
        if row.stage in ("done", "failed"):
            mark = "✓" if row.stage == "done" else "✕"
            ck_col = QColor(_STAGE_COLOR[row.stage])
            ck_col.setAlpha(alpha)
            p.setPen(QPen(ck_col))
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            p.setFont(font)
            p.drawText(
                QRectF(x + rw - 30, y, 20, rh),
                Qt.AlignmentFlag.AlignCenter,
                mark,
            )
