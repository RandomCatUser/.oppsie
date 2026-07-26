#!/usr/bin/env python3

import os
import sys
import time
import math
from pathlib import Path
from typing import List, Optional

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

# Add parent directory to import custom modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import oppsie
from converter.to_oppsie import convert_to_oppsie
from converter.from_oppsie import convert_from_oppsie

# ═══════════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS  (Catppuccin Mocha)
# ═══════════════════════════════════════════════════════════════════════════
C = {
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
    "surface0": "#313244",
    "surface1": "#45475a",
    "surface2": "#585b70",
    "overlay0": "#6c7086",
    "overlay1": "#7f849c",
    "overlay2": "#a6adc8",
    "text": "#cdd6f4",
    "subtext0": "#a6adc8",
    "subtext1": "#bac2de",
    "mauve": "#cba6f7",
    "pink": "#f5c2e7",
    "lavender": "#b4befe",
    "blue": "#89b4fa",
    "sapphire": "#74c7ec",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "red": "#f38ba8",
    "peach": "#fab387",
    "teal": "#94e2d5",
    "rosewater": "#f5e0dc",
}

FORMATS = ["oppsie", "png", "jpeg", "webp", "bmp"]


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def load_image(path):
    p = Path(str(path).strip().strip('"').strip("'")).resolve()
    if p.suffix.lower() == ".oppsie":
        with open(p, "rb") as f:
            return oppsie.decode(f.read())
    return Image.open(p)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def round_pixmap(src, size, radius):
    scaled = src.scaled(
        size, size,
        QtCore.Qt.KeepAspectRatioByExpanding,
        QtCore.Qt.SmoothTransformation
    )
    out = QtGui.QPixmap(size, size)
    out.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(out)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    clip = QtGui.QPainterPath()
    clip.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, scaled)
    p.end()
    return out


def make_thumbnail(path, size=44):
    try:
        img = load_image(path)
        thumb = img.copy()
        thumb.thumbnail((size, size), Image.Resampling.LANCZOS)
        if thumb.mode == "RGBA":
            thumb = thumb.convert("RGB")
        elif thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        data = thumb.tobytes("raw", "RGB")
        qi = QtGui.QImage(
            data, thumb.width, thumb.height,
            3 * thumb.width, QtGui.QImage.Format_RGB888
        )
        return round_pixmap(QtGui.QPixmap.fromImage(qi), size, 8)
    except Exception:
        return None


def make_large_thumbnail(path, size=200):
    try:
        img = load_image(path)
        thumb = img.copy()
        thumb.thumbnail((size, size), Image.Resampling.LANCZOS)
        if thumb.mode == "RGBA":
            thumb = thumb.convert("RGB")
        elif thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        data = thumb.tobytes("raw", "RGB")
        qi = QtGui.QImage(
            data, thumb.width, thumb.height,
            3 * thumb.width, QtGui.QImage.Format_RGB888
        )
        return QtGui.QPixmap.fromImage(qi)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  CONVERSION WORKER  (with cancellation)
# ═══════════════════════════════════════════════════════════════════════════
class ConversionWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    status = QtCore.pyqtSignal(str)
    done = QtCore.pyqtSignal(object)

    def __init__(self, src, dst, fmt, lossy, parent=None):
        super().__init__(parent)
        self.src = src
        self.dst = dst
        self.fmt = fmt
        self.lossy = lossy
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        t0 = time.perf_counter()
        try:
            self.status.emit(f"Encoding {Path(self.src).name}…")
            self.progress.emit(10)
            if self._cancel:
                self.done.emit({"ok": False, "error": "Cancelled"})
                return
            if self.fmt == "oppsie":
                convert_to_oppsie(self.src, self.dst, lossy_level=self.lossy)
            else:
                convert_from_oppsie(self.src, self.dst)
            if self._cancel:
                self.done.emit({"ok": False, "error": "Cancelled"})
                return
            self.progress.emit(80)
            ms = (time.perf_counter() - t0) * 1000
            dp = Path(self.dst)
            if dp.suffix.lower() == ".oppsie":
                with open(dp, "rb") as f:
                    oppsie.decode(f.read())
            else:
                Image.open(dp)
            self.progress.emit(100)
            self.done.emit({
                "ok": True,
                "src": Path(self.src),
                "dst": dp,
                "ms": ms,
            })
        except Exception as e:
            self.done.emit({"ok": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
#  STATUS DOT  (pulsing glow)
# ═══════════════════════════════════════════════════════════════════════════
class StatusDot(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QtGui.QColor(C["green"])
        self._phase = 0.0
        self._active = True
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def setColor(self, name):
        self._color = QtGui.QColor(C.get(name, name))
        self.update()

    def setActive(self, on):
        self._active = on
        if not on:
            self._phase = 0
        self.update()

    def _tick(self):
        if self._active:
            self._phase = (self._phase + 0.12) % (2 * math.pi)
            self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        alpha = int(20 + 18 * math.sin(self._phase)) if self._active else 10
        glow = QtGui.QColor(self._color)
        glow.setAlpha(max(0, alpha))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(glow)
        rect = self.rect().adjusted(-4, -4, 4, 4)
        p.drawEllipse(rect)
        p.setBrush(self._color)
        p.drawEllipse(self.rect())
        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  GLOW PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════
class GlowBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setFixedHeight(8)
        self._anim = QtCore.QPropertyAnimation(self, b"value")
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

    def _get_value(self):
        return self._value

    def _set_value(self, v):
        self._value = max(0, min(100, v))
        self.update()

    value = QtCore.pyqtProperty(int, _get_value, _set_value)

    def animateTo(self, v):
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(max(0, min(100, v)))
        self._anim.start()

    def reset(self):
        self._anim.stop()
        self._value = 0
        self.update()

    def paintEvent(self, _):
        if self._value <= 0:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        radius = rect.height() / 2
        fill_width = max(radius * 2, rect.width() * self._value / 100)
        fill_rect = QtCore.QRectF(rect.x(), rect.y(), fill_width, rect.height())
        glow = QtGui.QColor(C["mauve"])
        glow.setAlpha(25)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(fill_rect.adjusted(-2, -3, 2, 3), radius + 2, radius + 2)
        grad = QtGui.QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
        grad.setColorAt(0, QtGui.QColor(C["mauve"]))
        grad.setColorAt(1, QtGui.QColor(C["pink"]))
        p.setBrush(grad)
        p.drawRoundedRect(fill_rect, radius, radius)
        shimmer = QtGui.QLinearGradient(0, rect.y(), 0, rect.center().y())
        shimmer.setColorAt(0, QtGui.QColor(255, 255, 255, 50))
        shimmer.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        p.setBrush(shimmer)
        p.drawRoundedRect(fill_rect, radius, radius)
        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  FILE ITEM  (7-zip style row with checkbox)
# ═══════════════════════════════════════════════════════════════════════════
class FileItem(QtWidgets.QFrame):
    removeRequested = QtCore.pyqtSignal(object)
    selectedChanged = QtCore.pyqtSignal(bool)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.target_fmt = "oppsie"
        self._selected = False
        self._preview_window = None
        self._hover_timer = QtCore.QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(600)
        self._hover_timer.timeout.connect(self._show_preview)
        self.setAcceptDrops(False)
        self._build()
        self._apply_shadow()

    def _apply_shadow(self):
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QtGui.QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def _build(self):
        self.setFixedHeight(52)
        self.setObjectName("fileItem")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        # Checkbox (7-zip style)
        self._check = QtWidgets.QCheckBox()
        self._check.setChecked(True)
        self._check.setObjectName("fileCheck")
        self._check.setFixedSize(18, 18)
        lay.addWidget(self._check)

        # Thumbnail
        self._thumb_label = QtWidgets.QLabel()
        self._thumb_label.setFixedSize(36, 36)
        self._thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self._thumb_label.setObjectName("thumbLabel")
        pm = make_thumbnail(self.path, 36)
        if pm:
            self._thumb_label.setPixmap(pm)
        else:
            self._thumb_label.setText("📄")
            self._thumb_label.setStyleSheet("font-size:18px;")
        lay.addWidget(self._thumb_label)

        # File info (name + size in columns)
        name = QtWidgets.QLabel(self.path.name)
        name.setObjectName("fileName")
        lay.addWidget(name, 1)

        try:
            size_str = human_size(self.path.stat().st_size)
        except OSError:
            size_str = "—"
        size = QtWidgets.QLabel(size_str)
        size.setObjectName("fileSize")
        size.setFixedWidth(70)
        size.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        lay.addWidget(size)

        # Arrow
        arrow = QtWidgets.QLabel("→")
        arrow.setObjectName("arrow")
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        arrow.setFixedWidth(20)
        lay.addWidget(arrow)

        # Format combo
        self._fmt = QtWidgets.QComboBox()
        self._fmt.addItems(FORMATS)
        self._fmt.setCurrentText("oppsie")
        self._fmt.setObjectName("fmtCombo")
        self._fmt.setFixedWidth(95)
        self._fmt.currentTextChanged.connect(
            lambda t: setattr(self, "target_fmt", t)
        )
        lay.addWidget(self._fmt)

        # Status icon
        self._status_label = QtWidgets.QLabel()
        self._status_label.setFixedSize(22, 22)
        self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(self._status_label)

        # Remove button
        self._remove_btn = QtWidgets.QPushButton("✕")
        self._remove_btn.setObjectName("removeBtn")
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(
            lambda: self.removeRequested.emit(self)
        )
        lay.addWidget(self._remove_btn)

        self._thumb_label.installEventFilter(self)
        self.installEventFilter(self)

    def isChecked(self):
        return self._check.isChecked()

    def setChecked(self, v):
        self._check.setChecked(v)

    def eventFilter(self, obj, event):
        if obj == self._thumb_label or obj == self:
            if event.type() == QtCore.QEvent.Enter:
                self._hover_timer.start()
            elif event.type() == QtCore.QEvent.Leave:
                self._hover_timer.stop()
                self._hide_preview()
        return super().eventFilter(obj, event)

    def _show_preview(self):
        if self._preview_window is not None:
            return
        pm = make_large_thumbnail(self.path, 200)
        if pm is None:
            return
        self._preview_window = QtWidgets.QFrame()
        self._preview_window.setWindowFlags(QtCore.Qt.Popup)
        self._preview_window.setObjectName("previewWindow")
        layout = QtWidgets.QVBoxLayout(self._preview_window)
        layout.setContentsMargins(6, 6, 6, 6)
        label = QtWidgets.QLabel()
        label.setPixmap(pm)
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
        self._preview_window.setStyleSheet(f"""
            QFrame#previewWindow {{
                background: {C['crust']};
                border: 1px solid {C['surface0']};
                border-radius: 8px;
            }}
        """)
        pos = self._thumb_label.mapToGlobal(QtCore.QPoint(0, 0))
        self._preview_window.move(pos.x() - 20, pos.y() - pm.height() - 10)
        self._preview_window.show()

    def _hide_preview(self):
        if self._preview_window:
            self._preview_window.close()
            self._preview_window.deleteLater()
            self._preview_window = None

    def setSelected(self, selected):
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.selectedChanged.emit(selected)

    def isSelected(self):
        return self._selected

    def _set_state(self, state):
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def setConverting(self):
        self._status_label.setText("⟳")
        self._status_label.setStyleSheet(f"color:{C['yellow']};font-size:15px;")
        self._fmt.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._set_state("converting")

    def setDone(self):
        self._status_label.setText("✓")
        self._status_label.setStyleSheet(f"color:{C['green']};font-size:15px;font-weight:bold;")
        self._set_state("done")

    def setError(self):
        self._status_label.setText("✕")
        self._status_label.setStyleSheet(f"color:{C['red']};font-size:15px;font-weight:bold;")
        self._set_state("error")

    def reset(self):
        self._status_label.setText("")
        self._status_label.setStyleSheet("")
        self._fmt.setEnabled(True)
        self._remove_btn.setEnabled(True)
        self._set_state("")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            parent = self.parent()
            while parent and not isinstance(parent, FileQueue):
                parent = parent.parent()
            if parent:
                parent.selectItem(self)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
#  FILE QUEUE  (drop zone + scrollable list)
# ═══════════════════════════════════════════════════════════════════════════
class FileQueue(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[FileItem] = []
        self._selected_item: Optional[FileItem] = None
        self.setAcceptDrops(True)
        self._dash_offset = 0
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(45)
        self._build()

    def _tick(self):
        if not self._items:
            self._dash_offset = (self._dash_offset + 1) % 24
            self.update()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setObjectName("stack")
        lay.addWidget(self._stack)

        # Empty drop zone
        dz = QtWidgets.QWidget()
        dz.setObjectName("dropZone")
        dl = QtWidgets.QVBoxLayout(dz)
        dl.setAlignment(QtCore.Qt.AlignCenter)
        dl.setSpacing(10)

        cloud = QtWidgets.QLabel()
        cloud.setPixmap(self._cloud(64, 64))
        cloud.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(cloud)

        title = QtWidgets.QLabel("Drop files here to add")
        title.setObjectName("dzTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(title)

        sub = QtWidgets.QLabel("PNG · JPG · WEBP · BMP · OPPSIE")
        sub.setObjectName("dzSub")
        sub.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(sub)

        self._stack.addWidget(dz)

        # File list scroll area
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("fileScroll")
        self._scroll.viewport().setAcceptDrops(False)

        self._list_widget = QtWidgets.QWidget()
        self._list_layout = QtWidgets.QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(6, 6, 6, 6)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        self._stack.addWidget(self._scroll)

    def paintEvent(self, event):
        if self._items:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        bg = QtGui.QColor(C["mantle"])
        bg.setAlpha(220)
        p.setBrush(bg)
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(r, 14, 14)
        pen = QtGui.QPen(QtGui.QColor(C["surface1"]), 2)
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setDashPattern([6, 4])
        pen.setDashOffset(self._dash_offset)
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)
        p.end()

    def selectItem(self, item):
        if self._selected_item:
            self._selected_item.setSelected(False)
        self._selected_item = item
        if item:
            item.setSelected(True)

    def selectedItem(self):
        return self._selected_item

    def addFile(self, path: Path):
        for item in self._items:
            if item.path.resolve() == path.resolve():
                return
        item = FileItem(path)
        item.removeRequested.connect(self.removeFile)
        item.selectedChanged.connect(self._on_item_selected)
        self._items.append(item)
        self._list_layout.insertWidget(self._list_layout.count() - 1, item)
        self._stack.setCurrentIndex(1)
        self.changed.emit()

    def _on_item_selected(self, selected):
        if selected:
            for it in self._items:
                if it is not self.sender():
                    it.setSelected(False)
            self._selected_item = self.sender()

    def removeFile(self, item: FileItem):
        if item in self._items:
            if self._selected_item == item:
                self._selected_item = None
            self._items.remove(item)
            self._list_layout.removeWidget(item)
            item.deleteLater()
            if not self._items:
                self._stack.setCurrentIndex(0)
            self.changed.emit()

    def clear(self):
        for item in list(self._items):
            self._list_layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._selected_item = None
        self._stack.setCurrentIndex(0)
        self.changed.emit()

    def items(self) -> List[FileItem]:
        return list(self._items)

    def checkedItems(self) -> List[FileItem]:
        return [it for it in self._items if it.isChecked()]

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_file():
                self.addFile(p)
        e.acceptProposedAction()

    @staticmethod
    def _cloud(w, h):
        pm = QtGui.QPixmap(w, h)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        grad = QtGui.QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QtGui.QColor(C["pink"]))
        grad.setColorAt(1, QtGui.QColor(C["mauve"]))
        p.setBrush(QtGui.QBrush(grad))
        p.setPen(QtCore.Qt.NoPen)
        cx, cy = w / 2, h / 2
        p.drawEllipse(QtCore.QRectF(cx - 20, cy - 14, 26, 26))
        p.drawEllipse(QtCore.QRectF(cx - 8, cy - 24, 28, 28))
        p.drawEllipse(QtCore.QRectF(cx + 8, cy - 14, 26, 26))
        p.drawRoundedRect(QtCore.QRectF(cx - 20, cy - 4, 44, 18), 8, 8)
        p.setBrush(QtGui.QColor(255, 255, 255, 30))
        p.drawRoundedRect(QtCore.QRectF(cx - 12, cy - 18, 30, 12), 6, 6)
        p.end()
        return pm


# ═══════════════════════════════════════════════════════════════════════════
#  GROUP BOX  (7-zip style titled section)
# ═══════════════════════════════════════════════════════════════════════════
class SectionGroup(QtWidgets.QGroupBox):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setObjectName("sectionGroup")


# ═══════════════════════════════════════════════════════════════════════════
#  CUSTOM TITLE BAR
# ═══════════════════════════════════════════════════════════════════════════
class TitleBar(QtWidgets.QWidget):
    closeClicked = QtCore.pyqtSignal()
    minimizeClicked = QtCore.pyqtSignal()
    maximizeClicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setObjectName("titleBar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(0)

        self.icon_label = QtWidgets.QLabel("⬡")
        self.icon_label.setObjectName("titleIcon")
        layout.addWidget(self.icon_label)

        self.title_label = QtWidgets.QLabel("Oppsie Convert")
        self.title_label.setObjectName("titleText")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.min_btn = QtWidgets.QPushButton("–")
        self.min_btn.setObjectName("titleMinBtn")
        self.min_btn.setFixedSize(32, 24)
        self.min_btn.clicked.connect(self.minimizeClicked)
        layout.addWidget(self.min_btn)

        self.max_btn = QtWidgets.QPushButton("□")
        self.max_btn.setObjectName("titleMaxBtn")
        self.max_btn.setFixedSize(32, 24)
        self.max_btn.clicked.connect(self.maximizeClicked)
        layout.addWidget(self.max_btn)

        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setObjectName("titleCloseBtn")
        self.close_btn.setFixedSize(32, 24)
        self.close_btn.clicked.connect(self.closeClicked)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.window().windowHandle():
                self.window().windowHandle().startSystemMove()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW  (7-zip style two-panel layout)
# ═══════════════════════════════════════════════════════════════════════════
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("Oppsie Convert")
        self.resize(1040, 680)
        self.setMinimumSize(880, 560)

        self._worker: Optional[ConversionWorker] = None
        self._converting = False
        self._output_folder: Optional[Path] = None

        self._build()
        self._style()
        self._setup_shortcuts()

    def _build(self):
        central = QtWidgets.QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar()
        self.title_bar.closeClicked.connect(self.close)
        self.title_bar.minimizeClicked.connect(self.showMinimized)
        self.title_bar.maximizeClicked.connect(self._toggle_maximize)
        main_layout.addWidget(self.title_bar)

        # Content
        content = QtWidgets.QWidget()
        content.setObjectName("content")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 18)
        content_layout.setSpacing(12)

        # Header row (archive name + format like 7-zip)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)
        brand = QtWidgets.QLabel("⬡  Oppsie Convert")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        version = QtWidgets.QLabel("v1.3.0")
        version.setObjectName("ver")
        header.addWidget(version)
        content_layout.addLayout(header)

        # Two-panel split: left = file list, right = settings
        split = QtWidgets.QHBoxLayout()
        split.setSpacing(14)

        # ─── Left panel: Files ─────────────────────────────
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(8)

        files_header = QtWidgets.QHBoxLayout()
        files_title = QtWidgets.QLabel("Files to Convert")
        files_title.setObjectName("panelTitle")
        files_header.addWidget(files_title)
        files_header.addStretch()

        self._count_label = QtWidgets.QLabel("0 items")
        self._count_label.setObjectName("countLabel")
        files_header.addWidget(self._count_label)
        left_panel.addLayout(files_header)

        self._queue = FileQueue()
        left_panel.addWidget(self._queue, 1)

        # File action buttons (Add / Clear / Select All)
        file_actions = QtWidgets.QHBoxLayout()
        file_actions.setSpacing(8)
        self._add_btn = QtWidgets.QPushButton("+  Add Files")
        self._add_btn.setObjectName("addBtn")
        self._add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._browse)
        file_actions.addWidget(self._add_btn)

        self._select_all_btn = QtWidgets.QPushButton("Select All")
        self._select_all_btn.setObjectName("secondaryBtn")
        self._select_all_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._select_all_btn.clicked.connect(self._select_all)
        file_actions.addWidget(self._select_all_btn)

        self._clear_btn = QtWidgets.QPushButton("Clear")
        self._clear_btn.setObjectName("secondaryBtn")
        self._clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_queue)
        file_actions.addWidget(self._clear_btn)

        file_actions.addStretch()
        left_panel.addLayout(file_actions)

        left_wrap = QtWidgets.QWidget()
        left_wrap.setLayout(left_panel)
        split.addWidget(left_wrap, 3)

        # ─── Right panel: Settings (7-zip style sections) ──
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(10)

        settings_title = QtWidgets.QLabel("Conversion Settings")
        settings_title.setObjectName("panelTitle")
        right_panel.addWidget(settings_title)

        # Group 1: Archive
        archive_group = SectionGroup("Archive")
        ag_layout = QtWidgets.QVBoxLayout(archive_group)
        ag_layout.setSpacing(8)
        ag_layout.setContentsMargins(14, 18, 14, 12)

        # Output format row
        fmt_row = QtWidgets.QHBoxLayout()
        fmt_label = QtWidgets.QLabel("Output format:")
        fmt_label.setObjectName("fieldLabel")
        fmt_label.setFixedWidth(110)
        fmt_row.addWidget(fmt_label)

        self._global_fmt = QtWidgets.QComboBox()
        self._global_fmt.addItems(FORMATS)
        self._global_fmt.setCurrentText("oppsie")
        self._global_fmt.setObjectName("settingCombo")
        self._global_fmt.currentTextChanged.connect(self._apply_global_format)
        fmt_row.addWidget(self._global_fmt, 1)
        ag_layout.addLayout(fmt_row)

        # Output folder row
        out_row = QtWidgets.QHBoxLayout()
        out_label = QtWidgets.QLabel("Output folder:")
        out_label.setObjectName("fieldLabel")
        out_label.setFixedWidth(110)
        out_row.addWidget(out_label)

        self._out_path = QtWidgets.QLineEdit()
        self._out_path.setReadOnly(True)
        self._out_path.setPlaceholderText("Same as source")
        self._out_path.setObjectName("outPath")
        out_row.addWidget(self._out_path, 1)

        self._out_btn = QtWidgets.QPushButton("…")
        self._out_btn.setObjectName("browseBtn")
        self._out_btn.setFixedSize(30, 28)
        self._out_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._out_btn.clicked.connect(self._choose_output_folder)
        out_row.addWidget(self._out_btn)
        ag_layout.addLayout(out_row)

        # Suffix row
        suf_row = QtWidgets.QHBoxLayout()
        suf_label = QtWidgets.QLabel("Filename suffix:")
        suf_label.setObjectName("fieldLabel")
        suf_label.setFixedWidth(110)
        suf_row.addWidget(suf_label)

        self._suffix_edit = QtWidgets.QLineEdit("_converted")
        self._suffix_edit.setObjectName("outPath")
        suf_row.addWidget(self._suffix_edit, 1)
        ag_layout.addLayout(suf_row)

        right_panel.addWidget(archive_group)

        # Group 2: Compression
        comp_group = SectionGroup("Compression")
        cg_layout = QtWidgets.QVBoxLayout(comp_group)
        cg_layout.setSpacing(8)
        cg_layout.setContentsMargins(14, 18, 14, 12)

        # Quality / compression level
        q_row = QtWidgets.QHBoxLayout()
        q_label = QtWidgets.QLabel("Compression level:")
        q_label.setObjectName("fieldLabel")
        q_label.setFixedWidth(110)
        q_row.addWidget(q_label)

        self._quality = QtWidgets.QComboBox()
        self._quality.addItems([
            "Lossless", "1 — Light", "2", "3 — Medium",
            "4", "5", "6", "7 — Max"
        ])
        self._quality.setObjectName("settingCombo")
        self._quality.setToolTip(
            "Higher values give better quality but larger files.\n"
            "Lossless is only available for OPPsie format."
        )
        q_row.addWidget(self._quality, 1)
        cg_layout.addLayout(q_row)

        # Update mode (keep / overwrite) - decorative but functional
        ow_row = QtWidgets.QHBoxLayout()
        ow_label = QtWidgets.QLabel("Overwrite mode:")
        ow_label.setObjectName("fieldLabel")
        ow_label.setFixedWidth(110)
        ow_row.addWidget(ow_label)

        self._overwrite = QtWidgets.QComboBox()
        self._overwrite.addItems(["Ask before overwrite", "Always overwrite", "Skip existing"])
        self._overwrite.setObjectName("settingCombo")
        ow_row.addWidget(self._overwrite, 1)
        cg_layout.addLayout(ow_row)

        right_panel.addWidget(comp_group)

        # Group 3: Options
        opt_group = SectionGroup("Options")
        og_layout = QtWidgets.QVBoxLayout(opt_group)
        og_layout.setSpacing(6)
        og_layout.setContentsMargins(14, 18, 14, 12)

        self._open_after = QtWidgets.QCheckBox("Open output folder when done")
        self._open_after.setObjectName("optCheck")
        og_layout.addWidget(self._open_after)

        self._keep_meta = QtWidgets.QCheckBox("Preserve metadata (EXIF)")
        self._keep_meta.setObjectName("optCheck")
        self._keep_meta.setChecked(True)
        og_layout.addWidget(self._keep_meta)

        self._delete_orig = QtWidgets.QCheckBox("Delete original files after success")
        self._delete_orig.setObjectName("optCheck")
        og_layout.addWidget(self._delete_orig)

        right_panel.addWidget(opt_group)

        right_panel.addStretch()

        right_wrap = QtWidgets.QWidget()
        right_wrap.setLayout(right_panel)
        right_wrap.setObjectName("rightPanel")
        right_wrap.setFixedWidth(360)
        split.addWidget(right_wrap)

        content_layout.addLayout(split, 1)

        # ─── Progress bar ────────────────────────────────────
        self._bar = GlowBar()
        self._bar.hide()
        content_layout.addWidget(self._bar)

        # ─── Bottom action bar (OK / Cancel / Help style) ──
        action_bar = QtWidgets.QHBoxLayout()
        action_bar.setSpacing(10)

        # Status (left)
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(8)
        self._dot = StatusDot()
        status_row.addWidget(self._dot)
        self._status_label = QtWidgets.QLabel("Ready — add files to begin")
        self._status_label.setObjectName("statusText")
        self._status_label.setWordWrap(False)
        status_row.addWidget(self._status_label, 1)
        action_bar.addLayout(status_row, 1)

        # Buttons (right) — 7-zip OK / Cancel / Help
        self._help_btn = QtWidgets.QPushButton("Help")
        self._help_btn.setObjectName("ghostBtn")
        self._help_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._help_btn.clicked.connect(self._show_help)
        action_bar.addWidget(self._help_btn)

        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        action_bar.addWidget(self._cancel_btn)

        self._convert_btn = QtWidgets.QPushButton("OK — Convert")
        self._convert_btn.setObjectName("convBtn")
        self._convert_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._convert)
        action_bar.addWidget(self._convert_btn)

        content_layout.addLayout(action_bar)

        main_layout.addWidget(content)

        self._queue.changed.connect(self._on_queue_changed)

    def _setup_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self).activated.connect(self._browse)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(self._convert)
        QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self).activated.connect(self._delete_selected)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self).activated.connect(self._cancel_conversion)
        QtWidgets.QShortcut(QtGui.QKeySequence("F1"), self).activated.connect(self._show_help)

    def _select_all(self):
        items = self._queue.items()
        if not items:
            return
        all_checked = all(it.isChecked() for it in items)
        for it in items:
            it.setChecked(not all_checked)

    def _apply_global_format(self, fmt):
        for it in self._queue.items():
            it._fmt.setCurrentText(fmt)

    def _show_help(self):
        QtWidgets.QMessageBox.information(
            self, "Help — Oppsie Convert",
            "Shortcuts:\n"
            "  Ctrl+O      — Add files\n"
            "  Ctrl+Enter  — Start conversion\n"
            "  Delete      — Remove selected file\n"
            "  Esc         — Cancel conversion\n"
            "  F1          — This help\n\n"
            "Tips:\n"
            "  • Hover a thumbnail to preview.\n"
            "  • Click a row to select it.\n"
            "  • Use the per-file dropdown to override the global format.\n"
            "  • Uncheck the box on the left to skip a file."
        )

    def _delete_selected(self):
        if self._converting:
            return
        item = self._queue.selectedItem()
        if item:
            self._queue.removeFile(item)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ─── Slots ────────────────────────────────────────────────
    def _choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", str(Path.home())
        )
        if folder:
            self._output_folder = Path(folder)
            self._out_path.setText(str(self._output_folder))
        else:
            self._output_folder = None
            self._out_path.clear()

    def _on_queue_changed(self):
        count = len(self._queue.items())
        checked = len(self._queue.checkedItems())
        self._count_label.setText(f"{checked}/{count} selected" if count else "0 items")
        self._convert_btn.setEnabled(checked > 0 and not self._converting)
        if count == 0:
            self._status_label.setText("Ready — add files to begin")
            self._dot.setColor("green")
        else:
            self._status_label.setText(f"{count} file{'s' if count > 1 else ''} in queue · {checked} selected")
            self._dot.setColor("green")

    def _clear_queue(self):
        if self._converting:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Clear Queue",
            "Remove all files from the queue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._queue.clear()

    def _browse(self):
        if self._converting:
            return
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.oppsie);;All files (*)"
        )
        for p in paths:
            self._queue.addFile(Path(p))

    def _convert(self):
        items = self._queue.checkedItems()
        if not items or self._converting:
            return

        self._converting = True
        self._convert_btn.setEnabled(False)
        self._add_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._select_all_btn.setEnabled(False)
        self._quality.setEnabled(False)
        self._out_btn.setEnabled(False)
        self._global_fmt.setEnabled(False)
        self._cancel_btn.show()
        self._cancel_btn.setEnabled(True)

        lossy = self._quality.currentIndex()
        for item in items:
            item.reset()

        self._convert_next(items, 0, lossy)

    def _convert_next(self, items, idx, lossy):
        while idx < len(items) and items[idx]._status_label.text() in ("✓", "✕"):
            idx += 1

        if idx >= len(items):
            self._on_all_done(items)
            return

        item = items[idx]
        item.setConverting()
        self._status_label.setText(
            f"Converting {item.path.name}  ({idx + 1}/{len(items)})…"
        )
        self._dot.setColor("yellow")
        self._dot.setActive(True)
        self._bar.show()
        self._bar.reset()
        self._bar.animateTo(5)

        if self._output_folder:
            dst_dir = self._output_folder
        else:
            dst_dir = item.path.parent
        ext = ".oppsie" if item.target_fmt == "oppsie" else f".{item.target_fmt}"
        suffix = self._suffix_edit.text().strip() or ""
        dst = dst_dir / (item.path.stem + suffix + ext)

        # Overwrite handling
        if dst.exists():
            mode = self._overwrite.currentIndex()
            if mode == 2:  # Skip
                item._status_label.setText("⊘")
                item._status_label.setStyleSheet(f"color:{C['overlay1']};font-size:14px;")
                self._convert_next(items, idx + 1, lossy)
                return
            elif mode == 0:  # Ask
                reply = QtWidgets.QMessageBox.question(
                    self, "File Exists",
                    f"{dst.name} already exists.\nOverwrite?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    self._convert_next(items, idx + 1, lossy)
                    return

        dst.parent.mkdir(parents=True, exist_ok=True)

        self._worker = ConversionWorker(
            str(item.path), str(dst), item.target_fmt, lossy
        )
        self._worker.progress.connect(self._bar.animateTo)
        self._worker.status.connect(self._status_label.setText)
        self._worker.done.connect(
            lambda r, i=item, ii=idx, itms=items, l=lossy:
                self._on_file_done(r, i, ii, itms, l)
        )
        self._worker.start()

    def _on_file_done(self, result, item, idx, items, lossy):
        if result.get("ok"):
            item.setDone()
            src, dst, ms = result["src"], result["dst"], result["ms"]
            try:
                src_size = src.stat().st_size
                dst_size = dst.stat().st_size
                ratio = dst_size / src_size * 100 if src_size else 0
                self._status_label.setText(
                    f"{src.name} → {dst.name}  |  "
                    f"{human_size(src_size)} → {human_size(dst_size)}  |  "
                    f"{ratio:.1f}%  |  {ms:.1f} ms"
                )
                # Optional: delete original
                if self._delete_orig.isChecked():
                    try:
                        src.unlink()
                    except OSError:
                        pass
            except OSError:
                self._status_label.setText(
                    f"{src.name} → {dst.name}  |  {ms:.1f} ms"
                )
        else:
            item.setError()
            err = result.get("error", "Unknown error")
            self._status_label.setText(f"Failed: {err}")
            self._dot.setColor("red")
            self._dot.setActive(False)

        self._convert_next(items, idx + 1, lossy)

    def _on_all_done(self, items):
        self._converting = False
        self._bar.hide()
        self._convert_btn.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        self._select_all_btn.setEnabled(True)
        self._quality.setEnabled(True)
        self._out_btn.setEnabled(True)
        self._global_fmt.setEnabled(True)
        self._cancel_btn.hide()

        done = sum(1 for i in items if i._status_label.text() == "✓")
        failed = sum(1 for i in items if i._status_label.text() == "✕")

        if failed == 0:
            msg = f"All {done} file{'s' if done != 1 else ''} converted successfully"
            self._status_label.setText(msg)
            self._dot.setColor("green")
            self._dot.setActive(True)
            if self._open_after.isChecked() and self._output_folder:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._output_folder)))
            QtWidgets.QMessageBox.information(self, "Conversion Complete", msg)
        else:
            msg = f"{done} succeeded, {failed} failed"
            self._status_label.setText(msg)
            self._dot.setColor("peach")
            self._dot.setActive(False)
            QtWidgets.QMessageBox.warning(self, "Conversion Complete", msg)

    def _cancel_conversion(self):
        if not self._converting:
            return
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.terminate()
            self._worker.wait(1000)
            self._worker = None
        self._converting = False
        self._bar.hide()
        self._convert_btn.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        self._select_all_btn.setEnabled(True)
        self._quality.setEnabled(True)
        self._out_btn.setEnabled(True)
        self._global_fmt.setEnabled(True)
        self._cancel_btn.hide()
        self._status_label.setText("Conversion cancelled")
        self._dot.setColor("peach")
        self._dot.setActive(False)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.terminate()
            self._worker.wait(2000)
        event.accept()

    # ─── Styling ──────────────────────────────────────────────
    def _style(self):
        self.setStyleSheet(f"""
            QWidget#centralWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(30,30,46,0.94),
                    stop:1 rgba(24,24,37,0.97));
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.06);
            }}

            /* ─── Title bar ─────────────────────────────────── */
            QWidget#titleBar {{
                background: rgba(17,17,27,0.7);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }}
            QLabel#titleIcon {{
                color: {C['mauve']};
                font-size: 18px;
                padding-left: 6px;
            }}
            QLabel#titleText {{
                color: {C['text']};
                font-size: 13px;
                font-weight: 600;
                padding-left: 8px;
                letter-spacing: 0.3px;
            }}
            QPushButton#titleMinBtn,
            QPushButton#titleMaxBtn,
            QPushButton#titleCloseBtn {{
                background: transparent;
                border: none;
                color: {C['overlay2']};
                font-size: 13px;
                font-weight: 500;
                padding: 0;
                border-radius: 4px;
            }}
            QPushButton#titleMinBtn:hover,
            QPushButton#titleMaxBtn:hover {{
                background: rgba(255,255,255,0.08);
                color: {C['text']};
            }}
            QPushButton#titleCloseBtn:hover {{
                background: rgba(243,139,168,0.2);
                color: {C['red']};
            }}

            QWidget#content {{
                background: transparent;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }}

            /* ─── Header ────────────────────────────────────── */
            QLabel#brand {{
                color: {C['mauve']};
                font-size: 20px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QLabel#ver {{
                color: {C['surface2']};
                font-size: 11px;
                padding-right: 2px;
            }}

            /* ─── Panel titles ─────────────────────────────── */
            QLabel#panelTitle {{
                color: {C['overlay2']};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1.2px;
                text-transform: uppercase;
                padding-bottom: 2px;
            }}
            QLabel#countLabel {{
                color: {C['overlay1']};
                font-size: 11px;
                font-weight: 500;
            }}

            /* ─── Right panel background ───────────────────── */
            QWidget#rightPanel {{
                background: transparent;
            }}

            /* ─── Section group (7-zip style box) ──────────── */
            QGroupBox#sectionGroup {{
                background: rgba(17,17,27,0.5);
                border: 1px solid {C['surface0']};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 8px;
                font-size: 11px;
            }}
            QGroupBox#sectionGroup::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                color: {C['mauve']};
                font-weight: 700;
                letter-spacing: 0.8px;
                background: {C['base']};
            }}

            QLabel#fieldLabel {{
                color: {C['overlay2']};
                font-size: 12px;
                font-weight: 500;
            }}

            /* ─── Drop zone ─────────────────────────────────── */
            QWidget#dropZone {{ background: transparent; border: none; }}
            QLabel#dzTitle {{
                color: {C['text']};
                font-size: 16px;
                font-weight: 300;
            }}
            QLabel#dzSub {{
                color: {C['overlay0']};
                font-size: 11px;
                letter-spacing: 1.5px;
            }}

            /* ─── File scroll area ──────────────────────────── */
            QScrollArea#fileScroll {{
                background: rgba(17,17,27,0.55);
                border: 1px solid {C['surface0']};
                border-radius: 10px;
            }}

            /* ─── File item ─────────────────────────────────── */
            QFrame#fileItem {{
                background: rgba(24,24,37,0.7);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px;
            }}
            QFrame#fileItem[selected="true"] {{
                border: 1px solid {C['mauve']};
                background: rgba(203,166,247,0.08);
            }}
            QFrame#fileItem[state="converting"] {{
                background: rgba(203,166,247,0.08);
                border-color: rgba(203,166,247,0.25);
            }}
            QFrame#fileItem[state="done"] {{
                background: rgba(166,227,161,0.06);
                border-color: rgba(166,227,161,0.18);
            }}
            QFrame#fileItem[state="error"] {{
                background: rgba(243,139,168,0.06);
                border-color: rgba(243,139,168,0.18);
            }}

            QCheckBox#fileCheck {{
                spacing: 0;
            }}
            QCheckBox#fileCheck::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid {C['surface2']};
                background: {C['crust']};
            }}
            QCheckBox#fileCheck::indicator:checked {{
                background: {C['mauve']};
                border-color: {C['mauve']};
                image: none;
            }}

            QLabel#fileName {{
                color: {C['text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#fileSize {{
                color: {C['overlay1']};
                font-size: 11px;
                font-family: "Cascadia Code", "Consolas", monospace;
            }}
            QLabel#arrow {{
                color: {C['surface2']};
                font-size: 14px;
            }}

            /* ─── Combo boxes ───────────────────────────────── */
            QComboBox#fmtCombo, QComboBox#settingCombo {{
                background: {C['crust']};
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 500;
                min-height: 20px;
            }}
            QComboBox#fmtCombo:hover, QComboBox#settingCombo:hover {{
                border-color: {C['surface2']};
            }}
            QComboBox#fmtCombo::drop-down,
            QComboBox#settingCombo::drop-down {{
                border: none;
                width: 20px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }}
            QComboBox#fmtCombo::down-arrow,
            QComboBox#settingCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {C['overlay1']};
                margin-right: 6px;
            }}
            QComboBox#fmtCombo QAbstractItemView,
            QComboBox#settingCombo QAbstractItemView {{
                background: {C['crust']};
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                selection-background-color: {C['surface0']};
                selection-color: {C['mauve']};
                outline: none;
                padding: 4px;
            }}

            /* ─── Line edits ────────────────────────────────── */
            QLineEdit#outPath {{
                background: {C['crust']};
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
            }}
            QLineEdit#outPath:focus {{
                border-color: {C['mauve']};
            }}

            /* ─── Buttons ───────────────────────────────────── */
            QPushButton#addBtn {{
                background: rgba(203,166,247,0.1);
                color: {C['mauve']};
                border: 1px solid rgba(203,166,247,0.3);
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#addBtn:hover {{
                background: rgba(203,166,247,0.18);
                border-color: {C['mauve']};
            }}
            QPushButton#addBtn:disabled {{
                color: {C['surface2']};
                border-color: {C['surface1']};
                background: transparent;
            }}

            QPushButton#secondaryBtn {{
                background: transparent;
                color: {C['overlay2']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton#secondaryBtn:hover {{
                background: rgba(255,255,255,0.04);
                color: {C['text']};
                border-color: {C['surface2']};
            }}
            QPushButton#secondaryBtn:disabled {{
                color: {C['surface0']};
                border-color: {C['surface0']};
            }}

            QPushButton#browseBtn {{
                background: {C['surface0']};
                color: {C['text']};
                border: 1px solid {C['surface1']};
                border-radius: 6px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#browseBtn:hover {{
                background: {C['surface1']};
                border-color: {C['surface2']};
            }}
            QPushButton#browseBtn:disabled {{
                color: {C['surface2']};
                background: {C['surface0']};
            }}

            /* ─── Primary convert button (OK style) ────────── */
            QPushButton#convBtn {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['mauve']}, stop:1 {C['pink']});
                color: {C['base']};
                border: none;
                border-radius: 6px;
                padding: 8px 22px;
                font-weight: bold;
                font-size: 13px;
                min-width: 110px;
            }}
            QPushButton#convBtn:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['lavender']}, stop:1 {C['pink']});
            }}
            QPushButton#convBtn:disabled {{
                background: {C['surface0']};
                color: {C['surface2']};
            }}

            QPushButton#cancelBtn {{
                background: rgba(243,139,168,0.12);
                color: {C['red']};
                border: 1px solid rgba(243,139,168,0.35);
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton#cancelBtn:hover {{
                background: rgba(243,139,168,0.22);
                border-color: {C['red']};
            }}

            QPushButton#ghostBtn {{
                background: transparent;
                color: {C['overlay1']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton#ghostBtn:hover {{
                color: {C['text']};
                border-color: {C['surface2']};
                background: rgba(255,255,255,0.03);
            }}

            /* ─── Remove button ─────────────────────────────── */
            QPushButton#removeBtn {{
                background: transparent;
                color: {C['surface2']};
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton#removeBtn:hover {{
                background: rgba(243,139,168,0.15);
                color: {C['red']};
            }}
            QPushButton#removeBtn:disabled {{
                color: {C['surface0']};
            }}

            /* ─── Options checkboxes ────────────────────────── */
            QCheckBox#optCheck {{
                color: {C['subtext1']};
                font-size: 12px;
                spacing: 8px;
                padding: 2px 0;
            }}
            QCheckBox#optCheck::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid {C['surface2']};
                background: {C['crust']};
            }}
            QCheckBox#optCheck::indicator:checked {{
                background: {C['mauve']};
                border-color: {C['mauve']};
            }}

            /* ─── Status label ──────────────────────────────── */
            QLabel#statusText {{
                color: {C['overlay2']};
                font-size: 12px;
                font-family: "Cascadia Code", "Consolas", monospace;
            }}

            /* ─── Scroll bars ───────────────────────────────── */
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {C['surface1']};
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C['surface2']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}

            /* ─── Message boxes ─────────────────────────────── */
            QMessageBox {{
                background: {C['base']};
            }}
            QMessageBox QLabel {{
                color: {C['text']};
                font-size: 13px;
            }}
            QMessageBox QPushButton {{
                background: {C['surface0']};
                color: {C['text']};
                border: 1px solid {C['surface1']};
                border-radius: 5px;
                padding: 6px 16px;
                font-size: 12px;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background: {C['surface1']};
                border-color: {C['surface2']};
            }}
        """)


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(C["base"]))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(C["text"]))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(C["crust"]))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(C["surface0"]))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(C["text"]))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(C["surface0"]))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(C["text"]))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()