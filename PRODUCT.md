# Product

<!-- impeccable:product-schema 1 -->

## Platform

macos

## Stack

delegated: Python with PySide6 for a cross-platform desktop UI, yt-dlp Python API for downloads, and PyInstaller for packaging. Chosen from the recommendation after the user asked to proceed.

## Users

Inferred from the request: a person on macOS who wants to download media from URLs with yt-dlp without composing command-line options.

## Product Purpose

Inferred from the request: provide a desktop interface for yt-dlp that makes URL entry, format choice, destination selection, queued downloads, progress, and cancellation accessible in one place.

## Positioning

Open decision: no differentiating product position has been specified beyond offering a GUI for yt-dlp.

## Operating Context

Confirmed: macOS desktop. The user selected a core downloader MVP with URL, format list, destination, queue, progress, and cancellation.

## Capabilities and Constraints

The first version should use yt-dlp's Python API and keep work off the UI thread. FFmpeg may be detected on the system for stream merging; audio extraction, subtitles, playlists, and cookies are outside the selected first-version scope.

## Evidence on Hand

No existing application, brand assets, or product evidence was present in the workspace when work began.

## Product Principles

- Make the download workflow legible without exposing a wall of CLI switches.
- Show format, destination, progress, and errors clearly.
- Keep the interface responsive while downloads run.
- Keep options explicit and avoid opaque shell command construction.
