"""
Live job-board pipeline widget.

Each card shows:
  - Video filename (middle-elided)
  - A processing bar to the right of the name:
      active  = sweeping shimmer wave
      queued  = dim outline + "QUEUED"
      done    = green fill that fades out
      failed  = red fill that fades out

Header:
  - Thin progress bar; "N / M" right-aligned on the summary line below it
  - "N processing" concurrency summary on the left

Cards sort: active first, then fading (in-place until gone), then queued.
Mouse-wheel scrolls; slim scrollbar tracks position.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
    QPainterPath, QLinearGradient,
)

# Stages that count as "actively processing"
_ACTIVE_STAGES = {"analyze", "correlate", "clip", "processing"}

# ---- palette
_COLOR_ACTIVE = QColor("#F97316")
_COLOR_DONE   = QColor("#22C55E")
_COLOR_FAILED = QColor("#EF4444")

# ---- layout
_PAD_X        = 14
_PAD_Y        = 10
_BAR_H        = 8
_HEADER_BAR_H = _PAD_Y + _BAR_H + 6
_HEADER_SUM_H = 20
_HEADER_H     = _HEADER_BAR_H + _HEADER_SUM_H + _PAD_Y

_ROW_H       = 36       # one line: name on the left, status bar on the right
_PROC_H      = 16
_NAME_FRAC   = 0.5      # share of the card width given to the file name
_ROW_STEP    = _ROW_H + 4
_MAX_VIS     = 6
_FADE_STEP   = 0.032
_SHIMMER_SPD = 0.014


class _JobRow:
    __slots__ = ("name", "stage", "shimmer", "alpha", "fading")

    def __init__(self, name: str, stage: str):
        self.name    = name
        self.stage   = stage
        self.shimmer = 0.0
        self.alpha   = 1.0
        self.fading  = False


class AnimatedPipelineWidget(QWidget):
    """
    Live pipeline job board.  Connect from PipelineWorker:
        job_started    -> on_job_started(name, stage)
        job_updated    -> on_job_updated(name, stage)
        job_finished   -> on_job_finished(name, success)
        pipeline_count -> on_count_updated(done, total)
    """

    workers_changed = pyqtSignal(int)  # emitted when user clicks [−] / [+]

    _BG          = QColor("#0d1117")
    _CARD_BG     = QColor("#161b22")
    _CARD_BG_Q   = QColor("#0f1317")
    _CARD_BD     = QColor("#21262d")
    _TEXT        = QColor("#e6edf3")
    _TEXT_DIM    = QColor("#484f58")
    _BAR_TRACK   = QColor("#21262d")
    _SCROLL_RAIL = QColor("#21262d")
    _SCROLL_THB  = QColor("#484f58")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows:     list[_JobRow] = []
        self._done:     int = 0
        self._total:    int = 0
        self._scroll_y: int = 0
        self._worker_target: int = 2
        self._worker_note: str = ""
        self._status: str = ""   # latest pipeline message, shown while nothing is processing
        self._dec_rect = None
        self._inc_rect = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self.setMinimumWidth(340)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self._update_size()

    # ------------------------------------------------------------------ public

    def set_video_count(self, n: int) -> None:
        self._total = n; self._update_size(); self.update()

    def set_total(self, n: int) -> None:
        self._total = n; self._update_size(); self.update()

    def set_status(self, text: str) -> None:
        """What the pipeline is doing, e.g. a model download, for the header."""
        self._status = text; self.update()

    def set_worker_target(self, n: int, note: str = "") -> None:
        """`note` ("auto", "gaming") explains where the count came from."""
        self._worker_target = max(1, n); self._worker_note = note; self.update()

    def on_job_started(self, name: str, stage: str) -> None:
        existing = next((r for r in self._rows if r.name == name), None)
        if existing:
            existing.stage   = stage
            existing.shimmer = 0.0
            existing.fading  = False
        else:
            row = _JobRow(name, stage)
            if stage == 'queued':
                self._rows.append(row)
            else:
                insert_at = sum(1 for r in self._rows
                                if not r.fading and r.stage in _ACTIVE_STAGES)
                self._rows.insert(insert_at, row)
        self._sort_rows()
        self._clamp_scroll()
        self._update_size()
        self.update()

    def on_job_updated(self, name: str, stage: str) -> None:
        for r in self._rows:
            if r.name == name:
                r.stage   = stage
                r.shimmer = 0.0
                break
        self._sort_rows()
        self.update()

    def on_job_finished(self, name: str, success: bool) -> None:
        for r in self._rows:
            if r.name == name:
                r.stage  = "done" if success else "failed"
                r.fading = True
                break
        self.update()

    def on_count_updated(self, done: int, total: int) -> None:
        self._done = done; self._total = total
        self._update_size(); self.update()

    # compat stubs
    def on_stage_started(self, stage: str) -> None: pass
    def on_stage_completed(self, stage: str, ok: bool) -> None: pass
    def set_stage_total(self, stage: str, total: int) -> None:
        if self._total == 0:
            self._total = total; self._update_size(); self.update()
    def on_item_completed(self, stage: str) -> None: pass

    def reset(self) -> None:
        self._rows.clear(); self._done = 0; self._total = 0; self._scroll_y = 0
        self._status = ""
        self._update_size(); self.update()

    # ------------------------------------------------------------------ sort

    def _sort_rows(self) -> None:
        active = [r for r in self._rows if not r.fading and r.stage in _ACTIVE_STAGES]
        fading = [r for r in self._rows if r.fading]
        queued = [r for r in self._rows if not r.fading and r.stage not in _ACTIVE_STAGES]
        self._rows = active + fading + queued

    # ------------------------------------------------------------------ scroll

    def wheelEvent(self, ev):
        step = int(_ROW_STEP * (-ev.angleDelta().y() / 120))
        self._scroll_y = max(0, min(self._scroll_y + step, self._max_scroll()))
        self.update()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            pos = ev.position()
            if self._dec_rect and self._dec_rect.contains(pos):
                n = max(1, self._worker_target - 1)
                self._worker_target = n
                self._worker_note = ""
                self.workers_changed.emit(n)
                self.update()
                return
            if self._inc_rect and self._inc_rect.contains(pos):
                n = self._worker_target + 1
                self._worker_target = n
                self._worker_note = ""
                self.workers_changed.emit(n)
                self.update()
                return
        super().mousePressEvent(ev)

    def _max_scroll(self) -> int:
        total_h = len(self._rows) * _ROW_STEP + _PAD_Y
        return max(0, total_h - (self.height() - _HEADER_H))

    def _clamp_scroll(self) -> None:
        self._scroll_y = max(0, min(self._scroll_y, self._max_scroll()))

    # ------------------------------------------------------------------ tick

    def _tick(self) -> None:
        changed = False
        live    = []
        for r in self._rows:
            if r.fading:
                r.alpha = max(0.0, r.alpha - _FADE_STEP)
                if r.alpha <= 0:
                    changed = True
                    continue
            if r.stage in _ACTIVE_STAGES:
                r.shimmer = (r.shimmer + _SHIMMER_SPD) % 1.0
            live.append(r)
            changed = True
        if len(live) != len(self._rows):
            self._rows = live
            self._clamp_scroll()
            self._update_size()
        if changed:
            self.update()

    # ------------------------------------------------------------------ size

    def _update_size(self) -> None:
        vis = min(len(self._rows), _MAX_VIS)
        h   = _HEADER_H + vis * _ROW_STEP + _PAD_Y
        self.setFixedHeight(max(h, _HEADER_H + _PAD_Y))

    # ------------------------------------------------------------------ paint

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = float(self.width())
        p.fillRect(0, 0, int(W), self.height(), self._BG)
        self._draw_header(p, W)
        self._draw_rows_area(p, W)
        p.end()

    # ------------------------------------------------------------------ header

    def _draw_header(self, p: QPainter, W: float) -> None:
        x  = float(_PAD_X)
        y  = float(_PAD_Y)
        bw = W - _PAD_X * 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._BAR_TRACK))
        p.drawRoundedRect(QRectF(x, y, bw, _BAR_H), _BAR_H / 2, _BAR_H / 2)

        if self._total > 0:
            frac = min(self._done / self._total, 1.0)
            fw   = bw * frac
            if fw > 0:
                p.setBrush(QBrush(_COLOR_DONE))
                p.drawRoundedRect(QRectF(x, y, fw, _BAR_H), _BAR_H / 2, _BAR_H / 2)

        sy = y + _BAR_H + 6
        f  = QFont(); f.setPointSize(9); f.setBold(True); p.setFont(f)
        fm = p.fontMetrics()

        if self._total:
            p.setPen(QPen(self._TEXT_DIM))
            p.drawText(
                QRectF(x, sy, bw, _HEADER_SUM_H),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{self._done} / {self._total}",
            )

        n_active = sum(1 for r in self._rows if r.stage in _ACTIVE_STAGES and not r.fading)
        if n_active == 0:
            self._dec_rect = self._inc_rect = None
            p.setPen(QPen(QColor("#9ca3af") if self._status else self._TEXT_DIM))
            count_w = fm.horizontalAdvance(f"{self._done} / {self._total}") + 16
            p.drawText(QRectF(x, sy, bw - count_w, _HEADER_SUM_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(self._status or "Starting…",
                                     Qt.TextElideMode.ElideRight, int(bw - count_w)))
        else:
            label = f"{n_active} processing"
            lw = float(fm.horizontalAdvance(label))
            p.setPen(QPen(self._TEXT))
            p.drawText(QRectF(x, sy, lw + 2, _HEADER_SUM_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       label)
            self._draw_worker_stepper(p, fm, x + lw + 10, sy)

    def _draw_worker_stepper(self, p: QPainter, fm, sx: float, sy: float) -> None:
        """Draw [−] N [+] stepper and record click-test rects for mousePressEvent."""
        bw, bh = 14.0, 14.0
        gap    = 3.0
        step_y = sy + (_HEADER_SUM_H - bh) / 2.0

        ts = str(self._worker_target)
        tw = float(fm.horizontalAdvance(ts)) + 8.0

        self._dec_rect = QRectF(sx,                        step_y, bw, bh)
        self._inc_rect = QRectF(sx + bw + gap + tw + gap, step_y, bw, bh)

        dim = QColor(self._TEXT_DIM)
        for rect, ch in ((self._dec_rect, '−'), (self._inc_rect, '+')):
            p.setPen(QPen(dim, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, 2, 2)
            fb = QFont(); fb.setPointSize(7); fb.setBold(True); p.setFont(fb)
            p.setPen(QPen(dim))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)

        fn = QFont(); fn.setPointSize(9); p.setFont(fn)
        p.setPen(QPen(dim))
        p.drawText(QRectF(sx + bw + gap, step_y, tw, bh), Qt.AlignmentFlag.AlignCenter, ts)

        if self._worker_note:
            note = {"auto": "workers (auto: as many as fit in memory)",
                    "gaming": "worker (gaming mode)"}.get(self._worker_note, self._worker_note)
            nx = self._inc_rect.right() + 8
            p.drawText(QRectF(nx, sy, p.fontMetrics().horizontalAdvance(note) + 4, _HEADER_SUM_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, note)

    # ------------------------------------------------------------------ rows

    def _draw_rows_area(self, p: QPainter, W: float) -> None:
        if not self._rows:
            return

        vp_top = float(_HEADER_H)
        vp_h   = float(self.height() - _HEADER_H)

        p.save()
        p.setClipRect(QRectF(0, vp_top, W, vp_h))
        y = vp_top + _PAD_Y // 2 - self._scroll_y
        for row in self._rows:
            if y + _ROW_H > vp_top and y < vp_top + vp_h:
                self._draw_card(p, W, y, row, int(row.alpha * 255))
            y += _ROW_STEP
        p.restore()

        if self._max_scroll() > 0 and self._scroll_y < self._max_scroll():
            fade_h = 32.0
            grad   = QLinearGradient(0, vp_top + vp_h - fade_h, 0, vp_top + vp_h)
            grad.setColorAt(0.0, QColor(13, 17, 23, 0))
            grad.setColorAt(1.0, QColor(13, 17, 23, 210))
            p.fillRect(QRectF(0, vp_top + vp_h - fade_h, W, fade_h), QBrush(grad))

        if self._max_scroll() > 0:
            self._draw_scrollbar(p, W, vp_top, vp_h)

    def _draw_scrollbar(self, p, W, vp_top, vp_h):
        tw = 3.0; tx = W - 6.0
        tr = QRectF(tx, vp_top + 6, tw, vp_h - 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._SCROLL_RAIL))
        p.drawRoundedRect(tr, 1.5, 1.5)
        total_h = len(self._rows) * _ROW_STEP + _PAD_Y
        th  = max(18.0, vp_h * (vp_h / total_h))
        sc  = self._scroll_y / max(1, self._max_scroll())
        ty  = vp_top + 6 + sc * (vp_h - 12 - th)
        p.setBrush(QBrush(self._SCROLL_THB))
        p.drawRoundedRect(QRectF(tx, ty, tw, th), 1.5, 1.5)

    # ------------------------------------------------------------------ card

    def _draw_card(self, p: QPainter, W: float, y: float,
                   row: _JobRow, alpha: int) -> None:
        x  = float(_PAD_X)
        rw = W - _PAD_X * 2
        rh = float(_ROW_H)

        is_active = row.stage in _ACTIVE_STAGES
        is_queued = not is_active and not row.fading
        col = (_COLOR_ACTIVE if is_active else
               _COLOR_DONE   if row.stage == "done" else
               _COLOR_FAILED if row.stage == "failed" else
               self._CARD_BD)

        card_bg = QColor(self._CARD_BG_Q if is_queued else self._CARD_BG)
        card_bg.setAlpha(alpha)
        p.setBrush(QBrush(card_bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(x, y, rw, rh), 6, 6)

        if is_active:
            bd = QColor(col); bd.setAlpha(int(alpha * 0.55))
        else:
            bd = QColor(self._CARD_BD); bd.setAlpha(alpha)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(bd, 1))
        p.drawRoundedRect(QRectF(x + 0.5, y + 0.5, rw - 1, rh - 1), 5.5, 5.5)

        f = QFont(); f.setPointSize(10); p.setFont(f)
        tc = QColor(self._TEXT if not is_queued else self._TEXT_DIM)
        tc.setAlpha(alpha)
        p.setPen(QPen(tc))
        name_w = (rw - 30) * _NAME_FRAC
        name_rect = QRectF(x + 10, y, name_w, rh)
        elided = p.fontMetrics().elidedText(
            row.name, Qt.TextElideMode.ElideMiddle, int(name_w)
        )
        p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        bx = x + 20 + name_w
        bh = float(_PROC_H)
        by = y + (rh - bh) / 2
        bw = rw - 30 - name_w

        if is_active:
            self._draw_bar_active(p, bx, by, bw, bh, row, alpha)
        elif is_queued:
            self._draw_bar_queued(p, bx, by, bw, bh, alpha)
        else:
            self._draw_bar_done(p, bx, by, bw, bh, col, row.stage, alpha)

    # ------------------------------------------------------------------ bar renderers

    def _draw_bar_active(self, p, x, y, w, h, row, alpha):
        r = h / 2

        bg = QColor(_COLOR_ACTIVE); bg.setAlpha(int(alpha * 0.18))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)

        cx = x + w * (row.shimmer * 1.5 - 0.25)
        ww = w * 0.60

        grad = QLinearGradient(cx - ww / 2, y, cx + ww / 2, y)
        grad.setColorAt(0.00, QColor(249, 115, 22,   0))
        grad.setColorAt(0.28, QColor(249, 115, 22,   int(alpha * 0.42)))
        grad.setColorAt(0.47, QColor(255, 195, 120,  int(alpha * 0.88)))
        grad.setColorAt(0.50, QColor(255, 240, 200,  int(alpha * 0.70)))
        grad.setColorAt(0.53, QColor(255, 195, 120,  int(alpha * 0.88)))
        grad.setColorAt(0.72, QColor(249, 115, 22,   int(alpha * 0.42)))
        grad.setColorAt(1.00, QColor(249, 115, 22,   0))

        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(x, y, w, h), r, r)
        p.setClipPath(clip)
        p.setBrush(QBrush(grad))
        p.drawRect(QRectF(cx - ww / 2, y, ww, h))
        p.restore()

        bd = QColor(_COLOR_ACTIVE); bd.setAlpha(int(alpha * 0.65))
        p.setPen(QPen(bd, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)

        f = QFont(); f.setPointSize(7); f.setBold(True); p.setFont(f)
        lc = QColor(_COLOR_ACTIVE); lc.setAlpha(int(alpha * 0.9))
        p.setPen(QPen(lc))
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "PROCESSING")

    def _draw_bar_queued(self, p, x, y, w, h, alpha):
        r = h / 2
        track = QColor(self._BAR_TRACK); track.setAlpha(int(alpha * 0.5))
        p.setPen(QPen(track, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)
        f = QFont(); f.setPointSize(7); p.setFont(f)
        dim = QColor(self._TEXT_DIM); dim.setAlpha(int(alpha * 0.45))
        p.setPen(QPen(dim))
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "QUEUED")

    def _draw_bar_done(self, p, x, y, w, h, col, stage, alpha):
        r = h / 2
        fill = QColor(col); fill.setAlpha(int(alpha * 0.50))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)
        bd = QColor(col); bd.setAlpha(int(alpha * 0.3))
        p.setPen(QPen(bd, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)
        f = QFont(); f.setPointSize(7); f.setBold(True); p.setFont(f)
        tc = QColor(col); tc.setAlpha(int(alpha * 0.9))
        p.setPen(QPen(tc))
        label = "DONE" if stage == "done" else "FAILED"
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, label)
