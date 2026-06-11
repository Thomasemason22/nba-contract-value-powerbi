# Power BI Build Guide

## 1. Import Data

Import all CSVs from the `data` folder. The key tables are:

- `fact_player_value.csv`
- `player_pace_adjusted.csv`
- `player_shooting_profile.csv`
- `player_playoff_performance.csv`
- `player_predictions.csv`
- `prediction_backtest.csv`
- `team_efficiency.csv`
- `team_context.csv`
- `team_payroll_allocation.csv`
- `dim_player.csv`
- `dim_team.csv`
- `dim_position.csv`
- `dim_season.csv`

Import `theme/nba-contract-value-theme.json` from **View > Browse for themes** before building visuals.

## 2. Relationships

Recommended model:

- `Dim_Player[PlayerKey]` to `Fact_Player_Value[PlayerKey]`
- `Dim_Player[PlayerKey]` to `Player_Predictions[PlayerKey]`
- `Dim_Player[PlayerKey]` to `Prediction_Backtest[PlayerKey]`
- `Dim_Season[Season]` to every fact table containing `Season`
- `Dim_Team[TeamKey]` to `Fact_Player_Value[StatsTeam]`
- `Dim_Team[TeamKey]` to `Team_Efficiency[TeamKey]`
- `Dim_Team[TeamKey]` to `Team_Context[TeamKey]`
- `Dim_Team[TeamKey]` to `Team_Payroll_Allocation[TeamKey]`
- `Dim_Position[Position]` to `Fact_Player_Value[Position]`
- `Fact_Player_Value[PlayerSeasonKey]` to `Player_Shooting_Profile[PlayerSeasonKey]`
- `Fact_Player_Value[PlayerSeasonKey]` to `Player_Pace_Adjusted[PlayerSeasonKey]`
- `Fact_Player_Value[PlayerSeasonKey]` to `Player_Playoff_Performance[PlayerSeasonKey]`

Use single-direction filtering from dimensions to facts. For player-season detail tables, one-to-one relationships are acceptable if Power BI detects unique keys.

## 3. Data Types

- Currency: salary, payroll, cost, salary cap fields.
- Decimal: percentages, ranks, ratings, value scores, prediction outputs.
- Whole number: games, points, rebounds, assists, season end year.
- Boolean: `SalaryAvailable`, `QualifiedForValueRank`, `PlayoffsAvailable`.

## 4. Report Pages

Use `docs/report_wireframe.md` for an 8-page report:

1. Executive Overview
2. Multi-Season Value Trends
3. Player Value Rankings
4. Contract Tiers and Payroll Strategy
5. Shot Profile and Play Style
6. Playoff Value
7. Prediction Lab
8. Methodology and Data Quality
