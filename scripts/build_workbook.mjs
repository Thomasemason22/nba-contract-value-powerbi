import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outputDir = root;
const dataDir = path.join(outputDir, "data");
const previewDir = path.join(root, "workbook_previews");

const tableFiles = [
  ["Fact_Player_Value", "fact_player_value.csv"],
  ["Player_Pace_Adjusted", "player_pace_adjusted.csv"],
  ["Player_Shooting_Profile", "player_shooting_profile.csv"],
  ["Player_Playoff_Performance", "player_playoff_performance.csv"],
  ["Player_Predictions", "player_predictions.csv"],
  ["Prediction_Backtest", "prediction_backtest.csv"],
  ["Prediction_Model_Metrics", "prediction_model_metrics.csv"],
  ["Team_Efficiency", "team_efficiency.csv"],
  ["Team_Context", "team_context.csv"],
  ["Team_Payroll_Allocation", "team_payroll_allocation.csv"],
  ["Dim_Player", "dim_player.csv"],
  ["Dim_Team", "dim_team.csv"],
  ["Dim_Position", "dim_position.csv"],
  ["Dim_Season", "dim_season.csv"],
  ["Measure_Catalog", "measure_catalog.csv"],
  ["Data_Dictionary", "data_dictionary.csv"],
  ["Source_Notes", "source_notes.csv"],
  ["Salary_Unmatched", "salary_unmatched.csv"],
];

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (char === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        cell += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (char !== "\r") {
      cell += char;
    }
  }

  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }

  return rows.filter((r) => r.some((v) => v !== ""));
}

function coerce(value) {
  if (value === "") return null;
  if (value === "True") return true;
  if (value === "False") return false;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function excelColumn(index) {
  let n = index + 1;
  let result = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result;
}

function rangeAddress(rowCount, colCount) {
  return `A1:${excelColumn(colCount - 1)}${rowCount}`;
}

function estimateWidth(values, colIndex) {
  const sample = values.slice(0, 120).map((row) => row[colIndex]);
  const maxLen = Math.max(
    ...sample.map((value) => (value === null || value === undefined ? 0 : String(value).length)),
    8
  );
  return Math.min(Math.max(maxLen + 2, 10), 34);
}

function cleanTableName(sheetName) {
  return `${sheetName.replace(/[^A-Za-z0-9_]/g, "_")}Table`.slice(0, 240);
}

function applyNumberFormats(sheet, headers, rowCount) {
  const currencyColumns = new Set([
    "Salary",
    "GuaranteedSalary",
    "Payroll",
    "CostPerPoint",
    "CostPerWinShare",
    "CostPerEstimatedWinShare",
    "CostPerPlayoffPoint",
    "CostPerPlayoffEstimatedWinShare",
    "PayrollPerWin",
  ]);
  const millionColumns = new Set(["SalaryMillions", "GuaranteedMillions", "PayrollMillions"]);
  const decimalColumns = new Set([
    "MPG",
    "PPG",
    "RPG",
    "APG",
    "SPG",
    "BPG",
    "TPG",
    "PER",
    "TS_Pct",
    "USG_Pct",
    "WS",
    "EstimatedWinShares",
    "TotalEstimatedWinShares",
    "WS/48",
    "BPM",
    "VORP",
    "ProductionScore",
    "PointsPerMillion",
    "WinSharesPerMillion",
    "EstimatedWinSharesPerMillion",
    "ValueScore",
    "ValueGap",
    "PTSPer36",
    "TRBPer36",
    "ASTPer36",
    "STLPer36",
    "BLKPer36",
    "TOVPer36",
    "BoxScoreRateScorePer36",
    "PTSPer100",
    "TRBPer100",
    "ASTPer100",
    "STLPer100",
    "BLKPer100",
    "TOVPer100",
    "PlayerORtg",
    "PlayerDRtg",
    "AvgShotDistance",
    "FGA_2P_Frequency",
    "FGA_0_3_Frequency",
    "FGA_3_10_Frequency",
    "FGA_10_16_Frequency",
    "FGA_16_3P_Frequency",
    "FGA_3P_Frequency",
    "FG_2P_Pct",
    "FG_0_3_Pct",
    "FG_3_10_Pct",
    "FG_10_16_Pct",
    "FG_16_3P_Pct",
    "FG_3P_Pct",
    "Assisted2P_Pct",
    "Assisted3P_Pct",
    "Dunk_FGA_Pct",
    "Corner3_Frequency",
    "Corner3Pct",
    "FreeThrowRate",
    "FG_Pct",
    "FT_Pct",
    "eFG_Pct",
    "PlayoffTS_Pct",
    "PlayoffProductionScore",
    "PlayoffEstimatedWinShares",
    "PlayoffValueScore",
    "PredictedNextSeasonWS",
    "PredictedNextSeasonEstimatedWinShares",
    "PredictedNextSeasonProductionScore",
    "PredictedNextSeasonValueScore",
    "NextSeasonWSError",
    "NextSeasonEstimatedWinShareError",
    "NextSeasonProductionError",
    "ActualNextSeasonEstimatedWinShares",
    "Top1SalaryShare",
    "Top3SalaryShare",
    "Top5SalaryShare",
    "GuardSalaryShare",
    "WingSalaryShare",
    "ForwardSalaryShare",
    "CenterSalaryShare",
    "SalaryCoveragePct",
    "PointsPerGame",
    "OpponentPointsPerGame",
    "NetPointDiff",
    "WinPct",
    "Pace",
    "AdjustedORtg",
    "AdjustedDRtg",
    "AdjustedNetRtg",
    "Team3P_Frequency",
    "TeamRimFrequency",
    "TeamAvgShotDistance",
    "TeamRimFGPct",
    "Team3P_Pct",
    "OppAvgShotDistance",
    "OppRimFrequency",
    "Opp3P_Frequency",
    "OppRimFGPct",
    "Opp3P_Pct",
  ]);

  headers.forEach((header, index) => {
    const col = excelColumn(index);
    const range = sheet.getRange(`${col}2:${col}${rowCount}`);
    if (currencyColumns.has(header)) {
      range.format.numberFormat = "$#,##0";
    } else if (millionColumns.has(header)) {
      range.format.numberFormat = "$0.0";
    } else if (decimalColumns.has(header)) {
      range.format.numberFormat = "0.00";
    }
  });
}

function writeSheet(workbook, sheetName, rows) {
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const matrix = rows.map((row) => row.map(coerce));
  const rowCount = matrix.length;
  const colCount = matrix[0]?.length ?? 1;
  const fullRange = sheet.getRange(rangeAddress(rowCount, colCount));
  fullRange.values = matrix;

  const headerRange = sheet.getRange(`A1:${excelColumn(colCount - 1)}1`);
  headerRange.format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  fullRange.format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };
  sheet.freezePanes.freezeRows(1);

  for (let index = 0; index < colCount; index += 1) {
    const col = excelColumn(index);
    sheet.getRange(`${col}:${col}`).format.columnWidth = estimateWidth(matrix, index);
  }

  if (rowCount > 1 && colCount > 1) {
    const table = sheet.tables.add(rangeAddress(rowCount, colCount), true, cleanTableName(sheetName));
    table.style = "TableStyleMedium2";
    table.showFilterButton = true;
  }

  applyNumberFormats(sheet, matrix[0], rowCount);
  return sheet;
}

function topRows(rows, sortColumn, limit) {
  const headers = rows[0];
  const sortIndex = headers.indexOf(sortColumn);
  return rows
    .slice(1)
    .filter((row) => row[sortIndex] !== "")
    .sort((a, b) => Number(b[sortIndex]) - Number(a[sortIndex]))
    .slice(0, limit);
}

function addOverview(workbook, tableData, summary) {
  const sheet = workbook.worksheets.add("Overview");
  sheet.showGridLines = false;

  const factRows = tableData.get("Fact_Player_Value");
  const teamRows = tableData.get("Team_Efficiency");
  const factHeaders = factRows[0];
  const playerIndex = factHeaders.indexOf("PlayerName");
  const salaryTeamIndex = factHeaders.indexOf("SalaryTeam");
  const valueScoreIndex = factHeaders.indexOf("ValueScore");
  const salaryMillionsIndex = factHeaders.indexOf("SalaryMillions");
  const pointsIndex = factHeaders.indexOf("TotalPoints");
  const qualifiedIndex = factHeaders.indexOf("QualifiedForValueRank");
  const seasonIndex = factHeaders.indexOf("Season");
  const latestSeason = summary.latest_season ?? "";

  const qualifiedPlayers = factRows
    .slice(1)
    .filter((row) => row[qualifiedIndex] === "True" && (!latestSeason || row[seasonIndex] === latestSeason))
    .sort((a, b) => Number(b[valueScoreIndex]) - Number(a[valueScoreIndex]))
    .slice(0, 10);

  const teamHeaders = teamRows[0];
  const teamNameIndex = teamHeaders.indexOf("TeamName");
  const teamValueIndex = teamHeaders.indexOf("ValueScore");
  const payrollIndex = teamHeaders.indexOf("PayrollMillions");
  const teamSeasonIndex = teamHeaders.indexOf("Season");
  const topTeams = teamRows
    .slice(1)
    .filter((row) => !latestSeason || row[teamSeasonIndex] === latestSeason)
    .sort((a, b) => Number(b[teamValueIndex]) - Number(a[teamValueIndex]))
    .slice(0, 10);

  sheet.getRange("A1:H1").values = [["NBA Contract Value Analysis"]];
  sheet.mergeCells("A1:H1");
  sheet.getRange("A1:H1").format = {
    fill: "#0B1623",
    font: { bold: true, color: "#FFFFFF", size: 18 },
  };

  sheet.getRange("A3:B8").values = [
    ["Season range", summary.season_range],
    ["Latest season", summary.latest_season],
    ["Player-season rows", summary.regular_season_player_rows],
    ["Unique players", summary.unique_players],
    ["Salary-covered rows", summary.salary_covered_rows],
    ["Team context rows", summary.team_context_rows ?? ""],
  ];
  sheet.getRange("A3:A8").format = { fill: "#E9EEF5", font: { bold: true, color: "#17324D" } };
  sheet.getRange("A3:B8").format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };
  sheet.getRange("A:A").format.columnWidth = 28;
  sheet.getRange("B:B").format.columnWidth = 22;

  sheet.getRange("A10:F10").values = [["Top Qualified Players by Value Score"]];
  sheet.mergeCells("A10:F10");
  sheet.getRange("A10:F10").format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
  };

  const playerTable = [
    ["Player", "Team", "Salary $M", "Points", "Value Score", "Qualified"],
    ...qualifiedPlayers.map((row) => [
      row[playerIndex],
      row[salaryTeamIndex],
      Number(row[salaryMillionsIndex]),
      Number(row[pointsIndex]),
      Number(row[valueScoreIndex]),
      row[qualifiedIndex],
    ]),
  ];
  sheet.getRange(`A11:F${10 + playerTable.length}`).values = playerTable;
  sheet.getRange("A11:F11").format = {
    fill: "#4B5563",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange(`C12:C${10 + playerTable.length}`).format.numberFormat = "$0.0";
  sheet.getRange(`D12:E${10 + playerTable.length}`).format.numberFormat = "0.00";
  sheet.getRange(`A11:F${10 + playerTable.length}`).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E2EC",
  };
  sheet.getRange("C:C").format.columnWidth = 13;
  sheet.getRange("D:D").format.columnWidth = 12;
  sheet.getRange("E:E").format.columnWidth = 15;
  sheet.getRange("F:F").format.columnWidth = 12;

  const chartDataStart = 11;
  const chartRows = [
    ["Team", "Value Score", "Payroll $M"],
    ...topTeams.map((row) => [
      row[teamNameIndex],
      Number(row[teamValueIndex]),
      Number(row[payrollIndex]),
    ]),
  ];
  sheet.getRange(`H${chartDataStart}:J${chartDataStart + chartRows.length - 1}`).values = chartRows;
  sheet.getRange(`H${chartDataStart}:J${chartDataStart}`).format = {
    fill: "#4B5563",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange(`I${chartDataStart + 1}:J${chartDataStart + chartRows.length - 1}`).format.numberFormat = "0.00";
  sheet.getRange("H:J").format.columnWidth = 18;

  const chart = sheet.charts.add(
    "bar",
    sheet.getRange(`H${chartDataStart}:I${chartDataStart + chartRows.length - 1}`)
  );
  chart.title = "Top Teams by Value Score";
  chart.hasLegend = false;
  chart.xAxis = { axisType: "textAxis" };
  chart.yAxis = { numberFormatCode: "0" };
  chart.setPosition("L3", "T22");

  sheet.getRange("A24:D34").values = [
    ["Recommended Power BI pages", "", "", ""],
    ["1", "Executive Overview", "", ""],
    ["2", "Multi-Season Value Trends", "", ""],
    ["3", "Player Value Rankings", "", ""],
    ["4", "Contract Tiers and Payroll Strategy", "", ""],
    ["5", "Shot Profile and Play Style", "", ""],
    ["6", "Playoff Value", "", ""],
    ["7", "Prediction Lab", "", ""],
    ["8", "Methodology and Data Quality", "", ""],
    ["Import option", "Use CSVs in /data or import this workbook directly.", "", ""],
    ["Docs", "DAX formulas, relationships, theme, and visual layout are in /docs and /theme.", "", ""],
  ];
  sheet.mergeCells("A24:D24");
  sheet.mergeCells("B25:D25");
  sheet.mergeCells("B26:D26");
  sheet.mergeCells("B27:D27");
  sheet.mergeCells("B28:D28");
  sheet.mergeCells("B29:D29");
  sheet.mergeCells("B30:D30");
  sheet.mergeCells("B31:D31");
  sheet.mergeCells("B32:D32");
  sheet.mergeCells("B33:D33");
  sheet.mergeCells("B34:D34");
  sheet.getRange("A24:D24").format = { fill: "#17324D", font: { bold: true, color: "#FFFFFF" } };
  sheet.getRange("A25:A32").format = { fill: "#E9EEF5", font: { bold: true, color: "#17324D" } };
  sheet.getRange("A33:A34").format = { fill: "#E9EEF5", font: { bold: true, color: "#17324D" } };
  sheet.getRange("A24:D34").format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };
  sheet.getRange("B25:D34").format.wrapText = true;

  return sheet;
}

async function main() {
  await fs.mkdir(previewDir, { recursive: true });
  const summary = JSON.parse(await fs.readFile(path.join(outputDir, "project_summary.json"), "utf8"));

  const tableData = new Map();
  for (const [sheetName, filename] of tableFiles) {
    const text = await fs.readFile(path.join(dataDir, filename), "utf8");
    tableData.set(sheetName, parseCsv(text));
  }

  const workbook = Workbook.create();
  addOverview(workbook, tableData, summary);

  for (const [sheetName] of tableFiles) {
    writeSheet(workbook, sheetName, tableData.get(sheetName));
  }

  const overviewPreview = await workbook.render({
    sheetName: "Overview",
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(previewDir, "workbook_overview.png"),
    new Uint8Array(await overviewPreview.arrayBuffer())
  );

  for (const [sheetName] of [
    ["Fact_Player_Value"],
    ["Player_Playoff_Performance"],
    ["Player_Predictions"],
    ["Player_Shooting_Profile"],
    ["Team_Context"],
    ["Team_Payroll_Allocation"],
    ["Team_Efficiency"],
    ["Data_Dictionary"],
  ]) {
    const preview = await workbook.render({
      sheetName,
      range: "A1:H18",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(previewDir, `${sheetName.toLowerCase()}_preview.png`),
      new Uint8Array(await preview.arrayBuffer())
    );
  }

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: "formula error scan",
  });
  console.log(errors.ndjson);

  const output = await SpreadsheetFile.exportXlsx(workbook);
  const workbookPath = path.join(outputDir, "NBA_Contract_Value_Analysis.xlsx");
  await output.save(workbookPath);
  console.log(`Workbook saved to ${workbookPath}`);
}

main();
