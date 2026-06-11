# Power BI Build Guide

## 1. Import Data

Use **Get Data > Text/CSV** and import these files from the `data` folder:

- `fact_player_value.csv`
- `team_efficiency.csv`
- `dim_player.csv`
- `dim_team.csv`
- `dim_position.csv`

You can also import `NBA_Contract_Value_Analysis.xlsx` if you prefer a single workbook source.

## 2. Set Data Types

In Power Query:

- Set `Salary`, `GuaranteedSalary`, `CostPerPoint`, and `CostPerWinShare` to decimal number or currency.
- Set `QualifiedForValueRank` and `IsMatchedToStats` to true/false.
- Set rank columns to whole number.
- Keep `PlayerKey`, `TeamKey`, `SalaryTeam`, `StatsTeam`, and `Position` as text.

## 3. Create Relationships

Recommended model:

- `Dim_Player[PlayerKey]` one-to-many to `Fact_Player_Value[PlayerKey]`
- `Dim_Team[TeamKey]` one-to-many to `Fact_Player_Value[SalaryTeam]`
- `Dim_Team[TeamKey]` one-to-many to `Team_Efficiency[TeamKey]`
- `Dim_Position[Position]` one-to-many to `Fact_Player_Value[Position]`

Set relationship direction to single direction from dimension to fact.

## 4. Add Measures

Paste the measures from `docs/dax_measures.md`.

## 5. Build Report Pages

Use `docs/report_wireframe.md` for a clean 4-page report:

1. League Overview
2. Player Value Rankings
3. Team Payroll Efficiency
4. Position and Contract Outliers

## 6. Suggested Filters

Add slicers for:

- Team
- Conference
- Position group
- Qualified for value rank
- All-Star flag

For the cleanest analysis, set `QualifiedForValueRank = TRUE` on player ranking visuals.
