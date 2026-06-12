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
  return Math.min(Math.max(maxLen + 2, 11), 38);
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
    fill: "#0B1623",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  fullRange.format.borders = { preset: "all", style: "thin", color: "#D7E0EA" };
  sheet.freezePanes.freezeRows(1);

  for (let index = 0; index < colCount; index += 1) {
    const col = excelColumn(index);
    sheet.getRange(`${col}:${col}`).format.columnWidth = estimateWidth(matrix, index);
  }

  if (rowCount > 1 && colCount > 1) {
    const table = sheet.tables.add(rangeAddress(rowCount, colCount), true, cleanTableName(sheetName));
    table.style = "TableStyleMedium4";
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

  const latestFactRows = factRows.slice(1).filter((row) => !latestSeason || row[seasonIndex] === latestSeason);
  const salaryCoveredRows = latestFactRows.filter((row) => row[factHeaders.indexOf("SalaryAvailable")] === "True").length;
  const salaryCoverage = latestFactRows.length ? salaryCoveredRows / latestFactRows.length : 0;

  sheet.getRange("A1:J1").values = [["NBA Contract Value Analysis", "", "", "", "", "", "", "", "", ""]];
  sheet.mergeCells("A1:J2");
  sheet.getRange("A1:J2").format = {
    fill: "#07111F",
    font: { bold: true, color: "#F8FAFC", size: 26 },
  };

  sheet.getRange("A3:J3").values = [[
    "Power BI-ready player salary, production, playoff, team context, and prediction model tables",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
  ]];
  sheet.mergeCells("A3:J3");
  sheet.getRange("A3:J3").format = {
    fill: "#07111F",
    font: { color: "#A8B3C5", size: 12 },
  };

  const kpis = [
    ["Season Range", String(summary.season_range).replace(" through ", " to "), "Model window"],
    ["Player-Seasons", summary.regular_season_player_rows, "Fact rows"],
    ["Unique Players", summary.unique_players, "Dim_Player"],
    ["Salary Coverage", salaryCoverage, "Latest season"],
    ["Playoff Rows", summary.playoff_rows, "Postseason"],
  ];
  const starts = ["A5", "C5", "E5", "G5", "I5"];
  kpis.forEach((kpi, index) => {
    const startCol = index * 2;
    const left = excelColumn(startCol);
    const right = excelColumn(startCol + 1);
    sheet.getRange(`${left}5:${right}7`).values = [
      [kpi[0], ""],
      [kpi[1], ""],
      [kpi[2], ""],
    ];
    sheet.mergeCells(`${left}5:${right}5`);
    sheet.mergeCells(`${left}6:${right}6`);
    sheet.mergeCells(`${left}7:${right}7`);
    sheet.getRange(`${left}5:${right}7`).format = {
      fill: "#102033",
      font: { color: "#F8FAFC" },
    };
    sheet.getRange(`${left}5:${right}5`).format = {
      fill: "#102033",
      font: { bold: true, color: "#A8B3C5", size: 10 },
    };
    sheet.getRange(`${left}6:${right}6`).format = {
      fill: "#102033",
      font: { bold: true, color: index === 3 ? "#22C55E" : "#F8FAFC", size: 17 },
    };
    sheet.getRange(`${left}7:${right}7`).format = {
      fill: "#102033",
      font: { color: "#A8B3C5", size: 10 },
    };
    sheet.getRange(`${left}5:${right}7`).format.borders = {
      preset: "all",
      style: "thin",
      color: "#27415F",
    };
  });
  sheet.getRange("C6:D6").format.numberFormat = "#,##0";
  sheet.getRange("E6:F6").format.numberFormat = "#,##0";
  sheet.getRange("G6:H6").format.numberFormat = "0.0%";
  sheet.getRange("I6:J6").format.numberFormat = "#,##0";

  sheet.getRange("A9:G9").values = [["Top Qualified Players by Value Score", "", "", "", "", "", ""]];
  sheet.mergeCells("A9:G9");
  sheet.getRange("A9:G9").format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
  };

  const playerTable = [
    ["Player", "Team", "Salary $M", "Points", "Est. Win Shares", "Value Score", "Tier"],
    ...qualifiedPlayers.map((row) => [
      row[playerIndex],
      row[salaryTeamIndex],
      Number(row[salaryMillionsIndex]),
      Number(row[pointsIndex]),
      Number(row[factHeaders.indexOf("EstimatedWinShares")]),
      Number(row[valueScoreIndex]),
      row[factHeaders.indexOf("PlayerValueTier")],
    ]),
  ];
  sheet.getRange(`A10:G${9 + playerTable.length}`).values = playerTable;
  sheet.getRange("A10:G10").format = {
    fill: "#4B5563",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange(`C11:C${9 + playerTable.length}`).format.numberFormat = "$0.0";
  sheet.getRange(`D11:F${9 + playerTable.length}`).format.numberFormat = "0.00";
  sheet.getRange(`A10:G${9 + playerTable.length}`).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E2EC",
  };
  sheet.getRange(`A11:G${9 + playerTable.length}`).format = {
    fill: "#F8FAFC",
    font: { color: "#0B1623" },
  };
  sheet.getRange("A:A").format.columnWidth = 28;
  sheet.getRange("B:B").format.columnWidth = 12;
  sheet.getRange("C:C").format.columnWidth = 13;
  sheet.getRange("D:D").format.columnWidth = 12;
  sheet.getRange("E:E").format.columnWidth = 15;
  sheet.getRange("F:F").format.columnWidth = 13;
  sheet.getRange("G:G").format.columnWidth = 24;

  const chartDataStart = 10;
  const chartRows = [
    ["Team", "Value Score", "Payroll $M"],
    ...topTeams.map((row) => [
      row[teamNameIndex],
      Number(row[teamValueIndex]),
      Number(row[payrollIndex]),
    ]),
  ];
  sheet.getRange(`I${chartDataStart}:K${chartDataStart + chartRows.length - 1}`).values = chartRows;
  sheet.getRange(`I${chartDataStart}:K${chartDataStart}`).format = {
    fill: "#4B5563",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange(`J${chartDataStart + 1}:K${chartDataStart + chartRows.length - 1}`).format.numberFormat = "0.00";
  sheet.getRange(`I${chartDataStart}:K${chartDataStart + chartRows.length - 1}`).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E2EC",
  };
  sheet.getRange("I:I").format.columnWidth = 22;
  sheet.getRange("J:K").format.columnWidth = 14;

  const chart = sheet.charts.add(
    "bar",
    sheet.getRange(`I${chartDataStart}:J${chartDataStart + chartRows.length - 1}`)
  );
  chart.title = "Top Teams by Value Score";
  chart.hasLegend = false;
  chart.xAxis = { axisType: "textAxis" };
  chart.yAxis = { numberFormatCode: "0" };
  chart.setPosition("M5", "T24");

  sheet.getRange("A23:K23").values = [["Power BI Build Path", "", "", "", "", "", "", "", "", "", ""]];
  sheet.mergeCells("A23:K23");
  sheet.getRange("A23:K23").format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A24:K28").values = [
    ["1", "Import CSVs from /data", "Fact_Player_Value, dimensions, team tables, predictions, and playoff performance", "", "", "", "Recommended pages", "", "", "", ""],
    ["2", "Create relationships", "Use Dim_Player, Dim_Team, Dim_Position, and Dim_Season as lookup tables", "", "", "", "Overview, Trends, Players, Contracts", "", "", "", ""],
    ["3", "Add DAX measures", "Use docs/dax_measures.md and data/measure_catalog.csv", "", "", "", "Shot Profile, Playoffs, Prediction Lab", "", "", "", ""],
    ["4", "Apply theme", "Import theme/nba-contract-value-theme.json", "", "", "", "Methodology and Data Quality", "", "", "", ""],
    ["5", "Design report", "Use docs/report_wireframe.md and the included mockup", "", "", "", "Keep CSV schemas stable for refresh", "", "", "", ""],
  ];
  for (let row = 24; row <= 28; row += 1) {
    sheet.mergeCells(`C${row}:F${row}`);
    sheet.mergeCells(`G${row}:K${row}`);
  }
  sheet.getRange("A24:A28").format = { fill: "#FBBF24", font: { bold: true, color: "#171007" } };
  sheet.getRange("B24:K28").format = { fill: "#F8FAFC", font: { color: "#0B1623" }, wrapText: true };
  sheet.getRange("B24:B28").format = { fill: "#E9EEF5", font: { bold: true, color: "#17324D" } };
  sheet.getRange("A23:K28").format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };

  sheet.getRange("A30:K30").values = [[
    "Source note",
    "EstimatedWinShares is a transparent production proxy because ESPN does not provide official win shares. CSV outputs remain the Power BI source of truth.",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
  ]];
  sheet.mergeCells("B30:K31");
  sheet.getRange("A30:A31").format = { fill: "#102033", font: { bold: true, color: "#FBBF24" } };
  sheet.getRange("B30:K31").format = { fill: "#102033", font: { color: "#F8FAFC" }, wrapText: true };
  sheet.getRange("A30:K31").format.borders = { preset: "all", style: "thin", color: "#27415F" };

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
