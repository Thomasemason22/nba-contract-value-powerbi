# Report Wireframe

## Page 1: Executive Overview

- KPI cards: Total Salary, Estimated Win Shares, Value Score, Salary Coverage %
- Line chart: Value Score by season
- Scatter: Salary Millions vs Production Score
- Bar: Top teams by Value Score
- Slicers: Season, team, position group, contract tier, value tier

## Page 2: Multi-Season Value Trends

- Line chart: salary, estimated win shares, and value score by season
- Small multiples: Value Score by position group
- Matrix: season by contract tier
- Highlight: biggest season-over-season player value jumps

## Page 3: Player Value Rankings

- Table: Player, season, team, salary, estimated win shares, Production Score, Value Score, Value Tier
- Top 15 bar chart by Value Score
- Bottom 15 high-salary value risks
- Custom tooltip: salary, stats, shooting profile, contract tier

## Page 4: Contract Tiers and Payroll Strategy

- Stacked bar: payroll by contract tier
- Scatter: Top 3 Payroll Share vs Adjusted Net Rating
- Matrix: team payroll allocation by position group
- KPI: average payroll per win

## Page 5: Shot Profile and Play Style

- Scatter: 3P attempt share vs Value Score
- Bar: free throw rate leaders
- Bar: 3P attempt share leaders
- Matrix: player shot profile and value tier

## Page 6: Playoff Value

- Table: playoff production, playoff estimated win shares, Playoff Value Score
- Bar: best playoff value players by season
- Scatter: regular-season value vs playoff value
- Filter to completed playoff seasons only

## Page 7: Prediction Lab

- Table: Predicted Next Estimated Win Shares, Predicted Next Value Score, Prediction Tier
- Scatter: current Value Score vs predicted next Value Score
- Bar: projected bargain players
- Include model metric cards: RMSE, MAE, training rows

## Page 8: Methodology and Data Quality

- Source cards
- Salary coverage by season
- Missing salary table
- Contract tier definition
- Prediction caveats

## UI Upgrades

- Add a left navigation rail using buttons/bookmarks.
- Use a collapsible slicer panel or top filter strip.
- Create a dedicated player tooltip page.
- Keep every page to one main analytical question.
- Use the included dark theme and amber only for highlights/callouts.
