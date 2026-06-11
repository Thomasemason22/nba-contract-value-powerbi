# Suggested Power BI DAX Measures

Create these measures on the `Fact_Player_Value` table after importing the CSVs or workbook.

```DAX
Total Salary = SUM(Fact_Player_Value[Salary])

Salary Millions = DIVIDE([Total Salary], 1000000)

Total Points = SUM(Fact_Player_Value[TotalPoints])

Total Rebounds = SUM(Fact_Player_Value[TotalRebounds])

Total Assists = SUM(Fact_Player_Value[TotalAssists])

Total Win Shares = SUM(Fact_Player_Value[WS])

Total VORP = SUM(Fact_Player_Value[VORP])

Production Score = SUM(Fact_Player_Value[ProductionScore])

Cost Per Point = DIVIDE([Total Salary], [Total Points])

Cost Per Win Share = DIVIDE([Total Salary], [Total Win Shares])

Points Per $1M = DIVIDE([Total Points], [Salary Millions])

Win Shares Per $1M = DIVIDE([Total Win Shares], [Salary Millions])

Value Score = DIVIDE([Production Score], [Salary Millions])

Player Count = DISTINCTCOUNT(Fact_Player_Value[PlayerKey])

Average Player ORtg = AVERAGE(Player_Pace_Adjusted[PlayerORtg])

Average Player DRtg = AVERAGE(Player_Pace_Adjusted[PlayerDRtg])

Average Shot Distance = AVERAGE(Player_Shooting_Profile[AvgShotDistance])

Average 3P Attempt Share = AVERAGE(Player_Shooting_Profile[FGA_3P_Frequency])

Average Rim Attempt Share = AVERAGE(Player_Shooting_Profile[FGA_0_3_Frequency])

Team Adjusted Net Rating = AVERAGE(Team_Context[AdjustedNetRtg])

Payroll Per Win = DIVIDE([Total Salary], SUM(Team_Efficiency[W]))

Qualified Player Count =
CALCULATE(
    [Player Count],
    Fact_Player_Value[QualifiedForValueRank] = TRUE()
)

Value Rank =
RANKX(
    ALLSELECTED(Dim_Player[PlayerName]),
    [Value Score],
    ,
    DESC
)

Salary Rank =
RANKX(
    ALLSELECTED(Dim_Player[PlayerName]),
    [Total Salary],
    ,
    DESC
)

Value Gap = [Salary Rank] - [Value Rank]
```

Suggested formatting:

- Salary measures: Currency, whole dollars or one decimal in millions.
- Ratio measures: Currency for cost metrics; decimal for value metrics.
- Rank measures: Whole number.
