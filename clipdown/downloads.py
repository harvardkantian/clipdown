"""yt-dlp integration and background workers."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


@dataclass(frozen=True)
class FormatChoice:
    selector: str
    label: str
    extension: str
    resolution: str
    approximate_size: int | None


def inspect_url(url: str) -> tuple[dict[str, Any], list[FormatChoice]]:
    """Extract one video's metadata and a deduplicated list of playable choices."""
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise DownloadError("yt-dlp did not return video information")

    formats = info.get("formats") or []
    audio_exists = any(item.get("acodec") not in (None, "none") for item in formats)
    separate_audio = [
        item
        for item in formats
        if item.get("acodec") not in (None, "none") and item.get("vcodec") in (None, "none")
    ]
    best_audio = max(
        separate_audio,
        key=lambda item: (item.get("tbr") or 0, item.get("filesize") or item.get("filesize_approx") or 0),
        default=None,
    )
    best_audio_size = (
        (best_audio.get("filesize") or best_audio.get("filesize_approx"))
        if best_audio
        else None
    )
    # Prefer one good candidate per resolution. A video-only stream is paired with
    # the best available audio; yt-dlp/FFmpeg handles the merge.
    best_by_height: dict[int, tuple[dict[str, Any], str]] = {}
    for item in formats:
        if item.get("vcodec") in (None, "none"):
            continue
        height = item.get("height")
        if not isinstance(height, int):
            continue
        has_audio = item.get("acodec") not in (None, "none")
        if not has_audio and not audio_exists:
            continue
        current = best_by_height.get(height)
        score = (
            int(has_audio),
            int(item.get("ext") == "mp4"),
            item.get("tbr") or 0,
            item.get("filesize") or item.get("filesize_approx") or 0,
        )
        if current is None or score > current[0].get("_clipdown_score", ()):
            item = dict(item)
            item["_clipdown_score"] = score
            selector = str(item["format_id"]) if has_audio else f'{item["format_id"]}+bestaudio/best'
            best_by_height[height] = (item, selector)

    choices: list[FormatChoice] = []
    for height, (item, selector) in sorted(best_by_height.items(), reverse=True):
        ext = str(item.get("ext") or "media")
        size = item.get("filesize") or item.get("filesize_approx")
        if item.get("acodec") in (None, "none") and isinstance(size, int) and isinstance(best_audio_size, int):
            size += best_audio_size
        audio_label = "video + audio" if item.get("acodec") not in (None, "none") else "video + best audio"
        choices.append(
            FormatChoice(
                selector=selector,
                label=f"{ext.upper()} · {audio_label}",
                extension=ext,
                resolution=f"{height}p",
                approximate_size=size if isinstance(size, int) else None,
            )
        )

    if audio_exists:
        audio_format = best_audio
        if audio_format:
            ext = str(audio_format.get("ext") or "audio")
            size = audio_format.get("filesize") or audio_format.get("filesize_approx")
            choices.append(
                FormatChoice(
                    selector=str(audio_format["format_id"]),
                    label=f"Audio only · {ext.upper()}",
                    extension=ext,
                    resolution="—",
                    approximate_size=size if isinstance(size, int) else None,
                )
            )

    if not choices:
        choices.append(FormatChoice("bv*+ba/b", "Best available · video + audio", "media", "Best", None))
    return info, choices


class InspectWorker(QThread):
    succeeded = Signal(dict, list)
    failed = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            info, choices = inspect_url(self.url)
            self.succeeded.emit(info, choices)
        except Exception as error:  # Surface extractor/network errors to the UI.
            self.failed.emit(str(error))


class DownloadWorker(QThread):
    progress = Signal(dict)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, choice: FormatChoice, destination: Path) -> None:
        super().__init__()
        self.url = url
        self.choice = choice
        self.destination = destination
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            self.destination.mkdir(parents=True, exist_ok=True)
            template = str(self.destination / "%(title).200B [%(id)s].%(ext)s")

            def report(status: dict[str, Any]) -> None:
                if self._cancel_event.is_set():
                    raise DownloadError("Download cancelled")
                self.progress.emit(dict(status))

            options = {
                "format": self.choice.selector,
                "outtmpl": template,
                "progress_hooks": [report],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            with YoutubeDL(options) as ydl:
                ydl.download([self.url])
            if self._cancel_event.is_set():
                self.failed.emit("Download cancelled")
            else:
                self.succeeded.emit(template)
        except Exception as error:
            if self._cancel_event.is_set():
                self.failed.emit("Download cancelled")
            else:
                self.failed.emit(str(error))
