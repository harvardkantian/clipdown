"""Clipdown's macOS-first desktop interface."""

from __future__ import annotations

import sys
import uuid
import shutil
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .downloads import DownloadWorker, FormatChoice, InspectWorker


@dataclass
class QueueEntry:
    id: str
    url: str
    title: str
    choice: FormatChoice
    destination: Path
    status: str = "Queued"
    progress: int = 0
    detail: str = "Waiting"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("KodaTools", "Clipdown")
        self.destination = Path(
            self.settings.value("destination", str(Path.home() / "Downloads"))
        ).expanduser()
        self.info: dict = {}
        self.choices: list[FormatChoice] = []
        self.inspected_url: str | None = None
        self._pending_url: str | None = None
        self.entries: list[QueueEntry] = []
        self.inspect_worker: InspectWorker | None = None
        self.download_worker: DownloadWorker | None = None
        self.active_entry_id: str | None = None
        self._quit_after_cancel = False

        self.setWindowTitle("Clipdown")
        self.setMinimumSize(860, 640)
        self.resize(1060, 760)
        self._build_menu()
        self._build_shell()
        self._set_dependency_status()
        self._refresh_queue()

    def _set_dependency_status(self) -> None:
        available = []
        missing = []
        for name, label in (("ffmpeg", "FFmpeg"), ("deno", "Deno")):
            (available if shutil.which(name) else missing).append(label)
        if not missing:
            message = f"{' · '.join(available)} ready for merging and YouTube support."
            self.inline_status.setText(message)
            self.inline_status.setStyleSheet("")
            return
        ready = f"{' · '.join(available)} ready. " if available else ""
        message = ready + f"Install {' and '.join(missing)} for full format support."
        self.inline_status.setText(message)
        self.inline_status.setStyleSheet("")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        add_action = QAction("New Download", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(lambda: self._show_page(0))
        file_menu.addAction(add_action)
        open_folder = QAction("Open Downloads Folder", self)
        open_folder.triggered.connect(self._open_destination)
        file_menu.addAction(open_folder)
        file_menu.addSeparator()
        quit_action = QAction("Quit Clipdown", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("View")
        for title, index, shortcut in (
            ("Downloads", 0, "Ctrl+1"),
            ("Queue", 1, "Ctrl+2"),
        ):
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, i=index: self._show_page(i))
            view_menu.addAction(action)

    def _build_shell(self) -> None:
        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(184)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        for label in ("Downloads", "Queue"):
            self.sidebar.addItem(QListWidgetItem(label))
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._show_page)
        shell.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.add_page = self._make_add_page()
        self.queue_page = self._make_queue_page()
        self.pages.addWidget(self.add_page)
        self.pages.addWidget(self.queue_page)
        shell.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        self.setStyleSheet(
            """
            QWidget { font-size: 13px; }
            QListWidget#sidebar { background: palette(alternate-base); padding: 12px 8px; }
            QListWidget#sidebar::item { padding: 9px 12px; border-radius: 6px; margin: 2px 0; }
            QListWidget#sidebar::item:selected { background: palette(highlight); color: palette(highlighted-text); }
            QLabel#pageTitle { font-size: 23px; font-weight: 650; }
            QLabel#sectionTitle { font-size: 15px; font-weight: 600; }
            QLabel#muted { color: palette(window-text); }
            QLineEdit { min-height: 30px; padding: 0 9px; border: 1px solid palette(midlight); border-radius: 6px; background: palette(base); color: palette(text); }
            QPushButton { min-height: 30px; padding: 0 12px; border: 1px solid palette(midlight); border-radius: 6px; background: palette(button); color: palette(button-text); }
            QPushButton#primary { font-weight: 600; border-color: palette(highlight); background: palette(highlight); color: palette(highlighted-text); }
            QPushButton#primary:disabled { border-color: palette(midlight); background: palette(midlight); color: palette(mid); }
            QTableWidget { gridline-color: palette(midlight); border: 1px solid palette(midlight); background: palette(base); color: palette(text); }
            QHeaderView::section { padding: 7px 8px; font-weight: 600; }
            """
        )

    def _make_add_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 22)
        layout.setSpacing(12)

        title = QLabel("New Download")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel("Paste a media URL to inspect its available formats.")
        intro.setObjectName("muted")
        layout.addWidget(intro)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://…")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._inspect_url)
        self.url_input.textChanged.connect(self._invalidate_inspection)
        self.check_button = QPushButton("Check URL")
        self.check_button.setObjectName("primary")
        self.check_button.clicked.connect(self._inspect_url)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.check_button)
        layout.addLayout(url_row)

        self.info_label = QLabel("No URL checked yet")
        self.info_label.setObjectName("muted")
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumHeight(42)
        layout.addWidget(self.info_label)

        format_title = QLabel("Available formats")
        format_title.setObjectName("sectionTitle")
        layout.addWidget(format_title)
        self.formats_table = QTableWidget(0, 3)
        self.formats_table.setHorizontalHeaderLabels(["Format", "Resolution", "Approx. size"])
        self.formats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.formats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.formats_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.formats_table.verticalHeader().setVisible(False)
        self.formats_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.formats_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.formats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.formats_table.itemSelectionChanged.connect(self._sync_add_enabled)
        self.formats_stack = QStackedWidget()
        self.formats_empty = QLabel("Paste a URL to see available formats.")
        self.formats_empty.setObjectName("muted")
        self.formats_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formats_stack.addWidget(self.formats_empty)
        self.formats_stack.addWidget(self.formats_table)
        layout.addWidget(self.formats_stack, 1)

        destination_row = QHBoxLayout()
        destination_caption = QLabel("Save to")
        destination_caption.setObjectName("muted")
        self.destination_label = QLabel(str(self.destination))
        self.destination_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.destination_label.setToolTip(str(self.destination))
        self.destination_label.setMinimumWidth(120)
        self.destination_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.destination_label.setWordWrap(False)
        self.destination_label.setObjectName("destinationPath")
        self.choose_destination_button = QPushButton("Choose…")
        self.choose_destination_button.clicked.connect(self._choose_destination)
        self.open_destination_button = QPushButton("Show in Finder")
        self.open_destination_button.clicked.connect(self._open_destination)
        destination_row.addWidget(destination_caption)
        destination_row.addWidget(self.destination_label, 1)
        destination_row.addWidget(self.open_destination_button)
        destination_row.addWidget(self.choose_destination_button)
        layout.addLayout(destination_row)

        footer = QHBoxLayout()
        self.inline_status = QLabel("FFmpeg improves support for combining separate streams.")
        self.inline_status.setObjectName("muted")
        self.add_button = QPushButton("Add to Queue")
        self.add_button.setObjectName("primary")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._add_to_queue)
        footer.addWidget(self.inline_status, 1)
        footer.addWidget(self.add_button)
        layout.addLayout(footer)
        return page

    def _make_queue_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 22)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Queue")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.open_queue_folder_button = QPushButton("Show in Finder")
        self.open_queue_folder_button.clicked.connect(self._open_destination)
        header.addWidget(self.open_queue_folder_button)
        layout.addLayout(header)

        self.queue_summary = QLabel("Downloads you add will appear here.")
        self.queue_summary.setObjectName("muted")
        layout.addWidget(self.queue_summary)
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(["Media", "Format", "Progress", "Status", "Action"])
        header_view = self.queue_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(2, 168)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setWordWrap(False)
        layout.addWidget(self.queue_table, 1)

        bottom = QHBoxLayout()
        self.queue_empty_hint = QLabel("Add a URL from Downloads to get started.")
        self.queue_empty_hint.setObjectName("muted")
        bottom.addWidget(self.queue_empty_hint, 1)
        self.new_download_button = QPushButton("New Download")
        self.new_download_button.clicked.connect(lambda: self._show_page(0))
        bottom.addWidget(self.new_download_button)
        layout.addLayout(bottom)
        return page

    def _show_page(self, index: int) -> None:
        index = max(0, min(index, self.pages.count() - 1))
        self.pages.setCurrentIndex(index)
        if self.sidebar.currentRow() != index:
            self.sidebar.setCurrentRow(index)

    def _inspect_url(self) -> None:
        url = self.url_input.text().strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            self.inline_status.setText("Enter a full http or https media URL.")
            self.inline_status.setStyleSheet("color: palette(bright-text)")
            return
        if self.inspect_worker and self.inspect_worker.isRunning():
            return
        self.choices = []
        self.inspected_url = None
        self._pending_url = url
        self.formats_table.setRowCount(0)
        self.formats_empty.setText("Checking available formats…")
        self.formats_stack.setCurrentWidget(self.formats_empty)
        self.info_label.setText("Checking URL…")
        self.inline_status.setText("Fetching media details and formats.")
        self.inline_status.setStyleSheet("")
        self.check_button.setEnabled(False)
        self.url_input.setEnabled(False)
        worker = InspectWorker(url)
        self.inspect_worker = worker
        worker.succeeded.connect(self._inspection_succeeded)
        worker.failed.connect(self._inspection_failed)
        worker.finished.connect(lambda: self.check_button.setEnabled(True))
        worker.finished.connect(lambda: self.url_input.setEnabled(True))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _inspection_succeeded(self, info: dict, choices: list) -> None:
        self.info = info
        self.choices = choices
        self.inspected_url = self._pending_url
        title = str(info.get("title") or "Untitled media")
        duration = info.get("duration")
        duration_text = self._duration_text(duration)
        self.info_label.setText(f"{title}  ·  {duration_text}" if duration_text else title)
        self.formats_table.setRowCount(len(choices))
        for row, choice in enumerate(choices):
            label_item = QTableWidgetItem(choice.label)
            label_item.setData(Qt.ItemDataRole.UserRole, choice)
            self.formats_table.setItem(row, 0, label_item)
            self.formats_table.setItem(row, 1, QTableWidgetItem(choice.resolution))
            size_text = self._format_size(choice.approximate_size)
            self.formats_table.setItem(row, 2, QTableWidgetItem(size_text))
        if choices:
            self.formats_stack.setCurrentWidget(self.formats_table)
            self.formats_table.selectRow(0)
            self.inline_status.setText(f"{len(choices)} format choices found. Select one and add it to the queue.")
            self.inline_status.setStyleSheet("")
        self._sync_add_enabled()

    def _inspection_failed(self, message: str) -> None:
        self.inspected_url = None
        self.info_label.setText("Could not inspect this URL")
        self.formats_empty.setText("No format choices to show.")
        self.formats_stack.setCurrentWidget(self.formats_empty)
        self.inline_status.setText(self._friendly_error(message))
        self.inline_status.setStyleSheet("color: palette(bright-text)")
        self.add_button.setEnabled(False)

    @staticmethod
    def _duration_text(seconds: object) -> str:
        if not isinstance(seconds, (int, float)):
            return ""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

    @staticmethod
    def _format_size(size: object) -> str:
        if not isinstance(size, int) or size <= 0:
            return "Unknown"
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return "Unknown"

    @staticmethod
    def _friendly_error(message: str) -> str:
        clean = " ".join(message.split())
        if not clean:
            return "yt-dlp returned no details. Check the URL and try again."
        lower = clean.lower()
        if "ffmpeg" in lower:
            return "FFmpeg is needed to merge these streams. Install FFmpeg, then retry."
        if "javascript runtime" in lower or "deno" in lower:
            return "YouTube extraction needs a supported JavaScript runtime. Install Deno, then retry."
        return clean[:420]

    def _sync_add_enabled(self) -> None:
        self.add_button.setEnabled(
            bool(
                self.choices
                and self.inspected_url == self.url_input.text().strip()
                and self.formats_table.currentRow() >= 0
            )
        )

    def _invalidate_inspection(self) -> None:
        if self.inspected_url is None or self.url_input.text().strip() == self.inspected_url:
            return
        self.inspected_url = None
        self.choices = []
        self.formats_table.setRowCount(0)
        self.formats_empty.setText("Check the changed URL to refresh formats.")
        self.formats_stack.setCurrentWidget(self.formats_empty)
        self.info_label.setText("URL changed — check it again")
        self.inline_status.setText("Check the URL again to load its current formats.")
        self.inline_status.setStyleSheet("")
        self._sync_add_enabled()

    def _choose_destination(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Download Folder",
            str(self.destination),
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.destination = Path(selected)
            self.destination_label.setText(str(self.destination))
            self.destination_label.setToolTip(str(self.destination))
            self.settings.setValue("destination", str(self.destination))

    def _open_destination(self) -> None:
        self.destination.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.destination)))

    def _add_to_queue(self) -> None:
        row = self.formats_table.currentRow()
        if row < 0 or row >= len(self.choices):
            return
        choice = self.choices[row]
        entry = QueueEntry(
            id=uuid.uuid4().hex,
            url=self.inspected_url or "",
            title=str(self.info.get("title") or "Untitled media"),
            choice=choice,
            destination=self.destination,
        )
        self.entries.append(entry)
        self._refresh_queue()
        self._show_page(1)
        self._start_next_download()

    def _refresh_queue(self) -> None:
        self.queue_table.setRowCount(len(self.entries))
        active_count = sum(entry.status == "Downloading" for entry in self.entries)
        queued_count = sum(entry.status == "Queued" for entry in self.entries)
        if not self.entries:
            self.queue_summary.setText("Downloads you add will appear here.")
            self.queue_empty_hint.setText("Add a URL from Downloads to get started.")
        else:
            parts = []
            if active_count:
                parts.append(f"{active_count} active")
            if queued_count:
                parts.append(f"{queued_count} waiting")
            parts.append(f"{len(self.entries)} total")
            self.queue_summary.setText("  ·  ".join(parts))
            self.queue_empty_hint.setText("Each download is saved to its selected destination.")

        for row, entry in enumerate(self.entries):
            title_item = QTableWidgetItem(entry.title)
            title_item.setToolTip(str(entry.destination))
            self.queue_table.setItem(row, 0, title_item)
            format_text = f"{entry.choice.resolution} · {entry.choice.extension.upper()}"
            self.queue_table.setItem(row, 1, QTableWidgetItem(format_text))

            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(entry.progress)
            progress.setTextVisible(entry.status == "Downloading")
            if entry.status == "Downloading" and entry.progress == 0:
                progress.setRange(0, 0)
            self.queue_table.setCellWidget(row, 2, progress)
            status_item = QTableWidgetItem(entry.detail)
            status_item.setToolTip(entry.detail)
            if len(entry.detail) > 36:
                status_item.setText(entry.detail[:33] + "…")
            self.queue_table.setItem(row, 3, status_item)

            action = QPushButton("Cancel" if entry.status == "Downloading" else "Remove")
            action.setEnabled(entry.detail != "Cancelling…")
            action.clicked.connect(lambda checked=False, item_id=entry.id: self._cancel_or_remove(item_id))
            self.queue_table.setCellWidget(row, 4, action)

    def _start_next_download(self) -> None:
        if self.download_worker and self.download_worker.isRunning():
            return
        entry = next((item for item in self.entries if item.status == "Queued"), None)
        if entry is None:
            self.active_entry_id = None
            self._refresh_queue()
            return
        self.active_entry_id = entry.id
        entry.status = "Downloading"
        entry.detail = "Starting…"
        self._refresh_queue()

        worker = DownloadWorker(entry.url, entry.choice, entry.destination)
        self.download_worker = worker
        worker.progress.connect(lambda status, item_id=entry.id: self._download_progress(item_id, status))
        worker.succeeded.connect(lambda path, item_id=entry.id: self._download_succeeded(item_id, path))
        worker.failed.connect(lambda message, item_id=entry.id: self._download_failed(item_id, message))
        worker.finished.connect(self._download_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _download_progress(self, entry_id: str, status: dict) -> None:
        entry = self._find_entry(entry_id)
        if entry is None:
            return
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = status.get("downloaded_bytes") or 0
            if total:
                entry.progress = max(0, min(100, int(downloaded * 100 / total)))
            speed = status.get("speed")
            if speed:
                entry.detail = f"{entry.progress}% · {self._format_speed(speed)}"
            elif total:
                entry.detail = f"{entry.progress}%"
            else:
                entry.detail = "Downloading…"
        elif status.get("status") == "finished":
            entry.progress = 100
            entry.detail = "Finalizing…"
        self._refresh_queue()

    @staticmethod
    def _format_speed(bytes_per_second: float) -> str:
        value = float(bytes_per_second)
        for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
            if value < 1024 or unit == "GB/s":
                return f"{value:.1f} {unit}"
            value /= 1024
        return ""

    def _download_succeeded(self, entry_id: str, destination: str) -> None:
        entry = self._find_entry(entry_id)
        if entry:
            entry.status = "Complete"
            entry.progress = 100
            folder = Path(destination).parent.name
            entry.detail = f"Saved to {folder}" if folder else "Saved"
        self._refresh_queue()

    def _download_failed(self, entry_id: str, message: str) -> None:
        entry = self._find_entry(entry_id)
        if entry:
            if "cancel" in message.lower():
                entry.status = "Cancelled"
                entry.detail = "Cancelled"
            else:
                entry.status = "Failed"
                entry.detail = self._friendly_error(message)
        self._refresh_queue()

    def _download_worker_finished(self) -> None:
        self.download_worker = None
        self.active_entry_id = None
        if self._quit_after_cancel:
            self._quit_after_cancel = False
            self.close()
            return
        self._start_next_download()

    def _cancel_or_remove(self, entry_id: str) -> None:
        entry = self._find_entry(entry_id)
        if entry is None:
            return
        if entry.status == "Downloading" and self.download_worker:
            entry.detail = "Cancelling…"
            self.download_worker.cancel()
        else:
            self.entries.remove(entry)
            self._start_next_download()
        self._refresh_queue()

    def _find_entry(self, entry_id: str) -> QueueEntry | None:
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt event API name
        if self.download_worker and self.download_worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Download in progress",
                "A download is running. Cancel it and quit?",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
            self._quit_after_cancel = True
            self.download_worker.cancel()
            event.ignore()
            return
        event.accept()


def main() -> int:
    bundled_tools = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys([*bundled_tools, *path_parts]))
    app = QApplication(sys.argv)
    app.setApplicationName("Clipdown")
    app.setOrganizationName("KodaTools")
    app.setStyle("macOS")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
