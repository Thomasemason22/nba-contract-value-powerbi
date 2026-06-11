# Report Wireframe

## Page 1: League Overview

Purpose: Give the audience the headline story quickly.

Recommended visuals:

- Header strip with title, season, and data refresh date
- KPI cards: Total Salary, Total Win Shares, Value Score, Payroll Per Win
- Scatter plot: Salary Millions vs Production Score by player, colored by position group
- Bar chart: Top 10 teams by Value Score
- Slicers: Conference, Team, Position Group, QualifiedForValueRank

## Page 2: Player Value Rankings

Purpose: Show who produced the most relative to salary.

Recommended visuals:

- Table: Player, Team, Position, Salary Millions, PPG, WS, Player ORtg, Value Score, Value Gap
- Bar chart: Top 15 players by Value Score
- Bar chart: Bottom 15 qualified players by Cost Per Win Share
- Tooltip fields: PER, TS%, USG%, VORP, PTSPer100, PlayerORtg

## Page 3: Shot Profile and Play Style

Purpose: Connect player value to how players score.

Recommended visuals:

- Scatter plot: Avg Shot Distance vs Value Score, sized by Total Points
- Bar chart: Top players by rim attempt share
- Bar chart: Top players by three-point attempt share
- Matrix: Player, Team, Position, AvgShotDistance, FGA_0_3_Frequency, FGA_3P_Frequency, Corner3Pct
- Tooltip fields: Assisted2P_Pct, Assisted3P_Pct, DunksMade

## Page 4: Team Payroll Efficiency

Purpose: Compare team spending efficiency.

Recommended visuals:

- Matrix: Team, Payroll, Wins, Adjusted Net Rating, Total Win Shares, Cost Per Win Share, Value Score
- Bar chart: Teams by Value Score
- Scatter plot: Payroll Millions vs Adjusted Net Rating
- Bar chart: Team 3P Frequency by team
- Filled map is optional, but a conference/division slicer is usually cleaner.

## Page 5: Contract Outliers

Purpose: Tell the “who is underpaid or overpaid?” story.

Recommended visuals:

- Bar chart: Average salary by position group
- Bar chart: Average value score by position group
- Table: Biggest positive Value Gap
- Table: Biggest negative Value Gap
- Slicer: All-Star flag

## Design Notes

Use the included Power BI theme and keep the report calm, high-contrast, and portfolio-ready:

- Background: near-black navy
- Surface cards: deep blue-gray
- Primary accent: electric cyan
- Secondary accent: amber
- Positive highlight: green
- Negative highlight: red
- Use amber only for callouts, not every chart
- Keep the player ranking table as the main analytical object
