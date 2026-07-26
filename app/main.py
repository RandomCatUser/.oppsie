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
#  DESIGN TOKENS  (Windows 95 / 90s UI Retro Theme)
# ═══════════════════════════════════════════════════════════════════════════
C = {
    "window": "#C0C0C0",      # Classic Gray
    "dark": "#808080",        # Border Dark
    "darker": "#000000",      # Absolute Black Border
    "light": "#FFFFFF",       # Border Light
    "text": "#000000",        # Black Text
    "active_title": "#000080",# Navy Blue Title Bar
    "active_title_text": "#FFFFFF",
    "select": "#000080",      # Selection Navy
    "select_text": "#FFFFFF",
    "face": "#C0C0C0",
    "shadow": "#808080",
    "highlight": "#FFFFFF",
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


def make_thumbnail(path, size=32):
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
#  CONVERSION WORKER
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
#  90s STATUS LED
# ═══════════════════════════════════════════════════════════════════════════
class StatusLED(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._color = QtGui.QColor("#00FF00") # Classic matrix green
        self.update()

    def setColor(self, name):
        if name == "green": self._color = QtGui.QColor("#00FF00")
        elif name == "yellow": self._color = QtGui.QColor("#FFFF00")
        elif name == "red": self._color = QtGui.QColor("#FF0000")
        elif name == "peach": self._color = QtGui.QColor("#FF8000")
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        r = self.rect()
        
        p.setPen(QtGui.QPen(QtGui.QColor(C["darker"]), 1))
        p.drawRect(r.x(), r.y(), r.width()-1, r.height()-1)
        p.setPen(QtGui.QPen(QtGui.QColor(C["dark"]), 1))
        p.drawLine(r.x()+1, r.y()+1, r.right()-1, r.y()+1)
        p.drawLine(r.x()+1, r.y()+1, r.x()+1, r.bottom()-1)
        p.setPen(QtGui.QPen(QtGui.QColor(C["light"]), 1))
        p.drawLine(r.right()-1, r.y()+1, r.right()-1, r.bottom()-1)
        p.drawLine(r.x()+1, r.bottom()-1, r.right()-1, r.bottom()-1)
        
        inner = r.adjusted(3, 3, -3, -3)
        p.fillRect(inner, QtGui.QBrush(self._color))


# ═══════════════════════════════════════════════════════════════════════════
#  WINDOWS 95 PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════
class Win95ProgressBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setFixedHeight(20)

    def _get_value(self): return self._value
    def _set_value(self, v):
        self._value = max(0, min(100, v))
        self.update()

    value = QtCore.pyqtProperty(int, _get_value, _set_value)

    def animateTo(self, v):
        self._value = max(0, min(100, v))
        self.update()

    def reset(self):
        self._value = 0
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        r = self.rect()

        p.setPen(QtGui.QPen(QtGui.QColor(C["darker"]), 1))
        p.drawRect(r.x(), r.y(), r.width()-1, r.height()-1)
        p.setPen(QtGui.QPen(QtGui.QColor(C["dark"]), 1))
        p.drawLine(r.x()+1, r.y()+1, r.right()-1, r.y()+1)
        p.drawLine(r.x()+1, r.y()+1, r.x()+1, r.bottom()-1)
        p.setPen(QtGui.QPen(QtGui.QColor(C["light"]), 1))
        p.drawLine(r.right()-1, r.y()+1, r.right()-1, r.bottom()-1)
        p.drawLine(r.x()+1, r.bottom()-1, r.right()-1, r.bottom()-1)

        inner_rect = r.adjusted(3, 3, -3, -3)
        if self._value > 0:
            fill_width = int(inner_rect.width() * self._value / 100)
            block_w = 7
            x = inner_rect.x()
            p.setBrush(QtGui.QBrush(QtGui.QColor(C["active_title"])))
            p.setPen(QtCore.Qt.NoPen)
            while x < inner_rect.x() + fill_width:
                p.drawRect(x, inner_rect.y(), min(block_w, inner_rect.x() + fill_width - x), inner_rect.height())
                x += block_w + 2


# ═══════════════════════════════════════════════════════════════════════════
#  FILE ITEM
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

    def _build(self):
        self.setFixedHeight(48)
        self.setMinimumWidth(400) # Ensure items require enough width to trigger horizontal scrollbar
        self.setObjectName("fileItem")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        self._check = QtWidgets.QCheckBox()
        self._check.setChecked(True)
        self._check.setObjectName("fileCheck")
        self._check.setFixedSize(16, 16)
        lay.addWidget(self._check)

        self._thumb_label = QtWidgets.QLabel()
        self._thumb_label.setFixedSize(32, 32)
        self._thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self._thumb_label.setObjectName("thumbLabel")
        pm = make_thumbnail(self.path, 32)
        if pm:
            self._thumb_label.setPixmap(pm)
        else:
            self._thumb_label.setText("📄")
            self._thumb_label.setStyleSheet("font-size:16px;")
        lay.addWidget(self._thumb_label)

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

        arrow = QtWidgets.QLabel("->")
        arrow.setObjectName("arrow")
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        arrow.setFixedWidth(20)
        lay.addWidget(arrow)

        self._fmt = QtWidgets.QComboBox()
        self._fmt.addItems(FORMATS)
        self._fmt.setCurrentText("oppsie")
        self._fmt.setObjectName("fmtCombo")
        self._fmt.setFixedWidth(90)
        self._fmt.currentTextChanged.connect(lambda t: setattr(self, "target_fmt", t))
        lay.addWidget(self._fmt)

        self._status_label = QtWidgets.QLabel()
        self._status_label.setFixedSize(20, 20)
        self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(self._status_label)

        self._remove_btn = QtWidgets.QPushButton("X")
        self._remove_btn.setObjectName("removeBtn")
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(lambda: self.removeRequested.emit(self))
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
        if self._preview_window is not None: return
        pm = make_large_thumbnail(self.path, 200)
        if pm is None: return
        self._preview_window = QtWidgets.QFrame()
        self._preview_window.setWindowFlags(QtCore.Qt.Popup)
        self._preview_window.setObjectName("previewWindow")
        layout = QtWidgets.QVBoxLayout(self._preview_window)
        layout.setContentsMargins(2, 2, 2, 2)
        label = QtWidgets.QLabel()
        label.setPixmap(pm)
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
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
        self._status_label.setText("...")
        self._status_label.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:bold;")
        self._fmt.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._set_state("converting")

    def setDone(self):
        self._status_label.setText("OK")
        self._status_label.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:bold;")
        self._set_state("done")

    def setError(self):
        self._status_label.setText("!")
        self._status_label.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:bold;")
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
#  FILE QUEUE
# ═══════════════════════════════════════════════════════════════════════════
class FileQueue(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[FileItem] = []
        self._selected_item: Optional[FileItem] = None
        self.setAcceptDrops(True)
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setObjectName("stack")
        lay.addWidget(self._stack)

        dz = QtWidgets.QWidget()
        dz.setObjectName("dropZone")
        dl = QtWidgets.QVBoxLayout(dz)
        dl.setAlignment(QtCore.Qt.AlignCenter)
        dl.setSpacing(6)

        title = QtWidgets.QLabel("Drop files here to add")
        title.setObjectName("dzTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(title)

        sub = QtWidgets.QLabel("Supported: PNG, JPG, WEBP, BMP, OPPSIE")
        sub.setObjectName("dzSub")
        sub.setAlignment(QtCore.Qt.AlignCenter)
        dl.addWidget(sub)

        self._stack.addWidget(dz)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        # Enable both vertical and horizontal scrollbars as needed
        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setObjectName("fileScroll")
        self._scroll.viewport().setAcceptDrops(False)

        self._list_widget = QtWidgets.QWidget()
        self._list_layout = QtWidgets.QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(2, 2, 2, 2)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        self._stack.addWidget(self._scroll)

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
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_file():
                self.addFile(p)
        e.acceptProposedAction()


# ═══════════════════════════════════════════════════════════════════════════
#  CUSTOM TITLE BAR
# ═══════════════════════════════════════════════════════════════════════════
class TitleBar(QtWidgets.QWidget):
    closeClicked = QtCore.pyqtSignal()
    minimizeClicked = QtCore.pyqtSignal()
    maximizeClicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setObjectName("titleBar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(2)

        self.icon_label = QtWidgets.QLabel("ᓚ₍⑅^..^₎♡")
        self.icon_label.setObjectName("titleIcon")
        layout.addWidget(self.icon_label)

        self.title_label = QtWidgets.QLabel("Oppsie Convert")
        self.title_label.setObjectName("titleText")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.min_btn = QtWidgets.QPushButton("_")
        self.min_btn.setObjectName("titleBtn")
        self.min_btn.setFixedSize(26, 22)
        self.min_btn.clicked.connect(self.minimizeClicked)
        layout.addWidget(self.min_btn)

        self.max_btn = QtWidgets.QPushButton("□")
        self.max_btn.setObjectName("titleBtn")
        self.max_btn.setFixedSize(26, 22)
        self.max_btn.clicked.connect(self.maximizeClicked)
        layout.addWidget(self.max_btn)

        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setObjectName("titleBtn")
        self.close_btn.setFixedSize(26, 22)
        self.close_btn.clicked.connect(self.closeClicked)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.window().windowHandle():
                self.window().windowHandle().startSystemMove()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle("Oppsie Convert")
        self.resize(800, 580) # Default size
        self.setMinimumSize(640, 480) # Allows much smaller resizing

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
        main_layout.setContentsMargins(3, 3, 3, 3)
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
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # Two-panel split
        split = QtWidgets.QHBoxLayout()
        split.setSpacing(10)

        # ─── Left panel: Files ─────────────────────────────
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(5)

        files_title = QtWidgets.QLabel("Files to Convert")
        files_title.setObjectName("panelTitle")
        left_panel.addWidget(files_title)

        self._queue = FileQueue()
        left_panel.addWidget(self._queue, 1)

        file_actions = QtWidgets.QHBoxLayout()
        file_actions.setSpacing(5)
        self._add_btn = QtWidgets.QPushButton("Add Files")
        self._add_btn.setObjectName("btn")
        self._add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._browse)
        file_actions.addWidget(self._add_btn)

        self._select_all_btn = QtWidgets.QPushButton("Select All")
        self._select_all_btn.setObjectName("btn")
        self._select_all_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._select_all_btn.clicked.connect(self._select_all)
        file_actions.addWidget(self._select_all_btn)

        self._clear_btn = QtWidgets.QPushButton("Clear")
        self._clear_btn.setObjectName("btn")
        self._clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_queue)
        file_actions.addWidget(self._clear_btn)

        file_actions.addStretch()
        left_panel.addLayout(file_actions)

        left_wrap = QtWidgets.QWidget()
        left_wrap.setLayout(left_panel)
        split.addWidget(left_wrap, 3) # Left takes up 3/4 of horizontal space

        # ─── Right panel: Settings ─────────────────────────
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(10)

        archive_group = QtWidgets.QGroupBox("Archive")
        ag_layout = QtWidgets.QVBoxLayout(archive_group)
        ag_layout.setSpacing(8)
        ag_layout.setContentsMargins(8, 12, 8, 8)

        fmt_row = QtWidgets.QHBoxLayout()
        fmt_label = QtWidgets.QLabel("Output format:")
        fmt_label.setObjectName("fieldLabel")
        fmt_label.setFixedWidth(100)
        fmt_row.addWidget(fmt_label)

        self._global_fmt = QtWidgets.QComboBox()
        self._global_fmt.addItems(FORMATS)
        self._global_fmt.setCurrentText("oppsie")
        self._global_fmt.setObjectName("settingCombo")
        self._global_fmt.currentTextChanged.connect(self._apply_global_format)
        fmt_row.addWidget(self._global_fmt, 1)
        ag_layout.addLayout(fmt_row)

        out_row = QtWidgets.QHBoxLayout()
        out_label = QtWidgets.QLabel("Output folder:")
        out_label.setObjectName("fieldLabel")
        out_label.setFixedWidth(100)
        out_row.addWidget(out_label)

        self._out_path = QtWidgets.QLineEdit()
        self._out_path.setReadOnly(True)
        self._out_path.setPlaceholderText("Same as source")
        self._out_path.setObjectName("outPath")
        out_row.addWidget(self._out_path, 1)

        self._out_btn = QtWidgets.QPushButton("...")
        self._out_btn.setObjectName("btn")
        self._out_btn.setFixedSize(30, 22)
        self._out_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._out_btn.clicked.connect(self._choose_output_folder)
        out_row.addWidget(self._out_btn)
        ag_layout.addLayout(out_row)

        suf_row = QtWidgets.QHBoxLayout()
        suf_label = QtWidgets.QLabel("Filename suffix:")
        suf_label.setObjectName("fieldLabel")
        suf_label.setFixedWidth(100)
        suf_row.addWidget(suf_label)

        self._suffix_edit = QtWidgets.QLineEdit("_converted")
        self._suffix_edit.setObjectName("outPath")
        suf_row.addWidget(self._suffix_edit, 1)
        ag_layout.addLayout(suf_row)

        right_panel.addWidget(archive_group)

        comp_group = QtWidgets.QGroupBox("Compression")
        cg_layout = QtWidgets.QVBoxLayout(comp_group)
        cg_layout.setSpacing(8)
        cg_layout.setContentsMargins(8, 12, 8, 8)

        q_row = QtWidgets.QHBoxLayout()
        q_label = QtWidgets.QLabel("Compression level:")
        q_label.setObjectName("fieldLabel")
        q_label.setFixedWidth(100)
        q_row.addWidget(q_label)

        self._quality = QtWidgets.QComboBox()
        self._quality.addItems([
            "Lossless", "1 - Light", "2", "3 - Medium",
            "4", "5", "6", "7 - Max"
        ])
        self._quality.setObjectName("settingCombo")
        q_row.addWidget(self._quality, 1)
        cg_layout.addLayout(q_row)

        ow_row = QtWidgets.QHBoxLayout()
        ow_label = QtWidgets.QLabel("Overwrite mode:")
        ow_label.setObjectName("fieldLabel")
        ow_label.setFixedWidth(100)
        ow_row.addWidget(ow_label)

        self._overwrite = QtWidgets.QComboBox()
        self._overwrite.addItems(["Ask before overwrite", "Always overwrite", "Skip existing"])
        self._overwrite.setObjectName("settingCombo")
        ow_row.addWidget(self._overwrite, 1)
        cg_layout.addLayout(ow_row)

        right_panel.addWidget(comp_group)

        opt_group = QtWidgets.QGroupBox("Options")
        og_layout = QtWidgets.QVBoxLayout(opt_group)
        og_layout.setSpacing(4)
        og_layout.setContentsMargins(8, 12, 8, 8)

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
        right_wrap.setMinimumWidth(300)
        right_wrap.setMaximumWidth(380)
        split.addWidget(right_wrap, 1) # Right takes up 1/4 of horizontal space

        content_layout.addLayout(split, 1)

        self._bar = Win95ProgressBar()
        self._bar.hide()
        content_layout.addWidget(self._bar)

        action_bar = QtWidgets.QHBoxLayout()
        action_bar.setSpacing(10)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(8)
        self._dot = StatusLED()
        status_row.addWidget(self._dot)
        self._status_label = QtWidgets.QLabel("Ready - add files to begin")
        self._status_label.setObjectName("statusText")
        status_row.addWidget(self._status_label, 1)
        action_bar.addLayout(status_row, 1)

        self._help_btn = QtWidgets.QPushButton("Help")
        self._help_btn.setObjectName("btn")
        self._help_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._help_btn.clicked.connect(self._show_help)
        action_bar.addWidget(self._help_btn)

        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._cancel_btn.setObjectName("btn")
        self._cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        action_bar.addWidget(self._cancel_btn)

        self._convert_btn = QtWidgets.QPushButton("OK - Convert")
        self._convert_btn.setObjectName("primaryBtn")
        self._convert_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._convert)
        action_bar.addWidget(self._convert_btn)

        self._size_grip = QtWidgets.QSizeGrip(self)
        action_bar.addWidget(self._size_grip)

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
        if not items: return
        all_checked = all(it.isChecked() for it in items)
        for it in items:
            it.setChecked(not all_checked)

    def _apply_global_format(self, fmt):
        for it in self._queue.items():
            it._fmt.setCurrentText(fmt)

    def _show_help(self):
        QtWidgets.QMessageBox.information(
            self, "Help - Oppsie Convert",
            "Shortcuts:\n"
            "  Ctrl+O      - Add files\n"
            "  Ctrl+Enter  - Start conversion\n"
            "  Delete      - Remove selected file\n"
            "  Esc         - Cancel conversion\n"
            "  F1          - This help\n\n"
            "Tips:\n"
            "  - Hover a thumbnail to preview.\n"
            "  - Click a row to select it.\n"
            "  - Uncheck the box on the left to skip a file.\n"
            "  - Drag the bottom right corner to resize the window."
        )

    def _delete_selected(self):
        if self._converting: return
        item = self._queue.selectedItem()
        if item: self._queue.removeFile(item)

    def _toggle_maximize(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def _choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", str(Path.home()))
        if folder:
            self._output_folder = Path(folder)
            self._out_path.setText(str(self._output_folder))
        else:
            self._output_folder = None
            self._out_path.clear()

    def _on_queue_changed(self):
        count = len(self._queue.items())
        checked = len(self._queue.checkedItems())
        self._convert_btn.setEnabled(checked > 0 and not self._converting)
        if count == 0:
            self._status_label.setText("Ready - add files to begin")
            self._dot.setColor("green")
        else:
            self._status_label.setText(f"{count} file(s) in queue - {checked} selected")
            self._dot.setColor("green")

    def _clear_queue(self):
        if self._converting: return
        reply = QtWidgets.QMessageBox.question(self, "Clear Queue", "Remove all files from the queue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self._queue.clear()

    def _browse(self):
        if self._converting: return
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Add Files", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.oppsie);;All files (*)")
        for p in paths:
            self._queue.addFile(Path(p))

    def _convert(self):
        items = self._queue.checkedItems()
        if not items or self._converting: return

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
        for item in items: item.reset()
        self._convert_next(items, 0, lossy)

    def _convert_next(self, items, idx, lossy):
        while idx < len(items) and items[idx]._status_label.text() in ("OK", "!", "OS"):
            idx += 1
        if idx >= len(items):
            self._on_all_done(items)
            return

        item = items[idx]
        item.setConverting()
        self._status_label.setText(f"Converting {item.path.name}  ({idx + 1}/{len(items)})...")
        self._dot.setColor("yellow")
        self._bar.show()
        self._bar.reset()
        self._bar.animateTo(5)

        if self._output_folder: dst_dir = self._output_folder
        else: dst_dir = item.path.parent
        ext = ".oppsie" if item.target_fmt == "oppsie" else f".{item.target_fmt}"
        suffix = self._suffix_edit.text().strip() or ""
        dst = dst_dir / (item.path.stem + suffix + ext)

        if dst.exists():
            mode = self._overwrite.currentIndex()
            if mode == 2:
                item._status_label.setText("OS")
                self._convert_next(items, idx + 1, lossy)
                return
            elif mode == 0:
                reply = QtWidgets.QMessageBox.question(self, "File Exists", f"{dst.name} already exists. Overwrite?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply != QtWidgets.QMessageBox.Yes:
                    self._convert_next(items, idx + 1, lossy)
                    return

        dst.parent.mkdir(parents=True, exist_ok=True)
        self._worker = ConversionWorker(str(item.path), str(dst), item.target_fmt, lossy)
        self._worker.progress.connect(self._bar.animateTo)
        self._worker.status.connect(self._status_label.setText)
        self._worker.done.connect(lambda r, i=item, ii=idx, itms=items, l=lossy: self._on_file_done(r, i, ii, itms, l))
        self._worker.start()

    def _on_file_done(self, result, item, idx, items, lossy):
        if result.get("ok"):
            item.setDone()
            src, dst, ms = result["src"], result["dst"], result["ms"]
            try:
                src_size = src.stat().st_size
                dst_size = dst.stat().st_size
                ratio = dst_size / src_size * 100 if src_size else 0
                self._status_label.setText(f"{src.name} -> {dst.name} | {human_size(src_size)} -> {human_size(dst_size)} | {ratio:.1f}% | {ms:.1f} ms")
                if self._delete_orig.isChecked():
                    try: src.unlink()
                    except OSError: pass
            except OSError:
                self._status_label.setText(f"{src.name} -> {dst.name} | {ms:.1f} ms")
        else:
            item.setError()
            err = result.get("error", "Unknown error")
            self._status_label.setText(f"Failed: {err}")
            self._dot.setColor("red")

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

        done = sum(1 for i in items if i._status_label.text() == "OK")
        failed = sum(1 for i in items if i._status_label.text() == "!")

        if failed == 0:
            msg = f"All {done} file(s) converted successfully"
            self._status_label.setText(msg)
            self._dot.setColor("green")
            if self._open_after.isChecked() and self._output_folder:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._output_folder)))
            QtWidgets.QMessageBox.information(self, "Conversion Complete", msg)
        else:
            msg = f"{done} succeeded, {failed} failed"
            self._status_label.setText(msg)
            self._dot.setColor("peach")
            QtWidgets.QMessageBox.warning(self, "Conversion Complete", msg)

    def _cancel_conversion(self):
        if not self._converting: return
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

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.terminate()
            self._worker.wait(2000)
        event.accept()

    def _style(self):
        self.setStyleSheet(f"""
            /* Root Window */
            QWidget#centralWidget {{
                background: {C['window']};
                border: 1px solid {C['darker']};
                border-top: 1px solid {C['light']};
                border-left: 1px solid {C['light']};
                border-right: 1px solid {C['darker']};
                border-bottom: 1px solid {C['darker']};
            }}

            /* Title Bar */
            QWidget#titleBar {{
                background: {C['active_title']};
                border-bottom: 1px solid {C['darker']};
            }}
            QLabel#titleIcon {{
                color: {C['active_title_text']};
                font-size: 14px;
                padding-left: 4px;
            }}
            QLabel#titleText {{
                color: {C['active_title_text']};
                font-size: 12px;
                font-weight: bold;
                padding-left: 4px;
            }}
            QPushButton#titleBtn {{
                background: {C['window']};
                color: {C['text']};
                border-top: 1px solid {C['light']};
                border-left: 1px solid {C['light']};
                border-right: 1px solid {C['darker']};
                border-bottom: 1px solid {C['darker']};
                font-weight: bold;
                font-size: 12px;
                padding: 0px;
                margin: 2px;
            }}
            QPushButton#titleBtn:pressed {{
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}

            QWidget#content {{ background: {C['window']}; }}
            QLabel#panelTitle {{ color: {C['text']}; font-size: 12px; font-weight: bold; }}
            QLabel#countLabel {{ color: {C['text']}; font-size: 11px; }}

            /* Group Box */
            QGroupBox {{
                background: {C['window']};
                border: 1px solid {C['dark']};
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
                border-radius: 0px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: bold;
                color: {C['text']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
                background: {C['window']};
            }}

            QLabel#fieldLabel {{ color: {C['text']}; font-size: 12px; }}

            QWidget#dropZone {{ background: {C['window']}; border: none; }}
            QLabel#dzTitle {{ color: {C['text']}; font-size: 12px; font-weight: bold; }}
            QLabel#dzSub {{ color: {C['text']}; font-size: 11px; }}

            /* File List Sunken Box */
            QScrollArea#fileScroll {{
                background: {C['window']};
                border: 1px solid {C['darker']};
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}

            /* File Items */
            QFrame#fileItem {{
                background: {C['window']};
                border: none;
                border-bottom: 1px dotted {C['dark']};
            }}
            QFrame#fileItem[selected="true"] {{
                background: {C['select']};
            }}
            QFrame#fileItem[selected="true"] QLabel#fileName,
            QFrame#fileItem[selected="true"] QLabel#fileSize,
            QFrame#fileItem[selected="true"] QLabel#arrow {{
                color: {C['select_text']};
            }}
            QFrame#fileItem[state="converting"] {{
                background: #FFFFCC; 
                border: 1px solid {C['darker']};
            }}
            QFrame#fileItem[state="done"] {{
                background: #CCFFCC; 
            }}
            QFrame#fileItem[state="error"] {{
                background: #FFCCCC; 
            }}

            /* Checkboxes */
            QCheckBox#fileCheck, QCheckBox#optCheck {{
                spacing: 6px;
                color: {C['text']};
                font-size: 12px;
            }}
            QCheckBox#fileCheck::indicator, QCheckBox#optCheck::indicator {{
                width: 13px; height: 13px;
                background: {C['window']};
                border: 1px solid {C['darker']};
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}

            QLabel#thumbLabel {{
                background: {C['window']};
                border: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}
            QLabel#fileName {{ color: {C['text']}; font-size: 12px; }}
            QLabel#fileSize {{ color: {C['text']}; font-size: 11px; }}
            QLabel#arrow {{ color: {C['text']}; font-size: 12px; }}

            /* Combo Boxes */
            QComboBox#fmtCombo, QComboBox#settingCombo {{
                background: {C['window']};
                color: {C['text']};
                border: 1px solid {C['darker']};
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
                padding: 1px 4px;
                font-size: 12px;
                min-height: 18px;
            }}
            QComboBox#fmtCombo::drop-down, QComboBox#settingCombo::drop-down {{
                width: 16px;
                border: none;
                background: {C['window']};
                border-left: 1px solid {C['darker']};
            }}
            QComboBox#fmtCombo::down-arrow, QComboBox#settingCombo::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {C['text']};
                margin-right: 4px;
            }}
            QComboBox#fmtCombo QAbstractItemView, QComboBox#settingCombo QAbstractItemView {{
                background: {C['window']};
                color: {C['text']};
                border: 1px solid {C['darker']};
                selection-background-color: {C['select']};
                selection-color: {C['select_text']};
                outline: none;
                padding: 1px;
            }}

            /* Line Edits */
            QLineEdit#outPath {{
                background: #FFFFFF;
                color: {C['text']};
                border: 1px solid {C['darker']};
                border-top: 1px solid {C['darker']};
                border-left: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
                padding: 1px 4px;
                font-size: 12px;
            }}

            /* Standard 3D Buttons */
            QPushButton#btn, QPushButton#removeBtn {{
                background: {C['window']};
                color: {C['text']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                padding: 4px 12px;
                font-size: 12px;
                min-width: 50px;
                border-radius: 0px;
            }}
            QPushButton#btn:pressed, QPushButton#removeBtn:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
                padding: 5px 11px 3px 13px;
            }}
            QPushButton#btn:disabled, QPushButton#removeBtn:disabled {{
                color: {C['dark']};
                border-top: 2px solid {C['window']};
                border-left: 2px solid {C['window']};
                border-right: 2px solid {C['dark']};
                border-bottom: 2px solid {C['dark']};
            }}

            /* Primary Convert Button */
            QPushButton#primaryBtn {{
                background: {C['window']};
                color: {C['text']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                padding: 4px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 0px;
            }}
            QPushButton#primaryBtn:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
                padding: 5px 15px 3px 17px;
            }}
            QPushButton#primaryBtn:disabled {{
                color: {C['dark']};
            }}

            QLabel#statusText {{ color: {C['text']}; font-size: 12px; }}

            /* Chunky 3D Scrollbars - Vertical */
            QScrollBar:vertical {{
                background: {C['window']};
                width: 16px;
                border: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}
            QScrollBar::handle:vertical {{
                background: {C['window']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: {C['window']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                height: 16px;
                subcontrol-origin: margin;
            }}
            QScrollBar::add-line:vertical:pressed, QScrollBar::sub-line:vertical:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: {C['window']};
            }}

            /* Chunky 3D Scrollbars - Horizontal */
            QScrollBar:horizontal {{
                background: {C['window']};
                height: 16px;
                border: 1px solid {C['darker']};
                border-right: 1px solid {C['light']};
                border-bottom: 1px solid {C['light']};
            }}
            QScrollBar::handle:horizontal {{
                background: {C['window']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                background: {C['window']};
                border-top: 2px solid {C['light']};
                border-left: 2px solid {C['light']};
                border-right: 2px solid {C['darker']};
                border-bottom: 2px solid {C['darker']};
                width: 16px;
                subcontrol-origin: margin;
            }}
            QScrollBar::add-line:horizontal:pressed, QScrollBar::sub-line:horizontal:pressed {{
                border-top: 2px solid {C['darker']};
                border-left: 2px solid {C['darker']};
                border-right: 2px solid {C['light']};
                border-bottom: 2px solid {C['light']};
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: {C['window']};
            }}
        """)


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Windows") 

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(C["window"]))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(C["text"]))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(C["window"]))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(C["window"]))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(C["text"]))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(C["window"]))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(C["text"]))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(C["select"]))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(C["select_text"]))
    app.setPalette(palette)

    font = QtGui.QFont("Tahoma", 8)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()