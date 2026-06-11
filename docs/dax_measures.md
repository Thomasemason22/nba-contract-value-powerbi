# Suggested Power BI DAX Measures

Create these measures after importing the CSVs.

```DAX
Total Salary = SUM(Fact_Player_Value[Salary])

Salary Millions = DIVIDE([Total Salary], 1000000)

Salary Coverage % =
DIVIDE(
    CALCULATE(COUNTROWS(Fact_Player_Value), Fact_Player_Value[SalaryAvailable] = TRUE()),
    COUNTROWS(Fact_Player_Value)
)

Total Points = SUM(Fact_Player_Value[TotalPoints])

Estimated Win Shares = SUM(Fact_Player_Value[EstimatedWinShares])

Production Score = SUM(Fact_Player_Value[ProductionScore])

Value Score = DIVIDE([Production Score], [Salary Millions])

Cost Per Point = DIVIDE([Total Salary], [Total Points])

Cost Per Estimated Win Share = DIVIDE([Total Salary], [Estimated Win Shares])

Payroll Per Win = DIVIDE([Total Salary], SUM(Team_Efficiency[W]))

Player Count = DISTINCTCOUNT(Dim_Player[PlayerKey])

Player-Season Count = DISTINCTCOUNT(Fact_Player_Value[PlayerSeasonKey])

Average 3P Attempt Share = AVERAGE(Player_Shooting_Profile[FGA_3P_Frequency])

Average Free Throw Rate = AVERAGE(Player_Shooting_Profile[FreeThrowRate])

Average eFG% = AVERAGE(Player_Shooting_Profile[eFG_Pct])

Playoff Production Score = SUM(Player_Playoff_Performance[PlayoffProductionScore])

Playoff Value Score =
DIVIDE(
    [Playoff Production Score],
    DIVIDE(SUM(Player_Playoff_Performance[Salary]), 1000000)
)

Top 3 Payroll Share = AVERAGE(Team_Payroll_Allocation[Top3SalaryShare])

Predicted Next Estimated Win Shares = SUM(Player_Predictions[PredictedNextSeasonEstimatedWinShares])

Predicted Next Value Score = AVERAGE(Player_Predictions[PredictedNextSeasonValueScore])

Value Rank =
RANKX(
    ALLSELECTED(Dim_Player[PlayerName]),
    [Value Score],
    ,
    DESC
)
```
