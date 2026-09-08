---
name: llm-connections
description: Connections board benchmark — puzzle tiles, category colors, date-first browsing
colors:
  ground: "#efefe6"
  ground-deep: "#e2e2d8"
  ink: "#1a1a1a"
  ink-muted: "#4a4a44"
  ink-soft: "#6b6b63"
  tile-bg: "#ffffff"
  tile-border: "#d3d3c8"
  tile-solved: "#c8dfc8"
  category-yellow: "#f8df00"
  category-green: "#6aaa64"
  category-blue: "#4a90d9"
  category-purple: "#bc9fdd"
  accent-link: "#4a90d9"
  outcome-solved: "#3d7a3d"
  outcome-lost: "#a33333"
typography:
  display:
    fontFamily: '"Caprasimo", Georgia, serif'
    fontWeight: 400
  body:
    fontFamily: '"Libre Franklin", system-ui, sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '"Libre Franklin", system-ui, sans-serif'
    fontSize: "0.75rem"
    fontWeight: 700
    letterSpacing: "0.05em"
  mono:
    fontFamily: 'ui-monospace, "SF Mono", monospace'
    fontSize: "0.8rem"
rounded:
  tile: "0.45rem"
  card: "0.75rem"
spacing:
  page: "1.5rem"
  section: "2.5rem"
  tile-gap: "0.35rem"
components:
  tile:
    backgroundColor: "{colors.tile-bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tile}"
    padding: "0.5rem"
  date-card:
    backgroundColor: "{colors.tile-bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "1rem"
  answer-band:
    rounded: "{rounded.tile}"
    padding: "0.65rem 0.85rem"
---

## Overview

The visual world is the Connections game board itself: off-white ground, bold uppercase word tiles in a 4×4 grid, and the four category reveal colors (yellow, green, blue, purple). The site reads as a puzzle archive, not an ML dashboard — dates are the hero, models are players whose outcomes sit beside the board.

## Colors

- **Ground** (`ground`, `ground-deep`): warm off-white page background and section dividers.
- **Ink** (`ink`, `ink-muted`, `ink-soft`): body text hierarchy; never raw gray unrelated to the ground hue.
- **Tiles** (`tile-bg`, `tile-border`, `tile-solved`): white tiles with neutral borders; solved words tint green.
- **Categories** (`category-yellow` through `category-purple`): Connections difficulty colors for answer bands and correct-guess accents only.
- **Outcomes** (`outcome-solved`, `outcome-lost`): text colors for result badges, paired with labels (never color-only).

## Typography

- **Display:** Caprasimo for wordmark and logo mark — playful, puzzle-adjacent.
- **Body:** Libre Franklin for all UI copy, tables, and reasoning text.
- **Tiles:** Bold uppercase, tight line-height, `clamp()` sizing on full boards.
- **Data:** Tabular nums on standings table.

## Layout

- Single column, max-width 52rem, centered.
- Home: vertical date card stack (newest first), standings below a heavy section break.
- Date detail: model sections separated by ground-deep rules; board above guess history.
- 4×4 grid never reflows — scales down on mobile, stays four columns.

## Elevation & Depth

- Date cards: 2px ink border + soft offset shadow (`0 2px 8px rgb(26 26 26 / 0.08)`).
- No glass, no gradient text, no hard offset block shadows.
- Hover: 2px translateY on date cards only.

## Shapes

- Rounded tiles (`0.45rem`) and cards (`0.75rem`).
- Outcome chips: pill (`border-radius: 999px`).
- Logo mark: yellow square with ink border, matching tile language.

## Components

- **TileGrid:** 4×4 grid, mini and full sizes; solved state tints tile background.
- **DateCard:** Entire card is a link; mini grid + outcome chips per model.
- **StandingsTable:** Bordered table, uppercase column headers on ground row.
- **GuessAccordion:** Native `<details>`; summary shows guess words; body uses category accent gradient on correct guesses.
- **AnswerBand:** Full-width category bar with group name + members (solved games only).

## Do's and Don'ts

**Do:** Use category colors on answer bands and correct-guess accents. Keep words uppercase on tiles. Show all models present in data.

**Don't:** Use generic dashboard cards, bar-chart heroes, or Inter/system-default UI. Don't imply NYT affiliation. Don't use kickers above headings.
