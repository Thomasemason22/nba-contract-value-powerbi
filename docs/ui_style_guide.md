# UI Style Guide

## Visual Direction

Premium sports analytics desk: dark, sharp, calm, and data-first.

## Theme

Import `theme/nba-contract-value-theme.json` in Power BI.

## Layout

- Canvas: 16:9.
- Background: `#07111F`.
- Outer margin: 24 px.
- Gutter: 16 px.
- Header: 64-76 px.
- Left navigation rail: 72-96 px if using icons/buttons.
- KPI cards: 4 max per page.

## Navigation

- Use page navigation buttons for Overview, Trends, Players, Contracts, Shot Profile, Playoffs, Prediction, Methodology.
- Use a consistent active-page accent in cyan.
- Keep slicers in one location across pages.

## Tooltip Page

Create a tooltip page named `Player Tooltip` with:

- Player name, season, team
- Salary and contract tier
- PPG/RPG/APG
- Estimated Win Shares, Production Score, eFG%, TS%, 3P attempt share
- Value Score and Value Tier
- Free throw rate, 3P attempt share, double-doubles/triple-doubles
- Prediction tier when available

## Color Tokens

- Background: `#07111F`
- Surface: `#102033`
- Elevated surface: `#172A42`
- Primary text: `#F8FAFC`
- Muted text: `#A8B3C5`
- Primary accent: `#38BDF8`
- Secondary accent: `#FBBF24`
- Positive: `#22C55E`
- Negative: `#F43F5E`

## Formatting Rules

- Salary: `$0.0M`
- Percentages: `0.0%`
- Value scores: one decimal
- Ranks: whole numbers
- Sort ranking visuals descending by value score unless intentionally showing risks
