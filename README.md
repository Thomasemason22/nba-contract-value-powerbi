# NBA Contract Value Analysis

## Project Question

Which NBA players, teams, and contract types generated the most value across the **2021-22 through 2025-26** seasons, and which players look like future value opportunities?

This Power BI portfolio project now includes all ESPN regular-season player-seasons over the selected seasons, historical ESPN salary rows when matched, ESPN playoff performance, team-building payroll allocation, contract/value tiers, and baseline prediction outputs.

## Data Sources

- ESPN NBA player stats: regular season and playoffs, paginated by season.
- ESPN NBA salary pages: paginated historical salary tables by season.
- ESPN NBA standings: wins, losses, points per game, opponent points per game, and point differential.
- Basketball Reference current contracts: attempted as a next-season salary baseline where reachable.

Data was pulled locally on **2026-06-11 15:04:51**. Public pages can update or throttle automated reads, so refresh before submitting final work if current numbers matter.

## Files

- `data/fact_player_value.csv`: all regular-season player-seasons with salary/value metrics.
- `data/player_pace_adjusted.csv`: per-36 player rate stats.
- `data/player_shooting_profile.csv`: shooting efficiency and 3P/FT attempt profile.
- `data/player_playoff_performance.csv`: postseason production and salary-adjusted playoff value.
- `data/player_predictions.csv`: latest-season baseline next-season forecasts.
- `data/prediction_backtest.csv`: model backtest rows with actual next-season outcomes.
- `data/team_efficiency.csv`: team payroll efficiency by season.
- `data/team_context.csv`: standings, scoring, opponent scoring, and point differential by team-season.
- `data/team_payroll_allocation.csv`: top-heavy payroll and position allocation analysis.
- `data/dim_player.csv`, `data/dim_team.csv`, `data/dim_position.csv`, `data/dim_season.csv`: lookup tables.
- `theme/nba-contract-value-theme.json`: importable Power BI theme.
- `assets/report_layout_mockup.svg`: visual layout reference.
- `docs/`: build guide, DAX, report wireframe, and UI style guide.
- `scripts/`: reproducible data and workbook builders.

## Refreshing the Data

Install Python dependencies, then run the generator from the repo root:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build_nba_powerbi_project.py
```

The CSVs can be imported directly into Power BI. `scripts/build_workbook.mjs` rebuilds the optional Excel companion workbook in the Codex spreadsheet runtime.

## Dataset Snapshot

- Regular-season player rows: **2,815**
- Unique players: **998**
- Salary-covered rows: **2,312**
- Playoff rows: **1,097**
- Team context rows: **150**
- Prediction rows: **578**

## Latest-Season Value Starters

| PlayerName              | StatsTeam | SalaryMillions | EstimatedWinShares | ValueScore | PlayerValueTier       |
| ----------------------- | --------- | -------------- | ------------------ | ---------- | --------------------- |
| Ryan Nembhard           | DAL       | 0.32           | 3.40               | 3167.07    | Efficient Role Player |
| Olivier-Maxence Prosper | MEM       | 0.53           | 3.14               | 1787.15    | Efficient Role Player |
| Jordan Miller           | LAC       | 0.71           | 3.79               | 1595.48    | Efficient Role Player |
| Maxime Raynaud          | SAC       | 1.27           | 6.24               | 1470.85    | Efficient Role Player |
| Spencer Jones           | DEN       | 0.62           | 3.00               | 1442.13    | Efficient Role Player |
| Kyle Anderson           | MEM       | 0.57           | 2.67               | 1413.20    | Efficient Role Player |
| Quenton Jackson         | IND       | 0.60           | 2.78               | 1385.56    | Efficient Role Player |
| Sidy Cissoko            | POR       | 0.69           | 3.02               | 1317.49    | Efficient Role Player |
| Pat Spencer             | GSW       | 0.86           | 3.61               | 1264.13    | Efficient Role Player |
| Tyus Jones              | ORL       | 0.51           | 2.08               | 1213.25    | Efficient Role Player |

Use these as analytical starting points. The report should let the viewer switch between raw value rankings, contract tiers, playoff value, team payroll strategy, and predicted future value.
