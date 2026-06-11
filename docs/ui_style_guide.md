# UI Style Guide

## Visual Direction

Target feel: premium sports analytics desk. Dark, sharp, and data-first, with just enough broadcast energy to feel basketball-specific.

## Theme

Import `theme/nba-contract-value-theme.json` in Power BI:

1. Open the report.
2. Go to **View > Browse for themes**.
3. Select `theme/nba-contract-value-theme.json`.

## Layout System

- Canvas: 16:9.
- Page background: `#07111F`.
- Use a 24 px outer margin and 16 px gutters.
- Header height: 64-76 px.
- KPI row height: 104-120 px.
- Use 4 KPI cards max per page.
- Put slicers in a left rail or a compact top strip, never scattered through the canvas.

## Components

- KPI cards: dark surface, large value, small uppercase label, no heavy border.
- Tables/matrices: dark header, subtle row grid, high-contrast text.
- Scatter plots: cyan points, amber highlight for selected outliers.
- Bar charts: sort descending, show data labels only when they add clarity.
- Tooltips: include salary, value score, win shares, ORtg/DRtg, and shot-profile fields.

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

## Typography

- Title: 24-30 pt, bold.
- Section headers: 13-15 pt, semibold.
- KPI values: 26-34 pt.
- Body/table text: 9-11 pt.

## Polish Checklist

- Every page has one clear analytical question.
- Every chart title explains the metric, not the chart type.
- Values are formatted: salary in `$M`, percentages as `%`, ranks as whole numbers.
- Use `QualifiedForValueRank = TRUE` on value ranking visuals.
- Avoid team-color overload. Use team filters for interaction, not page-wide color chaos.
