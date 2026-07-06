"""
Live job-board pipeline widget.

Each row shows a video filename and a three-stage pipeline flow:
    [ANALYZE] ──▶── [CORRELATE] ──▶── [CLIP]

Done stages are dimmed with a ✓; the active stage is bright with a shimmer;
pending stages are ghosted outlines.  A concurrency summary below the
progress bar shows how many videos are at each stage right now.
"""

from collections import Counter

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
    QPainterPath, QLinearGradient,
)

# ---- stage definitions ---------------------------------------------------
_PIPELINE   = ["analyze", "correlate", "clip"]

_STAGE_COLOR = {
    "analyze":   QColor("#3B82F6"),
    "correlate": QColor("#8B5CF6"),
    "clip":      QColor("#F97316"),
    "done":      QColor("#22C55E"),
    "failed":    QColor("#EF4444"),
    "ingest":    QColor("#6B7280"),
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
# pill widths for each pipeline stage
_STAGE_PW = {
    "analyze":   68,
    "correlate": 76,
    "clip":      48,
}
_ARROW_W   = 18   # width of ──▶── connector between pills
_PIPE_H    = 22   # height of the 3-pill pipeline row inside each card
_PILL_H    = 20
_PILL_R    = 4

_STAGE_SHIMMER = {
    "analyze":   0.006,
    "correlate": 0.022,
    "clip":      0.013,
}

# ---- layout --------------------------------------------------------------
_PAD_X     = 14
_PAD_Y     = 10
_BAR_H     = 6
_ROW_H     = 54          # card height (filename + pipeline row)
_ROW_STEP  = _ROW_H + 6
_MAX_VIS   = 5
_FADE_STEP = 0.04
_SCROLL_SPD = _ROW_STEP

_BAR_SECTION  = _PAD_Y + _BAR_H + _PAD_Y          # progress bar area
_SUM_H        = 18                                  # concurrency summary line height
_HEADER_H     = _BAR_SECTION + _SUM_H + _PAD_Y     # total pinned header height


# --------------------------------------------------------------------------

class _JobRow:
    __slots__ = ("name", "stage", "shimmer", "alpha", "fading")

    def __init__(self, name: str, stage: str):
        self.name    = name
        self.stage   = stage
        self.shimmer = 0.0
        self.alpha   = 1.0
        self.fading  = False


# --------------------------------------------------------------------------

class AnimatedPipelineWidget(QWidget):
    """
    Live pipeline job board.

    Connect from PipelineWorker:
        job_started    → on_job_started(name, stage)
        job_updated    → on_job_updated(name, stage)
        job_finished   → on_job_finished(name, success)
        pipeline_count → on_count_updated(done, total)
    """

    _BG         = QColor("#0d1117")
    _CARD_BG    = QColor("#161b22")
    _CARD_BD    = QColor("#21262d")
    _TEXT       = QColor("#c9d1d9")
    _TEXT_DIM   = QColor("#484f58")
    _BAR_TRACK  = QColor("#21262d")
    _SCROLL_BAR = QColor("#2a2d35")
    _SCROLL_THB = QColor("#484f58")
    _CONN_COL   = QColor("#30363d")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows:     list[_JobRow] = []
        self._done:     int = 0
        self._total:    int = 0
        self._scroll_y: int = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self.setMinimumWidth(340)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self._update_size()

    # ------------------------------------------------------------------ public API

    def set_video_count(self, n: int) -> None:
        self._total = n
        self._update_size()
        self.update()

    def set_total(self, n: int) -> None:
        self._total = n
        self._update_size()
        self.update()

    def on_job_started(self, name: str, stage: str) -> None:
        self._rows = [r for r in self._rows if r.name != name]
        self._rows.append(_JobRow(name, stage))
        self._clamp_scroll()
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

    # compat stubs
    def on_stage_started(self, stage: str) -> None: pass
    def on_stage_completed(self, stage: str, success: bool) -> None: pass
    def set_stage_total(self, stage: str, total: int) -> None:
        if self._total == 0:
            self._total = total
            self._update_size()
            self.update()
    def on_item_completed(self, stage: str) -> None: pass

    def reset(self) -> None:
        self._rows.clear()
        self._done     = 0
        self._total    = 0
        self._scroll_y = 0
        self._update_size()
        self.update()

    # ------------------------------------------------------------------ scroll

    def wheelEvent(self, event):  # noqa: N802
        delta = event.angleDelta().y()
        step  = int(_SCROLL_SPD * (-delta / 120))
        self._scroll_y = max(0, min(self._scroll_y + step, self._max_scroll()))
        self.update()

    def _max_scroll(self) -> int:
        total_h  = len(self._rows) * _ROW_STEP + _PAD_Y
        visible_h = self.height() - _HEADER_H
        return max(0, total_h - visible_h)

    def _clamp_scroll(self) -> None:
        self._scroll_y = max(0, min(self._scroll_y, self._max_scroll()))

    # ------------------------------------------------------------------ tick

    def _tick(self) -> None:
        changed = False
        live    = []
        for row in self._rows:
            if row.fading:
                row.alpha = max(0.0, row.alpha - _FADE_STEP)
                if row.alpha <= 0:
                    changed = True
                    continue
            speed = _STAGE_SHIMMER.get(row.stage, 0.0)
            if speed > 0:
                row.shimmer = (row.shimmer + speed) % 1.3
            live.append(row)
            changed = True
        if len(live) != len(self._rows):
            self._rows = live
            self._clamp_scroll()
            self._update_size()
        if changed:
            self.update()

    # ------------------------------------------------------------------ layout

    def _update_size(self) -> None:
        visible = min(len(self._rows), _MAX_VIS)
        h = _HEADER_H + visible * _ROW_STEP + _PAD_Y
        self.setFixedHeight(max(h, _HEADER_H + _PAD_Y))

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = float(self.width())
        p.fillRect(0, 0, int(W), self.height(), self._BG)
        self._draw_header(p, W)
        self._draw_rows(p, W)
        p.end()

    # ------------------------------------------------------------------ header

    def _draw_header(self, p: QPainter, W: float) -> None:
        x = float(_PAD_X)
        y = float(_PAD_Y)
        bw = W - _PAD_X * 2

        # Progress bar track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._BAR_TRACK))
        p.drawRoundedRect(QRectF(x, y, bw, _BAR_H), _BAR_H / 2, _BAR_H / 2)

        # Progress bar fill
        if self._total > 0:
            frac = min(self._done / self._total, 1.0)
            fw   = bw * frac
            if fw > 0:
                p.setBrush(QBrush(_STAGE_COLOR["done"]))
                p.drawRoundedRect(QRectF(x, y, fw, _BAR_H), _BAR_H / 2, _BAR_H / 2)

        # "N / M" label right-aligned over the bar
        font = QFont(); font.setPointSize(8)
        p.setFont(font)
        p.setPen(QPen(self._TEXT_DIM))
        label = f"{self._done} / {self._total}" if self._total else ""
        p.drawText(
            QRectF(x, y - 1, bw, _BAR_H),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

        # Concurrency summary  "2 ANALYZING · 1 CORRELATING · 4 CLIPPING"
        counts = Counter(
            row.stage for row in self._rows if not row.fading and row.stage in _PIPELINE
        )
        sy = y + _BAR_H + 6
        cx = x
        font = QFont(); font.setPointSize(8); font.setBold(True)
        p.setFont(font)
        fm = p.fontMetrics()

        if not counts:
            p.setPen(QPen(self._TEXT_DIM))
            p.drawText(QRectF(cx, sy, bw, _SUM_H),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "Waiting…")
        else:
            parts = []
            for s in _PIPELINE:
                n = counts.get(s, 0)
                if n:
                    parts.append((n, s))

            dot = "  ·  "
            dot_w = fm.horizontalAdvance(dot)

            for i, (n, s) in enumerate(parts):
                col = QColor(_STAGE_COLOR[s])
                text = f"{n} {_STAGE_LABEL[s]}"
                tw = fm.horizontalAdvance(text)
                p.setPen(QPen(col))
                p.drawText(QRectF(cx, sy, tw + 2, _SUM_H),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           text)
                cx += tw
                if i < len(parts) - 1:
                    p.setPen(QPen(self._TEXT_DIM))
                    p.drawText(QRectF(cx, sy, dot_w + 2, _SUM_H),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               dot)
                    cx += dot_w

    # ------------------------------------------------------------------ rows

    def _draw_rows(self, p: QPainter, W: float) -> None:
        if not self._rows:
            return

        vp_top = float(_HEADER_H)
        vp_h   = float(self.height() - _HEADER_H)

        p.save()
        p.setClipRect(QRectF(0, vp_top, W, vp_h))

        y = vp_top + _PAD_Y // 2 - self._scroll_y
        for row in self._rows:
            if y + _ROW_H > vp_top and y < vp_top + vp_h:
                self._draw_one_row(p, W, y, row, int(row.alpha * 255))
            y += _ROW_STEP

        p.restore()

        if self._max_scroll() > 0:
            self._draw_scrollbar(p, W, vp_top, vp_h)

    def _draw_scrollbar(self, p: QPainter, W: float,
                        vp_top: float, vp_h: float) -> None:
        tw  = 4.0
        tx  = W - _PAD_X // 2 - tw
        tr  = QRectF(tx, vp_top + 4, tw, vp_h - 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._SCROLL_BAR))
        p.drawRoundedRect(tr, 2, 2)
        total_h = len(self._rows) * _ROW_STEP + _PAD_Y
        th = max(20.0, vp_h * (vp_h / total_h))
        sc = self._scroll_y / max(1, self._max_scroll())
        ty = vp_top + 4 + sc * (vp_h - 8 - th)
        p.setBrush(QBrush(self._SCROLL_THB))
        p.drawRoundedRect(QRectF(tx, ty, tw, th), 2, 2)

    def _draw_one_row(self, p: QPainter, W: float, y: float,
                      row: _JobRow, alpha: int) -> None:
        x  = float(_PAD_X)
        rw = W - _PAD_X * 2
        rh = float(_ROW_H)

        # Card background
        bg = QColor(self._CARD_BG); bg.setAlpha(alpha)
        bd = QColor(self._CARD_BD); bd.setAlpha(alpha)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(bd, 1))
        p.drawRoundedRect(QRectF(x, y, rw, rh), 6, 6)

        # --- Filename (top portion) ---
        fname_h = rh - _PIPE_H - 8    # space for filename above pipeline row
        font = QFont(); font.setPointSize(10)
        p.setFont(font)
        tc = QColor(self._TEXT); tc.setAlpha(alpha)
        p.setPen(QPen(tc))

        name_x = x + 10
        name_w = rw - 20
        elided = p.fontMetrics().elidedText(
            row.name, Qt.TextElideMode.ElideRight, int(name_w)
        )
        p.drawText(
            QRectF(name_x, y, name_w, fname_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided,
        )

        # --- Pipeline mini-view (bottom portion) ---
        pipe_y = y + fname_h + 2
        self._draw_pipeline_row(p, x + 10, pipe_y, rw - 20, row, alpha)

    def _draw_pipeline_row(self, p: QPainter, x: float, y: float, w: float,
                           row: _JobRow, alpha: int) -> None:
        """Draw [ANALYZE] ──▶── [CORRELATE] ──▶── [CLIP] inline."""

        stage_idx = _PIPELINE.index(row.stage) if row.stage in _PIPELINE else (
            len(_PIPELINE) if row.stage in ("done", "failed") else -1
        )

        # Layout: compute total pipeline width and center it in w
        total_pipe_w = sum(_STAGE_PW[s] for s in _PIPELINE) + _ARROW_W * (len(_PIPELINE) - 1)
        start_x = x + max(0.0, (w - total_pipe_w) / 2)

        cx = start_x
        for i, stage in enumerate(_PIPELINE):
            pw = float(_STAGE_PW[stage])
            ph = float(_PILL_H)
            pill_y = y + (_PIPE_H - ph) / 2

            if i < stage_idx:
                # Done stage: dim fill + ✓
                self._draw_stage_pill_done(p, cx, pill_y, pw, ph, stage, alpha)
            elif i == stage_idx:
                # Active stage: bright + shimmer
                self._draw_stage_pill_active(p, cx, pill_y, pw, ph, stage, row, alpha)
            else:
                # Pending: ghost outline
                self._draw_stage_pill_pending(p, cx, pill_y, pw, ph, stage, alpha)

            cx += pw

            # Connector arrow between pills
            if i < len(_PIPELINE) - 1:
                arrow_color = QColor(self._CONN_COL)
                arrow_color.setAlpha(alpha)
                p.setPen(QPen(arrow_color, 1))
                mid_y = pill_y + ph / 2
                p.drawLine(
                    int(cx + 2), int(mid_y),
                    int(cx + _ARROW_W - 4), int(mid_y)
                )
                # arrowhead
                tip_x = cx + _ARROW_W - 4
                p.drawLine(int(tip_x), int(mid_y), int(tip_x - 4), int(mid_y - 3))
                p.drawLine(int(tip_x), int(mid_y), int(tip_x - 4), int(mid_y + 3))
                cx += _ARROW_W

    def _draw_stage_pill_done(self, p: QPainter, x: float, y: float,
                              w: float, h: float, stage: str, alpha: int) -> None:
        col = QColor(_STAGE_COLOR[stage])
        col.setAlpha(int(alpha * 0.45))
        bg  = QColor(_STAGE_COLOR[stage]); bg.setAlpha(int(alpha * 0.08))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(col, 1))
        p.drawRoundedRect(QRectF(x, y, w, h), _PILL_R, _PILL_R)
        font = QFont(); font.setPointSize(6)
        p.setFont(font)
        p.setPen(QPen(col))
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "✓")

    def _draw_stage_pill_active(self, p: QPainter, x: float, y: float,
                                w: float, h: float, stage: str,
                                row: _JobRow, alpha: int) -> None:
        col    = QColor(_STAGE_COLOR[stage]); col.setAlpha(alpha)
        bg_col = QColor(_STAGE_COLOR[stage]); bg_col.setAlpha(int(alpha * 0.22))
        p.setBrush(QBrush(bg_col))
        p.setPen(QPen(col, 1))
        p.drawRoundedRect(QRectF(x, y, w, h), _PILL_R, _PILL_R)

        # Shimmer sweep
        if row.shimmer < 1.15:
            sx  = x + w * (row.shimmer - 0.15)
            sw  = w * 0.35
            g   = QLinearGradient(sx, y, sx + sw, y)
            shim = QColor(255, 255, 255, int(35 * row.alpha))
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(0.5, shim)
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(x, y, w, h), _PILL_R, _PILL_R)
            p.setClipPath(clip)
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(sx, y, sw, h))
            p.restore()

        font = QFont(); font.setPointSize(6); font.setBold(True)
        p.setFont(font)
        p.setPen(QPen(col))
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter,
                   _STAGE_LABEL[stage])

    def _draw_stage_pill_pending(self, p: QPainter, x: float, y: float,
                                 w: float, h: float, stage: str, alpha: int) -> None:
        col = QColor(self._TEXT_DIM); col.setAlpha(int(alpha * 0.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, 1))
        p.drawRoundedRect(QRectF(x, y, w, h), _PILL_R, _PILL_R)
        font = QFont(); font.setPointSize(6)
        p.setFont(font)
        p.setPen(QPen(col))
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter,
                   _STAGE_LABEL[stage])
