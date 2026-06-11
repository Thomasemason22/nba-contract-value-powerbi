# NBA Contract Value Analysis

## Project Question

Which NBA players and teams delivered the most on-court production for the money during the **2025-26** season?

This starter project is built for Power BI. It includes cleaned CSV tables, an Excel workbook version of the same model, DAX measures, and a page-by-page report plan.

## Data Sources

- Player totals: https://www.basketball-reference.com/leagues/NBA_2026_totals.html
- Player per-game stats: https://www.basketball-reference.com/leagues/NBA_2026_per_game.html
- Player advanced stats: https://www.basketball-reference.com/leagues/NBA_2026_advanced.html
- Player per-100-possession stats: https://www.basketball-reference.com/leagues/NBA_2026_per_poss.html
- Player shooting profile: https://www.basketball-reference.com/leagues/NBA_2026_shooting.html
- Team summary and four factors: https://www.basketball-reference.com/leagues/NBA_2026.html
- Team adjusted ratings: https://www.basketball-reference.com/leagues/NBA_2026_ratings.html
- Player salaries/contracts: https://www.basketball-reference.com/contracts/players.html

Data was pulled locally on **2026-06-11 14:20:20**. Basketball Reference tables can update, so refresh the generated CSVs before submitting a final project if current numbers matter.

## Files

- `data/fact_player_value.csv`: primary fact table for player salary and performance.
- `data/player_pace_adjusted.csv`: per-100-possession player stats and player offensive/defensive rating.
- `data/player_shooting_profile.csv`: shot-distance, shot-location mix, assisted-shot, dunk, and corner-three metrics.
- `data/team_efficiency.csv`: team-level payroll efficiency summary.
- `data/team_context.csv`: team wins, ratings, pace, four factors, attendance, and shot-profile context.
- `data/dim_player.csv`: player attributes.
- `data/dim_team.csv`: NBA team lookup table.
- `data/dim_position.csv`: position lookup table.
- `data/data_dictionary.csv`: column definitions.
- `data/measure_catalog.csv`: suggested Power BI measures.
- `theme/nba-contract-value-theme.json`: importable Power BI theme.
- `assets/report_layout_mockup.svg`: visual reference for the report layout.
- `NBA_Contract_Value_Analysis.xlsx`: Excel workbook containing the same project tables.
- `docs/dax_measures.md`: DAX formulas to paste into Power BI.
- `docs/powerbi_build_guide.md`: step-by-step build instructions.
- `docs/report_wireframe.md`: suggested report pages and visuals.
- `docs/ui_style_guide.md`: visual design system, layout rhythm, and styling notes.
- `scripts/build_nba_powerbi_project.py`: rebuilds CSVs, docs, theme, and summary metadata.
- `scripts/build_workbook.mjs`: rebuilds the Excel workbook from the generated CSVs.

## Current Dataset Snapshot

- Salary rows: **529**
- Matched salary + stat rows: **510**
- Qualified value-rank players: **370**
- Pace-adjusted player rows: **510**
- Player shooting-profile rows: **510**
- Team context rows: **30**
- Top team by team value score: **Dallas Mavericks**

## Early Insight Starters

Top qualified players by value score in the current extract:

| PlayerName              | SalaryTeam | SalaryMillions | TotalPoints | WS   | ValueScore | ValueGap |
| ----------------------- | ---------- | -------------- | ----------- | ---- | ---------- | -------- |
| Kobe Sanders            | LAC        | 0.48           | 495.00      | 1.40 | 1972.88    | 9.00     |
| Jordan Miller           | LAC        | 0.71           | 598.00      | 3.50 | 1579.21    | 48.00    |
| Maxime Raynaud          | SAC        | 1.27           | 922.00      | 3.60 | 1473.99    | 175.00   |
| Spencer Jones           | DEN        | 0.62           | 352.00      | 2.60 | 1428.44    | -2.00    |
| Sidy Cissoko            | POR        | 0.69           | 383.00      | 1.30 | 1323.44    | 3.00     |
| Pat Spencer             | GSW        | 0.86           | 476.00      | 1.40 | 1267.89    | 34.00    |
| Nae'Qwan Tomlin         | CLE        | 0.72           | 374.00      | 2.20 | 1215.21    | -8.00    |
| Toumani Camara          | POR        | 2.22           | 1100.00     | 4.80 | 967.60     | 190.00   |
| Collin Gillespie        | PHO        | 2.30           | 1012.00     | 6.20 | 949.76     | 192.00   |
| Olivier-Maxence Prosper | DAL        | 1.00           | 530.00      | 2.40 | 940.68     | 3.00     |

Use these as starting points, not final conclusions. In the report, add slicers for conference, team, position, and qualified-player status so the audience can test the story.
