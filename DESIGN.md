---
name: Clipdown
description: A clear macOS utility for inspecting and managing yt-dlp downloads.
colors:
  primary: "AccentColor"
  primary-on: "HighlightText"
  window: "Canvas"
  text: "CanvasText"
  border: "ButtonBorder"
typography:
  body:
    fontFamily: "system-ui"
    fontSize: "13px"
    fontWeight: 400
  page-title:
    fontFamily: "system-ui"
    fontSize: "23px"
    fontWeight: 650
  section-title:
    fontFamily: "system-ui"
    fontSize: "15px"
    fontWeight: 600
  action:
    fontFamily: "system-ui"
    fontSize: "13px"
    fontWeight: 600
rounded:
  control: "6px"
spacing:
  micro: "2px"
  input-inset: "9px"
  control-inset: "12px"
  content-gap: "12px"
  sidebar-width: "184px"
  content-horizontal: "30px"
  content-top: "28px"
  content-bottom: "22px"
components:
  primary-action:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-on}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "30px"
  url-field:
    backgroundColor: "{colors.window}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "0 9px"
    height: "30px"
---

## Overview

**Creative North Star: The Clear Mac Utility.** Clipdown should feel like a focused macOS tool: familiar controls, system appearance, and a plain path from URL to saved media. Use the platform's typography and palette so the interface belongs beside Finder and other desktop utilities.

Keep the window calm and task-led. The URL and its available formats lead; destination and queue status stay close to the next action. **The Real State Rule.** Titles, formats, progress, and errors come from yt-dlp and the active job. Never fill empty screens with invented media data.

## Colors

Use Qt's system palette roles for window, text, borders, selection, and button colors. This follows the user's light or dark appearance and accent choice. Keep primary actions on the platform highlight color, with the matching highlighted text color. **The System Palette Rule.** Do not replace appearance-aware palette roles with fixed light-theme colors.

## Typography

Inherit the macOS system sans-serif face. Body text is 13px; page titles are 23px at weight 650; section headings are 15px at weight 600. Table headings and primary actions use the body size with a stronger weight. Avoid decorative display type and technical-looking monospace outside measurements.

## Layout

Use a compact 184px navigation sidebar and one resizable work area. Main pages use 30px horizontal insets, 28px above, 22px below, and 12px between related groups. Keep the URL check, format list, destination, and queue action in that order. The queue keeps title, chosen format, progress, state, and action in a single table row.

## Elevation & Depth

The interface is flat. Let macOS provide the window's native shadow; do not add card shadows or decorative depth. Separate areas through spacing, system surfaces, and restrained borders.

## Shapes

Controls use gently rounded corners (6px). Inputs and secondary buttons use a thin system border; selected navigation and primary actions use the system accent. Keep tables square-edged and visually quiet.

## Components

### Primary action

Use the system accent fill and highlighted text for the next meaningful action. Keep disabled actions visibly disabled and avoid competing custom colors.

### URL field

Use a 30px minimum height, 9px horizontal inset, system field surface, and a thin system border. Preserve the clear affordance and URL-shaped placeholder.

### Navigation

Use a text-only sidebar with 12px horizontal and 9px vertical item padding. The active destination gets the system highlight fill; inactive destinations remain quiet and readable.

### Format table

Use compact column headings and a readable row selection. Show format, resolution, and approximate size without fabricating unknown values.

### Queue row

Keep the selected format, progress bar, status, and Cancel or Remove action together. Progress describes the running item; completed, failed, and cancelled rows remain understandable until removed.

## Do's and Don'ts

### Do:

- **Do** use the current system palette so selection and text adapt to light and dark appearance.
- **Do** keep empty, checking, complete, cancelled, and failed states explicit.
- **Do** show the selected format and destination for each queued item.

### Don't:

- **Don't** invent media titles, sizes, or progress to decorate an empty state.
- **Don't** hide the selected format or download state behind a separate detail screen.
- **Don't** add decorative shadows, accent stripes, emoji, or fixed-theme colors.
