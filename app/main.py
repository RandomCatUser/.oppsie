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

        # Outer glow
        p.setBrush(glow)
        rect = self.rect().adjusted(-4, -4, 4, 4)
        p.drawEllipse(rect)

        # Core
        p.setBrush(self._color)
        p.drawEllipse(self.rect())
        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  GLOW PROGRESS BAR  (thin, animated with shimmer)
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

        # Background glow
        glow = QtGui.QColor(C["mauve"])
        glow.setAlpha(25)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(fill_rect.adjusted(-2, -3, 2, 3), radius + 2, radius + 2)

        # Gradient fill
        grad = QtGui.QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
        grad.setColorAt(0, QtGui.QColor(C["mauve"]))
        grad.setColorAt(1, QtGui.QColor(C["pink"]))
        p.setBrush(grad)
        p.drawRoundedRect(fill_rect, radius, radius)

        # Shimmer highlight
        shimmer = QtGui.QLinearGradient(0, rect.y(), 0, rect.center().y())
        shimmer.setColorAt(0, QtGui.QColor(255, 255, 255, 50))
        shimmer.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        p.setBrush(shimmer)
        p.drawRoundedRect(fill_rect, radius, radius)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  FILE ITEM  (with selection and hover preview)
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
        shadow.setBlurRadius(16)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def _build(self):
        self.setFixedHeight(64)
        self.setObjectName("fileItem")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        # Thumbnail (clickable for preview)
        self._thumb_label = QtWidgets.QLabel()
        self._thumb_label.setFixedSize(44, 44)
        self._thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self._thumb_label.setObjectName("thumbLabel")
        pm = make_thumbnail(self.path, 44)
        if pm:
            self._thumb_label.setPixmap(pm)
        else:
            self._thumb_label.setText("📄")
            self._thumb_label.setStyleSheet("font-size:20px;")
        lay.addWidget(self._thumb_label)

        # File info
        info = QtWidgets.QVBoxLayout()
        info.setSpacing(1)
        name = QtWidgets.QLabel(self.path.name)
        name.setObjectName("fileName")
        lay.addLayout(info, 1)
        info.addWidget(name)
        try:
            size = QtWidgets.QLabel(human_size(self.path.stat().st_size))
        except OSError:
            size = QtWidgets.QLabel("—")
        size.setObjectName("fileSize")
        info.addWidget(size)

        # Arrow
        arrow = QtWidgets.QLabel("→")
        arrow.setObjectName("arrow")
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(arrow)

        # Format combo
        self._fmt = QtWidgets.QComboBox()
        self._fmt.addItems(FORMATS)
        self._fmt.setCurrentText("oppsie")
        self._fmt.setObjectName("fmtCombo")
        self._fmt.setFixedWidth(105)
        self._fmt.currentTextChanged.connect(
            lambda t: setattr(self, "target_fmt", t)
        )
        lay.addWidget(self._fmt)

        # Status icon
        self._status_label = QtWidgets.QLabel()
        self._status_label.setFixedSize(24, 24)
        self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(self._status_label)

        # Remove button
        self._remove_btn = QtWidgets.QPushButton("✕")
        self._remove_btn.setObjectName("removeBtn")
        self._remove_btn.setFixedSize(28, 28)
        self._remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(
            lambda: self.removeRequested.emit(self)
        )
        lay.addWidget(self._remove_btn)

        # Install event filter for hover preview
        self._thumb_label.installEventFilter(self)
        self.installEventFilter(self)

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
        # Create a popup window
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
        # Position near the thumbnail
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
        self._status_label.setStyleSheet(f"color:{C['yellow']};font-size:16px;")
        self._fmt.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._set_state("converting")

    def setDone(self):
        self._status_label.setText("✓")
        self._status_label.setStyleSheet(f"color:{C['green']};font-size:16px;font-weight:bold;")
        self._set_state("done")

    def setError(self):
        self._status_label.setText("✕")
        self._status_label.setStyleSheet(f"color:{C['red']};font-size:16px;font-weight:bold;")
        self._set_state("error")

    def reset(self):
        self._status_label.setText("")
        self._status_label.setStyleSheet("")
        self._fmt.setEnabled(True)
        self._remove_btn.setEnabled(True)
        self._set_state("")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            # Select this item, deselect others in the queue
            parent = self.parent()
            while parent and not isinstance(parent, FileQueue):
                parent = parent.parent()
            if parent:
                parent.selectItem(self)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
#  FILE QUEUE  (drop zone + scrollable list, with selection support)
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
        dl.setSpacing(12)

        cloud = QtWidgets.QLabel()
        cloud.setPixmap(self._cloud(72, 72))
        cloud.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(cloud)

        title = QtWidgets.QLabel("Drop your files here")
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
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        self._stack.addWidget(self._scroll)

    def paintEvent(self, event):
        if self._items:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        # Background with glass effect
        bg = QtGui.QColor(C["mantle"])
        bg.setAlpha(220)
        p.setBrush(bg)
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(r, 16, 16)

        # Dashed border
        pen = QtGui.QPen(QtGui.QColor(C["surface1"]), 2)
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setDashPattern([6, 4])
        pen.setDashOffset(self._dash_offset)
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(r, 16, 16)
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
            # Deselect others
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

        # Highlight
        p.setBrush(QtGui.QColor(255, 255, 255, 30))
        p.drawRoundedRect(QtCore.QRectF(cx - 12, cy - 18, 30, 12), 6, 6)
        p.end()
        return pm


# ═══════════════════════════════════════════════════════════════════════════
#  CUSTOM TITLE BAR
# ═══════════════════════════════════════════════════════════════════════════
class TitleBar(QtWidgets.QWidget):
    closeClicked = QtCore.pyqtSignal()
    minimizeClicked = QtCore.pyqtSignal()
    maximizeClicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setObjectName("titleBar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(0)

        # Icon and title
        self.icon_label = QtWidgets.QLabel("⬡")
        self.icon_label.setObjectName("titleIcon")
        layout.addWidget(self.icon_label)

        self.title_label = QtWidgets.QLabel("Oppsie Convert")
        self.title_label.setObjectName("titleText")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window controls
        self.min_btn = QtWidgets.QPushButton("–")
        self.min_btn.setObjectName("titleMinBtn")
        self.min_btn.setFixedSize(32, 26)
        self.min_btn.clicked.connect(self.minimizeClicked)
        layout.addWidget(self.min_btn)

        self.max_btn = QtWidgets.QPushButton("□")
        self.max_btn.setObjectName("titleMaxBtn")
        self.max_btn.setFixedSize(32, 26)
        self.max_btn.clicked.connect(self.maximizeClicked)
        layout.addWidget(self.max_btn)

        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setObjectName("titleCloseBtn")
        self.close_btn.setFixedSize(32, 26)
        self.close_btn.clicked.connect(self.closeClicked)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.window().windowHandle().startSystemMove()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW  (frameless with glass effect, shortcuts, output folder)
# ═══════════════════════════════════════════════════════════════════════════
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("Oppsie Convert")
        self.resize(980, 720)O
        self.setMinimumSize(820, 580)

        self._worker: Optional[ConversionWorker] = None
        self._converting = False
        self._output_folder: Optional[Path] = None

        self._build()
        self._style()
        self._setup_shortcuts()

    def _build(self):
        # Central widget with rounded background and glass effect
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

        # Content area (with padding)
        content = QtWidgets.QWidget()
        content.setObjectName("content")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(30, 20, 30, 22)
        content_layout.setSpacing(18)

        # ── Header ──────────────────────────────────────────
        header = QtWidgets.QHBoxLayout()
        brand = QtWidgets.QLabel("⬡  Fast Convert")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        version = QtWidgets.QLabel("v1.3.0")
        version.setObjectName("ver")
        header.addWidget(version)
        content_layout.addLayout(header)

        # ── File queue ──────────────────────────────────────
        self._queue = FileQueue()
        self._queue.setMinimumHeight(280)
        content_layout.addWidget(self._queue, 1)

        # ── Progress bar ────────────────────────────────────
        self._bar = GlowBar()
        self._bar.hide()
        content_layout.addWidget(self._bar)

        # ── Action bar (first row: Add, Clear, Output) ────
        action_row1 = QtWidgets.QHBoxLayout()
        action_row1.setSpacing(12)

        self._add_btn = QtWidgets.QPushButton("+  Add Files")
        self._add_btn.setObjectName("addBtn")
        self._add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._browse)
        action_row1.addWidget(self._add_btn)

        self._clear_btn = QtWidgets.QPushButton("Clear All")
        self._clear_btn.setObjectName("clearBtn")
        self._clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_queue)
        action_row1.addWidget(self._clear_btn)

        action_row1.addStretch()

        # Output folder
        out_label = QtWidgets.QLabel("Output:")
        out_label.setObjectName("outLabel")
        action_row1.addWidget(out_label)

        self._out_path = QtWidgets.QLineEdit()
        self._out_path.setReadOnly(True)
        self._out_path.setPlaceholderText("Same as source")
        self._out_path.setObjectName("outPath")
        self._out_path.setFixedWidth(200)
        action_row1.addWidget(self._out_path)

        self._out_btn = QtWidgets.QPushButton("Browse…")
        self._out_btn.setObjectName("outBtn")
        self._out_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._out_btn.clicked.connect(self._choose_output_folder)
        action_row1.addWidget(self._out_btn)

        content_layout.addLayout(action_row1)

        # ── Action bar (second row: Quality, Convert, Cancel)
        action_row2 = QtWidgets.QHBoxLayout()
        action_row2.setSpacing(12)

        q_label = QtWidgets.QLabel("Quality")
        q_label.setObjectName("qualLabel")
        action_row2.addWidget(q_label)

        self._quality = QtWidgets.QComboBox()
        self._quality.addItems([
            "Lossless", "1 — Light", "2", "3 — Medium",
            "4", "5", "6", "7 — Max"
        ])
        self._quality.setObjectName("qualCombo")
        self._quality.setFixedWidth(135)
        self._quality.setToolTip(
            "Higher values give better quality but larger files.\n"
            "Lossless is only available for OPPsie format."
        )
        action_row2.addWidget(self._quality)

        action_row2.addStretch()

        self._convert_btn = QtWidgets.QPushButton("Convert Now")
        self._convert_btn.setObjectName("convBtn")
        self._convert_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._convert)
        action_row2.addWidget(self._convert_btn)

        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        action_row2.addWidget(self._cancel_btn)

        content_layout.addLayout(action_row2)

        # ── Status bar ──────────────────────────────────────
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(12)

        self._dot = StatusDot()
        status_row.addWidget(self._dot)

        self._status_label = QtWidgets.QLabel("Ready — add files to begin")
        self._status_label.setObjectName("statusText")
        self._status_label.setWordWrap(True)
        status_row.addWidget(self._status_label, 1)

        credit = QtWidgets.QLabel("Created by RandomCatUser")
        credit.setObjectName("credit")
        status_row.addWidget(credit)

        content_layout.addLayout(status_row)

        main_layout.addWidget(content)

        # Signals
        self._queue.changed.connect(self._on_queue_changed)

    def _setup_shortcuts(self):
        # Ctrl+O: Open files
        open_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self._browse)

        # Ctrl+Enter: Start conversion
        convert_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        convert_shortcut.activated.connect(self._convert)

        # Delete: Remove selected item
        delete_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self._delete_selected)

        # Escape: Cancel conversion (if running)
        escape_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self)
        escape_shortcut.activated.connect(self._cancel_conversion)

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
        self._convert_btn.setEnabled(count > 0 and not self._converting)
        if count == 0:
            self._status_label.setText("Ready — add files to begin")
            self._dot.setColor("green")
        else:
            self._status_label.setText(f"{count} file{'s' if count > 1 else ''} in queue")
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
        items = self._queue.items()
        if not items or self._converting:
            return

        self._converting = True
        self._convert_btn.setEnabled(False)
        self._add_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._quality.setEnabled(False)
        self._out_btn.setEnabled(False)
        self._cancel_btn.show()
        self._cancel_btn.setEnabled(True)

        lossy = self._quality.currentIndex()
        for item in items:
            item.reset()

        self._convert_next(items, 0, lossy)

    def _convert_next(self, items, idx, lossy):
        # Skip already processed (✓ or ✕)
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
        self._bar.show()
        self._bar.reset()
        self._bar.animateTo(5)

        # Determine destination path
        if self._output_folder:
            dst_dir = self._output_folder
        else:
            dst_dir = item.path.parent
        ext = ".oppsie" if item.target_fmt == "oppsie" else f".{item.target_fmt}"
        dst = dst_dir / (item.path.stem + "_converted" + ext)
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

        # Continue with next item
        self._convert_next(items, idx + 1, lossy)

    def _on_all_done(self, items):
        self._converting = False
        self._bar.hide()
        self._convert_btn.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        self._quality.setEnabled(True)
        self._out_btn.setEnabled(True)
        self._cancel_btn.hide()

        done = sum(1 for i in items if i._status_label.text() == "✓")
        failed = sum(1 for i in items if i._status_label.text() == "✕")

        if failed == 0:
            msg = f"All {done} file{'s' if done != 1 else ''} converted successfully"
            self._status_label.setText(msg)
            self._dot.setColor("green")
            # System notification (message box)
            QtWidgets.QMessageBox.information(self, "Conversion Complete", msg)
        else:
            msg = f"{done} succeeded, {failed} failed"
            self._status_label.setText(msg)
            self._dot.setColor("peach")
            self._dot.setActive(False)
            QtWidgets.QMessageBox.warning(self, "Conversion Complete", msg)

    def _cancel_conversion(self):
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
        self._quality.setEnabled(True)
        self._out_btn.setEnabled(True)
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
            /* ─── Root ───────────────────────────────────────────────── */
            QWidget#centralWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(30,30,46,0.92),
                    stop:1 rgba(24,24,37,0.96));
                border-radius: 18px;
                border: 1px solid rgba(255,255,255,0.06);
            }}

            /* ─── Title bar ──────────────────────────────────────────── */
            QWidget#titleBar {{
                background: rgba(17,17,27,0.6);
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }}
            QLabel#titleIcon {{
                color: {C['mauve']};
                font-size: 20px;
                padding-left: 8px;
            }}
            QLabel#titleText {{
                color: {C['text']};
                font-size: 15px;
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
                font-size: 14px;
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

            /* ─── Content ────────────────────────────────────────────── */
            QWidget#content {{
                background: transparent;
                border-bottom-left-radius: 18px;
                border-bottom-right-radius: 18px;
            }}

            /* ─── Header ─────────────────────────────────────────────── */
            QLabel#brand {{
                color: {C['mauve']};
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 0.6px;
            }}
            QLabel#ver {{
                color: {C['surface2']};
                font-size: 12px;
                padding-right: 4px;
            }}

            /* ─── Stacked widget ────────────────────────────────────── */
            QStackedWidget#stack {{
                background: transparent;
                border: none;
            }}

            /* ─── Drop zone ──────────────────────────────────────────── */
            QWidget#dropZone {{
                background: transparent;
                border: none;
            }}
            QLabel#dzTitle {{
                color: {C['text']};
                font-size: 20px;
                font-weight: 300;
            }}
            QLabel#dzSub {{
                color: {C['overlay0']};
                font-size: 13px;
                letter-spacing: 1.8px;
            }}

            /* ─── File scroll area ──────────────────────────────────── */
            QScrollArea#fileScroll {{
                background: rgba(24,24,37,0.5);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 16px;
            }}

            /* ─── File item ──────────────────────────────────────────── */
            QFrame#fileItem {{
                background: rgba(17,17,27,0.8);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px;
            }}
            QFrame#fileItem[selected="true"] {{
                border: 2px solid {C['mauve']};
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

            QLabel#fileName {{
                color: {C['text']};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#fileSize {{
                color: {C['overlay1']};
                font-size: 11px;
            }}
            QLabel#arrow {{
                color: {C['surface2']};
                font-size: 16px;
                padding: 0 6px;
            }}

            /* ─── Combo boxes ───────────────────────────────────────── */
            QComboBox#fmtCombo, QComboBox#qualCombo {{
                background: rgba(30,30,46,0.7);
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox#fmtCombo::drop-down,
            QComboBox#qualCombo::drop-down {{
                border: none;
                width: 22px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }}
            QComboBox#fmtCombo::down-arrow,
            QComboBox#qualCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {C['overlay1']};
                margin-right: 6px;
            }}
            QComboBox#fmtCombo QAbstractItemView,
            QComboBox#qualCombo QAbstractItemView {{
                background: {C['crust']};
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                selection-background-color: {C['surface0']};
                selection-color: {C['mauve']};
                outline: none;
            }}

            /* ─── Buttons ────────────────────────────────────────────── */
            QPushButton#addBtn, QPushButton#clearBtn {{
                background: rgba(203,166,247,0.06);
                color: {C['mauve']};
                border: 1px solid rgba(203,166,247,0.3);
                border-radius: 22px;
                padding: 9px 22px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#addBtn:hover, QPushButton#clearBtn:hover {{
                background: rgba(203,166,247,0.12);
                border-color: {C['mauve']};
            }}
            QPushButton#addBtn:disabled, QPushButton#clearBtn:disabled {{
                color: {C['surface2']};
                border-color: {C['surface1']};
                background: transparent;
            }}

            QPushButton#outBtn {{
                background: rgba(166,227,161,0.06);
                color: {C['green']};
                border: 1px solid rgba(166,227,161,0.3);
                border-radius: 22px;
                padding: 9px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#outBtn:hover {{
                background: rgba(166,227,161,0.12);
                border-color: {C['green']};
            }}
            QPushButton#outBtn:disabled {{
                color: {C['surface2']};
                border-color: {C['surface1']};
            }}

            QLineEdit#outPath {{
                background: rgba(30,30,46,0.6);
                color: {C['text']};
                border: 1px solid {C['surface0']};
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
            }}
            QLabel#outLabel {{
                color: {C['overlay1']};
                font-size: 12px;
                font-weight: 500;
            }}

            QPushButton#convBtn {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['mauve']}, stop:1 {C['pink']});
                color: {C['base']};
                border: none;
                border-radius: 22px;
                padding: 9px 34px;
                font-weight: bold;
                font-size: 14px;
                min-width: 150px;
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
                background: rgba(243,139,168,0.15);
                color: {C['red']};
                border: 1px solid rgba(243,139,168,0.3);
                border-radius: 22px;
                padding: 9px 22px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton#cancelBtn:hover {{
                background: rgba(243,139,168,0.25);
                border-color: {C['red']};
            }}

            /* ─── Remove button ──────────────────────────────────────── */
            QPushButton#removeBtn {{
                background: transparent;
                color: {C['surface2']};
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton#removeBtn:hover {{
                background: rgba(243,139,168,0.15);
                color: {C['red']};
            }}
            QPushButton#removeBtn:disabled {{
                color: {C['surface0']};
            }}

            /* ─── Status label ───────────────────────────────────────── */
            QLabel#statusText {{
                color: {C['overlay2']};
                font-size: 12px;
                font-family: "Cascadia Code", "Consolas", monospace;
            }}
            QLabel#credit {{
                color: {C['overlay1']};
                font-size: 11px;
                font-weight: 300;
                padding-right: 4px;
            }}

            /* ─── Scroll bars ────────────────────────────────────────── */
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