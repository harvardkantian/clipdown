# Clipdown

Clipdown is a macOS desktop interface for yt-dlp. It is being built as a focused first version: inspect one URL, compare available formats, choose a destination, queue downloads, watch progress, and cancel an active item.

## Requirements

- macOS 14.4 or newer (the packaged build targets Apple silicon)
- Python 3.11 or newer to run from source or rebuild the app
- FFmpeg available on `PATH` for merging separate video and audio streams
- Deno available on `PATH` for the strongest YouTube extraction support

## Run from source

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/clipdown
```

## Package a macOS app

```bash
.venv/bin/python -m pip install -e '.[build]'
.venv/bin/pyinstaller --windowed --name Clipdown --osx-bundle-identifier com.kodatools.clipdown --collect-all yt_dlp --collect-all yt_dlp_ejs run_clipdown.py
```

FFmpeg and Deno are not bundled. Clipdown detects both on `PATH` and shows their status. Install FFmpeg if the chosen format requires stream merging, and Deno for the strongest YouTube extraction support.

Only download media that you have the right and permission to save.
