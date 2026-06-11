from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT
DATA_OUTPUT = OUTPUT / "data"
DOCS_OUTPUT = OUTPUT / "docs"
THEME_OUTPUT = OUTPUT / "theme"
ASSETS_OUTPUT = OUTPUT / "assets"

SEASON = "2025-26"
PULLED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

SOURCES = {
    "totals": "https://www.basketball-reference.com/leagues/NBA_2026_totals.html",
    "per_game": "https://www.basketball-reference.com/leagues/NBA_2026_per_game.html",
    "advanced": "https://www.basketball-reference.com/leagues/NBA_2026_advanced.html",
    "per_poss": "https://www.basketball-reference.com/leagues/NBA_2026_per_poss.html",
    "shooting": "https://www.basketball-reference.com/leagues/NBA_2026_shooting.html",
    "team_summary": "https://www.basketball-reference.com/leagues/NBA_2026.html",
    "team_ratings": "https://www.basketball-reference.com/leagues/NBA_2026_ratings.html",
    "salaries": "https://www.basketball-reference.com/contracts/players.html",
}

TEAM_META = {
    "ATL": ("Atlanta Hawks", "East", "Southeast"),
    "BOS": ("Boston Celtics", "East", "Atlantic"),
    "BRK": ("Brooklyn Nets", "East", "Atlantic"),
    "CHO": ("Charlotte Hornets", "East", "Southeast"),
    "CHI": ("Chicago Bulls", "East", "Central"),
    "CLE": ("Cleveland Cavaliers", "East", "Central"),
    "DAL": ("Dallas Mavericks", "West", "Southwest"),
    "DEN": ("Denver Nuggets", "West", "Northwest"),
    "DET": ("Detroit Pistons", "East", "Central"),
    "GSW": ("Golden State Warriors", "West", "Pacific"),
    "HOU": ("Houston Rockets", "West", "Southwest"),
    "IND": ("Indiana Pacers", "East", "Central"),
    "LAC": ("Los Angeles Clippers", "West", "Pacific"),
    "LAL": ("Los Angeles Lakers", "West", "Pacific"),
    "MEM": ("Memphis Grizzlies", "West", "Southwest"),
    "MIA": ("Miami Heat", "East", "Southeast"),
    "MIL": ("Milwaukee Bucks", "East", "Central"),
    "MIN": ("Minnesota Timberwolves", "West", "Northwest"),
    "NOP": ("New Orleans Pelicans", "West", "Southwest"),
    "NYK": ("New York Knicks", "East", "Atlantic"),
    "OKC": ("Oklahoma City Thunder", "West", "Northwest"),
    "ORL": ("Orlando Magic", "East", "Southeast"),
    "PHI": ("Philadelphia 76ers", "East", "Atlantic"),
    "PHO": ("Phoenix Suns", "West", "Pacific"),
    "POR": ("Portland Trail Blazers", "West", "Northwest"),
    "SAC": ("Sacramento Kings", "West", "Pacific"),
    "SAS": ("San Antonio Spurs", "West", "Southwest"),
    "TOR": ("Toronto Raptors", "East", "Atlantic"),
    "UTA": ("Utah Jazz", "West", "Northwest"),
    "WAS": ("Washington Wizards", "East", "Southeast"),
}

POSITION_SORT = {
    "PG": (1, "Guard"),
    "SG": (2, "Guard"),
    "SF": (3, "Wing"),
    "PF": (4, "Forward"),
    "C": (5, "Center"),
}

TEAM_NAME_TO_KEY = {name: key for key, (name, _, _) in TEAM_META.items()}
TEAM_NAME_TO_KEY["LA Clippers"] = "LAC"


def normalize_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("*", "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def normalize_team_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s*\(\d+\)", "", text)
    text = text.replace("*", "")
    return re.sub(r"\s+", " ", text).strip()


def flatten_column(column: object) -> str:
    if not isinstance(column, tuple):
        return str(column)
    parts = [
        str(part)
        for part in column
        if str(part)
        and not str(part).startswith("Unnamed")
        and str(part) != "nan"
    ]
    if not parts:
        return str(column[-1])
    if len(parts) == 1:
        return parts[0]
    return "_".join(parts)


def clean_numeric_columns(df: pd.DataFrame, skip: set[str]) -> pd.DataFrame:
    for col in df.columns:
        if col in skip:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def read_stat_table(url: str) -> pd.DataFrame:
    df = pd.read_html(url)[0]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    return clean_numeric_columns(df, {"Player", "Team", "Tm", "Pos", "Awards", "PlayerKeyRaw"})


def choose_player_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    team_col = "Team" if "Team" in df.columns else "Tm"
    rows = []
    for _, group in df.groupby("PlayerKeyRaw", sort=False):
        multi_team = group[group[team_col].astype(str).str.match(r"^[2-9]TM$")]
        if not multi_team.empty:
            rows.append(multi_team.iloc[0])
            continue
        sort_cols = [c for c in ["G", "MP"] if c in group.columns]
        if sort_cols:
            rows.append(group.sort_values(sort_cols, ascending=False).iloc[0])
        else:
            rows.append(group.iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True)


def flatten_salary_column(column: object) -> str:
    if not isinstance(column, tuple):
        return str(column)
    parts = [str(part) for part in column if not str(part).startswith("Unnamed")]
    return parts[-1] if parts else str(column[-1])


def parse_money(value: object) -> float:
    if pd.isna(value):
        return np.nan
    digits = re.sub(r"[^0-9.-]", "", str(value))
    if not digits:
        return np.nan
    return float(digits)


def read_salary_table(url: str) -> pd.DataFrame:
    df = pd.read_html(url)[0]
    df.columns = [flatten_salary_column(col) for col in df.columns]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    keep_cols = ["Player", "Tm", SEASON, "Guaranteed", "PlayerKeyRaw"]
    df = df[keep_cols].rename(
        columns={
            "Player": "SalaryPlayer",
            "Tm": "SalaryTeam",
            SEASON: "Salary",
            "Guaranteed": "GuaranteedSalary",
        }
    )
    df["Salary"] = df["Salary"].map(parse_money)
    df["GuaranteedSalary"] = df["GuaranteedSalary"].map(parse_money)
    return df.dropna(subset=["Salary"]).reset_index(drop=True)


def read_per_possession_table(url: str) -> pd.DataFrame:
    df = choose_player_total_rows(read_stat_table(url))
    df = df.rename(
        columns={
            "PTS": "PTSPer100",
            "TRB": "TRBPer100",
            "AST": "ASTPer100",
            "STL": "STLPer100",
            "BLK": "BLKPer100",
            "TOV": "TOVPer100",
            "ORtg": "PlayerORtg",
            "DRtg": "PlayerDRtg",
        }
    )
    return df[
        [
            "PlayerKeyRaw",
            "PTSPer100",
            "TRBPer100",
            "ASTPer100",
            "STLPer100",
            "BLKPer100",
            "TOVPer100",
            "PlayerORtg",
            "PlayerDRtg",
        ]
    ]


def read_player_shooting_table(url: str) -> pd.DataFrame:
    df = pd.read_html(url)[0]
    df.columns = [flatten_column(col) for col in df.columns]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    df = clean_numeric_columns(df, {"Player", "Team", "Pos", "Awards", "PlayerKeyRaw"})
    df = choose_player_total_rows(df)
    df = df.rename(
        columns={
            "Team": "StatsTeam",
            "Dist.": "AvgShotDistance",
            "% of FGA by Distance_2P": "FGA_2P_Frequency",
            "% of FGA by Distance_0-3": "FGA_0_3_Frequency",
            "% of FGA by Distance_3-10": "FGA_3_10_Frequency",
            "% of FGA by Distance_10-16": "FGA_10_16_Frequency",
            "% of FGA by Distance_16-3P": "FGA_16_3P_Frequency",
            "% of FGA by Distance_3P": "FGA_3P_Frequency",
            "FG% by Distance_2P": "FG_2P_Pct",
            "FG% by Distance_0-3": "FG_0_3_Pct",
            "FG% by Distance_3-10": "FG_3_10_Pct",
            "FG% by Distance_10-16": "FG_10_16_Pct",
            "FG% by Distance_16-3P": "FG_16_3P_Pct",
            "FG% by Distance_3P": "FG_3P_Pct",
            "% of FG Ast'd_2P": "Assisted2P_Pct",
            "% of FG Ast'd_3P": "Assisted3P_Pct",
            "Dunks_%FGA": "Dunk_FGA_Pct",
            "Dunks_#": "DunksMade",
            "Corner 3s_%3PA": "Corner3_Frequency",
            "Corner 3s_3P%": "Corner3Pct",
            "1/2 Court_Att.": "HalfCourtAttempts",
            "1/2 Court_Md.": "HalfCourtMakes",
        }
    )
    return df[
        [
            "PlayerKeyRaw",
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
            "DunksMade",
            "Corner3_Frequency",
            "Corner3Pct",
            "HalfCourtAttempts",
            "HalfCourtMakes",
        ]
    ]


def prep_team_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [flatten_column(col) for col in df.columns]
    df = df[df["Team"].astype(str) != "Team"].copy()
    df["TeamName"] = df["Team"].map(normalize_team_name)
    df["TeamKey"] = df["TeamName"].map(TEAM_NAME_TO_KEY)
    df = df.dropna(subset=["TeamKey"])
    return clean_numeric_columns(df, {"Team", "TeamName", "TeamKey", "Conf", "Div", "Arena"})


def read_team_context(summary_url: str, ratings_url: str) -> pd.DataFrame:
    ratings = prep_team_table(pd.read_html(ratings_url)[0]).rename(
        columns={
            "W/L%": "WinPct",
            "Unadjusted_MOV": "MOV",
            "Unadjusted_ORtg": "UnadjustedORtg",
            "Unadjusted_DRtg": "UnadjustedDRtg",
            "Unadjusted_NRtg": "UnadjustedNetRtg",
            "Adjusted_MOV/A": "AdjustedMOV",
            "Adjusted_ORtg/A": "AdjustedORtg",
            "Adjusted_DRtg/A": "AdjustedDRtg",
            "Adjusted_NRtg/A": "AdjustedNetRtg",
        }
    )
    ratings = ratings[
        [
            "TeamKey",
            "TeamName",
            "Conf",
            "Div",
            "W",
            "L",
            "WinPct",
            "MOV",
            "UnadjustedORtg",
            "UnadjustedDRtg",
            "UnadjustedNetRtg",
            "AdjustedMOV",
            "AdjustedORtg",
            "AdjustedDRtg",
            "AdjustedNetRtg",
        ]
    ]

    summary_tables = pd.read_html(summary_url)
    advanced = prep_team_table(summary_tables[10]).rename(
        columns={
            "Age": "AvgAge",
            "PW": "PythagoreanWins",
            "PL": "PythagoreanLosses",
            "SOS": "StrengthOfSchedule",
            "ORtg": "TeamORtg",
            "DRtg": "TeamDRtg",
            "NRtg": "TeamNetRtg",
            "FTr": "FreeThrowRate",
            "3PAr": "ThreePointAttemptRate",
            "TS%": "TrueShootingPct",
            "Offense Four Factors_eFG%": "Off_eFGPct",
            "Offense Four Factors_TOV%": "Off_TOVPct",
            "Offense Four Factors_ORB%": "Off_ORBPct",
            "Offense Four Factors_FT/FGA": "Off_FTPerFGA",
            "Defense Four Factors_eFG%": "Def_eFGPct",
            "Defense Four Factors_TOV%": "Def_TOVPct",
            "Defense Four Factors_DRB%": "Def_DRBPct",
            "Defense Four Factors_FT/FGA": "Def_FTPerFGA",
            "Attend.": "Attendance",
            "Attend./G": "AttendancePerGame",
        }
    )
    advanced = advanced[
        [
            "TeamKey",
            "AvgAge",
            "PythagoreanWins",
            "PythagoreanLosses",
            "StrengthOfSchedule",
            "SRS",
            "Pace",
            "FreeThrowRate",
            "ThreePointAttemptRate",
            "TrueShootingPct",
            "Off_eFGPct",
            "Off_TOVPct",
            "Off_ORBPct",
            "Off_FTPerFGA",
            "Def_eFGPct",
            "Def_TOVPct",
            "Def_DRBPct",
            "Def_FTPerFGA",
            "Arena",
            "Attendance",
            "AttendancePerGame",
        ]
    ]

    team_shooting = prep_team_table(summary_tables[11]).rename(
        columns={
            "Dist.": "TeamAvgShotDistance",
            "% of FGA by Distance_0-3": "TeamRimFrequency",
            "% of FGA by Distance_3P": "Team3P_Frequency",
            "FG% by Distance_0-3": "TeamRimFGPct",
            "FG% by Distance_3P": "Team3P_Pct",
            "Dunks_%FGA": "TeamDunk_FGA_Pct",
            "Layups_%FGA": "TeamLayup_FGA_Pct",
            "Corner_%3PA": "TeamCorner3_Frequency",
            "Corner_3P%": "TeamCorner3Pct",
        }
    )
    team_shooting = team_shooting[
        [
            "TeamKey",
            "TeamAvgShotDistance",
            "TeamRimFrequency",
            "Team3P_Frequency",
            "TeamRimFGPct",
            "Team3P_Pct",
            "TeamDunk_FGA_Pct",
            "TeamLayup_FGA_Pct",
            "TeamCorner3_Frequency",
            "TeamCorner3Pct",
        ]
    ]

    opponent_shooting = prep_team_table(summary_tables[12]).rename(
        columns={
            "Dist.": "OppAvgShotDistance",
            "% of FGA by Distance_0-3": "OppRimFrequency",
            "% of FGA by Distance_3P": "Opp3P_Frequency",
            "FG% by Distance_0-3": "OppRimFGPct",
            "FG% by Distance_3P": "Opp3P_Pct",
            "Dunks_%FGA": "OppDunk_FGA_Pct",
            "Layups_%FGA": "OppLayup_FGA_Pct",
            "Corner_%3PA": "OppCorner3_Frequency",
            "Corner_3P%": "OppCorner3Pct",
        }
    )
    opponent_shooting = opponent_shooting[
        [
            "TeamKey",
            "OppAvgShotDistance",
            "OppRimFrequency",
            "Opp3P_Frequency",
            "OppRimFGPct",
            "Opp3P_Pct",
            "OppDunk_FGA_Pct",
            "OppLayup_FGA_Pct",
            "OppCorner3_Frequency",
            "OppCorner3Pct",
        ]
    ]

    return (
        ratings.merge(advanced, on="TeamKey", how="left")
        .merge(team_shooting, on="TeamKey", how="left")
        .merge(opponent_shooting, on="TeamKey", how="left")
        .sort_values("AdjustedNetRtg", ascending=False)
        .reset_index(drop=True)
    )


def first_position(position: object) -> str:
    if pd.isna(position):
        return "Unknown"
    return str(position).split("-")[0]


def position_group(position: object) -> str:
    pos = first_position(position)
    return POSITION_SORT.get(pos, (99, "Unknown"))[1]


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return np.where((denominator.notna()) & (denominator != 0), numerator / denominator, np.nan)


def csv_currency(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"${float(value):,.0f}"


def markdown_table(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    rows = [headers]
    for _, row in df.iterrows():
        rendered = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                rendered.append("" if math.isnan(float(value)) else f"{float(value):.2f}")
            else:
                rendered.append("" if pd.isna(value) else str(value))
        rows.append(rendered)

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(headers))]
    header_line = "| " + " | ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers))) + " |"
    rule_line = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body_lines = [
        "| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |"
        for row in rows[1:]
    ]
    return "\n".join([header_line, rule_line, *body_lines])


def build_tables() -> dict[str, pd.DataFrame]:
    totals = choose_player_total_rows(read_stat_table(SOURCES["totals"]))
    per_game = choose_player_total_rows(read_stat_table(SOURCES["per_game"]))
    advanced = choose_player_total_rows(read_stat_table(SOURCES["advanced"]))
    per_poss = read_per_possession_table(SOURCES["per_poss"])
    shooting = read_player_shooting_table(SOURCES["shooting"])
    team_context = read_team_context(SOURCES["team_summary"], SOURCES["team_ratings"])
    salaries = read_salary_table(SOURCES["salaries"])

    totals = totals.rename(
        columns={
            "Team": "StatsTeam",
            "PTS": "TotalPoints",
            "TRB": "TotalRebounds",
            "AST": "TotalAssists",
            "STL": "TotalSteals",
            "BLK": "TotalBlocks",
            "TOV": "TotalTurnovers",
            "MP": "TotalMinutes",
        }
    )
    per_game = per_game.rename(
        columns={
            "Team": "PerGameTeam",
            "PTS": "PPG",
            "TRB": "RPG",
            "AST": "APG",
            "STL": "SPG",
            "BLK": "BPG",
            "TOV": "TPG",
            "MP": "MPG",
        }
    )
    advanced = advanced.rename(
        columns={
            "Team": "AdvancedTeam",
            "TS%": "TS_Pct",
            "USG%": "USG_Pct",
            "TRB%": "TRB_Pct",
            "AST%": "AST_Pct",
            "STL%": "STL_Pct",
            "BLK%": "BLK_Pct",
            "TOV%": "TOV_Pct",
        }
    )

    total_cols = [
        "PlayerKeyRaw",
        "Player",
        "Age",
        "StatsTeam",
        "Pos",
        "G",
        "GS",
        "TotalMinutes",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "3P%",
        "2P",
        "2PA",
        "2P%",
        "eFG%",
        "FT",
        "FTA",
        "FT%",
        "ORB",
        "DRB",
        "TotalRebounds",
        "TotalAssists",
        "TotalSteals",
        "TotalBlocks",
        "TotalTurnovers",
        "PF",
        "TotalPoints",
        "Trp-Dbl",
        "Awards",
    ]
    per_game_cols = ["PlayerKeyRaw", "MPG", "PPG", "RPG", "APG", "SPG", "BPG", "TPG"]
    advanced_cols = [
        "PlayerKeyRaw",
        "PER",
        "TS_Pct",
        "USG_Pct",
        "TRB_Pct",
        "AST_Pct",
        "STL_Pct",
        "BLK_Pct",
        "TOV_Pct",
        "OWS",
        "DWS",
        "WS",
        "WS/48",
        "OBPM",
        "DBPM",
        "BPM",
        "VORP",
    ]

    stats = (
        totals[total_cols]
        .merge(per_game[per_game_cols], on="PlayerKeyRaw", how="left")
        .merge(advanced[advanced_cols], on="PlayerKeyRaw", how="left")
    )

    fact = salaries.merge(stats, on="PlayerKeyRaw", how="left")
    fact["PlayerName"] = fact["Player"].fillna(fact["SalaryPlayer"])
    fact["Season"] = SEASON
    fact["Position"] = fact["Pos"].map(first_position)
    fact["PositionGroup"] = fact["Pos"].map(position_group)
    fact["SalaryMillions"] = fact["Salary"] / 1_000_000
    fact["GuaranteedMillions"] = fact["GuaranteedSalary"] / 1_000_000
    fact["ProductionScore"] = (
        fact["TotalPoints"].fillna(0)
        + 1.2 * fact["TotalRebounds"].fillna(0)
        + 1.5 * fact["TotalAssists"].fillna(0)
        + 3.0 * fact["TotalSteals"].fillna(0)
        + 3.0 * fact["TotalBlocks"].fillna(0)
        - fact["TotalTurnovers"].fillna(0)
    )
    fact["EstimatedWinShares"] = fact["ProductionScore"] / 300
    if "WS" not in fact.columns:
        fact["WS"] = fact["EstimatedWinShares"]
    else:
        fact["WS"] = fact["WS"].fillna(fact["EstimatedWinShares"])
    fact["CostPerPoint"] = safe_divide(fact["Salary"], fact["TotalPoints"])
    fact["CostPerEstimatedWinShare"] = safe_divide(
        fact["Salary"], fact["EstimatedWinShares"].where(fact["EstimatedWinShares"] > 0)
    )
    fact["CostPerWinShare"] = fact["CostPerEstimatedWinShare"]
    fact["PointsPerMillion"] = safe_divide(fact["TotalPoints"], fact["SalaryMillions"])
    fact["EstimatedWinSharesPerMillion"] = safe_divide(fact["EstimatedWinShares"], fact["SalaryMillions"])
    fact["WinSharesPerMillion"] = fact["EstimatedWinSharesPerMillion"]
    fact["ValueScore"] = safe_divide(fact["ProductionScore"], fact["SalaryMillions"])
    fact["QualifiedForValueRank"] = (
        (fact["G"].fillna(0) >= 20)
        & (fact["TotalMinutes"].fillna(0) >= 500)
        & (fact["Salary"].fillna(0) > 0)
    )

    fact = fact.sort_values(["PlayerName", "SalaryTeam"]).reset_index(drop=True)
    fact["PlayerKey"] = ["P" + str(i + 1).zfill(4) for i in range(len(fact))]

    qualified = fact["QualifiedForValueRank"]
    fact["SalaryRank"] = fact.loc[qualified, "Salary"].rank(method="dense", ascending=False)
    fact["ProductionRank"] = fact.loc[qualified, "ProductionScore"].rank(method="dense", ascending=False)
    fact["ValueRank"] = fact.loc[qualified, "ValueScore"].rank(method="dense", ascending=False)
    fact["ValueGap"] = fact["SalaryRank"] - fact["ProductionRank"]
    fact["IsMatchedToStats"] = fact["G"].notna()
    fact["SourceSeasonNote"] = "Basketball Reference 2025-26 stats and 2025-26 listed salary"

    player_bridge = fact[["PlayerKeyRaw", "PlayerKey", "Season", "PlayerName", "SalaryTeam", "StatsTeam"]].copy()
    player_pace_adjusted = player_bridge.merge(per_poss, on="PlayerKeyRaw", how="inner").drop(columns=["PlayerKeyRaw"])
    player_shooting_profile = player_bridge.merge(shooting, on="PlayerKeyRaw", how="inner").drop(columns=["PlayerKeyRaw"])

    fact_columns = [
        "PlayerKey",
        "Season",
        "PlayerName",
        "SalaryTeam",
        "StatsTeam",
        "Position",
        "PositionGroup",
        "Age",
        "Salary",
        "SalaryMillions",
        "GuaranteedSalary",
        "GuaranteedMillions",
        "G",
        "GS",
        "TotalMinutes",
        "MPG",
        "TotalPoints",
        "PPG",
        "TotalRebounds",
        "RPG",
        "TotalAssists",
        "APG",
        "TotalSteals",
        "SPG",
        "TotalBlocks",
        "BPG",
        "TotalTurnovers",
        "TPG",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "3P%",
        "2P",
        "2PA",
        "2P%",
        "eFG%",
        "FT",
        "FTA",
        "FT%",
        "PER",
        "TS_Pct",
        "USG_Pct",
        "WS",
        "WS/48",
        "BPM",
        "VORP",
        "ProductionScore",
        "CostPerPoint",
        "CostPerWinShare",
        "PointsPerMillion",
        "WinSharesPerMillion",
        "ValueScore",
        "SalaryRank",
        "ProductionRank",
        "ValueRank",
        "ValueGap",
        "QualifiedForValueRank",
        "IsMatchedToStats",
        "Awards",
        "SourceSeasonNote",
    ]
    fact = fact[fact_columns]

    dim_player = fact[
        [
            "PlayerKey",
            "PlayerName",
            "Position",
            "PositionGroup",
            "Age",
            "SalaryTeam",
            "StatsTeam",
            "Awards",
            "QualifiedForValueRank",
            "IsMatchedToStats",
        ]
    ].copy()
    dim_player["IsAllStar"] = dim_player["Awards"].fillna("").str.contains(r"\bAS\b", regex=True)

    dim_team = []
    for key, (name, conference, division) in TEAM_META.items():
        dim_team.append(
            {
                "TeamKey": key,
                "TeamName": name,
                "Conference": conference,
                "Division": division,
            }
        )
    dim_team = pd.DataFrame(dim_team)

    dim_position = pd.DataFrame(
        [
            {
                "Position": position,
                "PositionGroup": meta[1],
                "SortOrder": meta[0],
            }
            for position, meta in POSITION_SORT.items()
        ]
    )

    matched_fact = fact[fact["IsMatchedToStats"]].copy()
    team_efficiency = (
        matched_fact.groupby(["Season", "SalaryTeam"], dropna=False)
        .agg(
            Payroll=("Salary", "sum"),
            GuaranteedSalary=("GuaranteedSalary", "sum"),
            PlayerCount=("PlayerKey", "nunique"),
            QualifiedPlayers=("QualifiedForValueRank", "sum"),
            TotalPoints=("TotalPoints", "sum"),
            TotalRebounds=("TotalRebounds", "sum"),
            TotalAssists=("TotalAssists", "sum"),
            TotalEstimatedWinShares=("EstimatedWinShares", "sum"),
            ProductionScore=("ProductionScore", "sum"),
        )
        .reset_index()
        .rename(columns={"SalaryTeam": "TeamKey"})
    )
    team_efficiency["PayrollMillions"] = team_efficiency["Payroll"] / 1_000_000
    team_efficiency["CostPerPoint"] = safe_divide(team_efficiency["Payroll"], team_efficiency["TotalPoints"])
    team_efficiency["CostPerWinShare"] = safe_divide(
        team_efficiency["Payroll"], team_efficiency["TotalWinShares"].where(team_efficiency["TotalWinShares"] > 0)
    )
    team_efficiency["PointsPerMillion"] = safe_divide(
        team_efficiency["TotalPoints"], team_efficiency["PayrollMillions"]
    )
    team_efficiency["ValueScore"] = safe_divide(
        team_efficiency["ProductionScore"], team_efficiency["PayrollMillions"]
    )
    team_efficiency = team_efficiency.merge(dim_team, on="TeamKey", how="left")
    team_efficiency = team_efficiency.merge(
        team_context[
            [
                "TeamKey",
                "W",
                "L",
                "WinPct",
                "Pace",
                "AdjustedORtg",
                "AdjustedDRtg",
                "AdjustedNetRtg",
                "Team3P_Frequency",
                "TeamRimFrequency",
            ]
        ],
        on="TeamKey",
        how="left",
    )
    team_efficiency = team_efficiency[
        [
            "Season",
            "TeamKey",
            "TeamName",
            "Conference",
            "Division",
            "Payroll",
            "PayrollMillions",
            "GuaranteedSalary",
            "W",
            "L",
            "WinPct",
            "Pace",
            "AdjustedORtg",
            "AdjustedDRtg",
            "AdjustedNetRtg",
            "PlayerCount",
            "QualifiedPlayers",
            "TotalPoints",
            "TotalRebounds",
            "TotalAssists",
            "TotalWinShares",
            "TotalVORP",
            "ProductionScore",
            "CostPerPoint",
            "CostPerWinShare",
            "PointsPerMillion",
            "ValueScore",
            "Team3P_Frequency",
            "TeamRimFrequency",
        ]
    ].sort_values("ValueScore", ascending=False)

    unmatched_salaries = fact[~fact["IsMatchedToStats"]][
        ["PlayerKey", "PlayerName", "Season", "SalaryTeam", "Salary", "GuaranteedSalary"]
    ].copy()

    data_dictionary = pd.DataFrame(
        [
            ("Fact_Player_Value", "PlayerKey", "Text", "Unique player row key for this project dataset."),
            ("Fact_Player_Value", "Season", "Text", "NBA season used for salary and performance analysis."),
            ("Fact_Player_Value", "PlayerName", "Text", "Player display name."),
            ("Fact_Player_Value", "SalaryTeam", "Text", "Team abbreviation from the salary/contracts table."),
            ("Fact_Player_Value", "StatsTeam", "Text", "Team abbreviation from the stats table. Multi-team players use the Basketball Reference combined row."),
            ("Fact_Player_Value", "Salary", "Currency", "Listed player salary for the selected season."),
            ("Fact_Player_Value", "TotalPoints", "Number", "Total points scored in the selected season."),
            ("Fact_Player_Value", "TotalRebounds", "Number", "Total rebounds in the selected season."),
            ("Fact_Player_Value", "TotalAssists", "Number", "Total assists in the selected season."),
            ("Fact_Player_Value", "WS", "Number", "Basketball Reference win shares."),
            ("Fact_Player_Value", "VORP", "Number", "Basketball Reference value over replacement player."),
            ("Fact_Player_Value", "ProductionScore", "Number", "Custom box-score production score: PTS + 1.2*REB + 1.5*AST + 3*STL + 3*BLK - TOV."),
            ("Fact_Player_Value", "CostPerPoint", "Currency", "Salary divided by total points. Lower is better."),
            ("Fact_Player_Value", "CostPerWinShare", "Currency", "Salary divided by win shares. Lower is better."),
            ("Fact_Player_Value", "ValueScore", "Number", "ProductionScore divided by salary in millions. Higher is better."),
            ("Fact_Player_Value", "ValueGap", "Number", "Salary rank minus production rank. Positive means production outranks salary."),
            ("Team_Efficiency", "Payroll", "Currency", "Sum of player salaries by salary team."),
            ("Team_Efficiency", "CostPerWinShare", "Currency", "Team payroll divided by player win shares."),
            ("Team_Efficiency", "ValueScore", "Number", "Team production score divided by payroll in millions."),
            ("Team_Context", "AdjustedNetRtg", "Number", "Basketball Reference adjusted net rating by team."),
            ("Team_Context", "Pace", "Number", "Estimated possessions per 48 minutes by team."),
            ("Team_Context", "Team3P_Frequency", "Number", "Share of team field goal attempts from three-point range."),
            ("Player_Pace_Adjusted", "PTSPer100", "Number", "Player points per 100 team possessions."),
            ("Player_Pace_Adjusted", "PlayerORtg", "Number", "Basketball Reference player offensive rating."),
            ("Player_Shooting_Profile", "AvgShotDistance", "Number", "Average field goal attempt distance in feet."),
            ("Player_Shooting_Profile", "FGA_3P_Frequency", "Number", "Share of player field goal attempts from three-point range."),
            ("Player_Shooting_Profile", "FGA_0_3_Frequency", "Number", "Share of player field goal attempts from 0-3 feet."),
            ("Player_Shooting_Profile", "Corner3Pct", "Number", "Player field goal percentage on corner threes."),
            ("Dim_Team", "TeamKey", "Text", "NBA team abbreviation."),
            ("Dim_Position", "SortOrder", "Number", "Suggested sort order for positions in visuals."),
        ],
        columns=["TableName", "ColumnName", "DataType", "Description"],
    )

    measure_catalog = pd.DataFrame(
        [
            (
                "Total Salary",
                "SUM(Fact_Player_Value[Salary])",
                "Currency",
                "Total salary in the current filter context.",
            ),
            (
                "Salary Millions",
                "DIVIDE([Total Salary], 1000000)",
                "Decimal",
                "Total salary shown in millions.",
            ),
            (
                "Total Points",
                "SUM(Fact_Player_Value[TotalPoints])",
                "Whole number",
                "Total points scored.",
            ),
            (
                "Total Win Shares",
                "SUM(Fact_Player_Value[WS])",
                "Decimal",
                "Total win shares.",
            ),
            (
                "Production Score",
                "SUM(Fact_Player_Value[ProductionScore])",
                "Decimal",
                "Weighted box-score production score.",
            ),
            (
                "Cost Per Point",
                "DIVIDE([Total Salary], [Total Points])",
                "Currency",
                "Salary spent for each point scored. Lower is better.",
            ),
            (
                "Cost Per Win Share",
                "DIVIDE([Total Salary], [Total Win Shares])",
                "Currency",
                "Salary spent for each win share. Lower is better.",
            ),
            (
                "Value Score",
                "DIVIDE([Production Score], [Salary Millions])",
                "Decimal",
                "Production generated per $1M of salary. Higher is better.",
            ),
            (
                "Player Count",
                "DISTINCTCOUNT(Fact_Player_Value[PlayerKey])",
                "Whole number",
                "Number of players in the current context.",
            ),
            (
                "Value Rank",
                "RANKX(ALLSELECTED(Dim_Player[PlayerName]), [Value Score], , DESC)",
                "Whole number",
                "Ranks selected players by value score.",
            ),
            (
                "Avg Player ORtg",
                "AVERAGE(Player_Pace_Adjusted[PlayerORtg])",
                "Decimal",
                "Average Basketball Reference offensive rating for selected players.",
            ),
            (
                "Avg Shot Distance",
                "AVERAGE(Player_Shooting_Profile[AvgShotDistance])",
                "Decimal",
                "Average field goal attempt distance for selected players.",
            ),
            (
                "Team Adjusted Net Rating",
                "AVERAGE(Team_Context[AdjustedNetRtg])",
                "Decimal",
                "Adjusted team net rating in the current filter context.",
            ),
            (
                "Payroll Per Win",
                "DIVIDE([Total Salary], SUM(Team_Efficiency[W]))",
                "Currency",
                "Team salary spend per regular-season win.",
            ),
        ],
        columns=["MeasureName", "DAX", "Format", "Description"],
    )

    source_notes = pd.DataFrame(
        [
            ("Season", SEASON),
            ("PulledAtLocalTime", PULLED_AT),
            ("Stats source", SOURCES["totals"]),
            ("Per-game source", SOURCES["per_game"]),
            ("Advanced source", SOURCES["advanced"]),
            ("Per-100 source", SOURCES["per_poss"]),
            ("Player shooting source", SOURCES["shooting"]),
            ("Team summary source", SOURCES["team_summary"]),
            ("Team ratings source", SOURCES["team_ratings"]),
            ("Salary source", SOURCES["salaries"]),
            ("Matched salary rows", str(int(fact["IsMatchedToStats"].sum()))),
            ("Unmatched salary rows", str(int((~fact["IsMatchedToStats"]).sum()))),
            ("Value rank qualifier", "At least 20 games, 500 minutes, and positive listed salary."),
            ("Player pace-adjusted rows", str(len(player_pace_adjusted))),
            ("Player shooting profile rows", str(len(player_shooting_profile))),
            ("Team context rows", str(len(team_context))),
        ],
        columns=["Item", "Value"],
    )

    return {
        "Fact_Player_Value": fact,
        "Team_Efficiency": team_efficiency,
        "Team_Context": team_context,
        "Player_Pace_Adjusted": player_pace_adjusted,
        "Player_Shooting_Profile": player_shooting_profile,
        "Dim_Player": dim_player,
        "Dim_Team": dim_team,
        "Dim_Position": dim_position,
        "Data_Dictionary": data_dictionary,
        "Measure_Catalog": measure_catalog,
        "Source_Notes": source_notes,
        "Unmatched_Salaries": unmatched_salaries,
    }


def write_docs(tables: dict[str, pd.DataFrame]) -> None:
    fact = tables["Fact_Player_Value"]
    team_eff = tables["Team_Efficiency"]
    team_context = tables["Team_Context"]
    player_pace = tables["Player_Pace_Adjusted"]
    player_shooting = tables["Player_Shooting_Profile"]
    matched = int(fact["IsMatchedToStats"].sum())
    total = len(fact)
    qualified = int(fact["QualifiedForValueRank"].sum())
    top_values = (
        fact[fact["QualifiedForValueRank"]]
        .sort_values("ValueScore", ascending=False)
        .head(10)[["PlayerName", "SalaryTeam", "SalaryMillions", "TotalPoints", "WS", "ValueScore", "ValueGap"]]
    )
    best_team = team_eff.sort_values("ValueScore", ascending=False).iloc[0]
    top_table = markdown_table(top_values)

    readme = f"""# NBA Contract Value Analysis

## Project Question

Which NBA players and teams delivered the most on-court production for the money during the **{SEASON}** season?

This starter project is built for Power BI. It includes cleaned CSV tables, an Excel workbook version of the same model, DAX measures, and a page-by-page report plan.

## Data Sources

- Player totals: {SOURCES["totals"]}
- Player per-game stats: {SOURCES["per_game"]}
- Player advanced stats: {SOURCES["advanced"]}
- Player per-100-possession stats: {SOURCES["per_poss"]}
- Player shooting profile: {SOURCES["shooting"]}
- Team summary and four factors: {SOURCES["team_summary"]}
- Team adjusted ratings: {SOURCES["team_ratings"]}
- Player salaries/contracts: {SOURCES["salaries"]}

Data was pulled locally on **{PULLED_AT}**. Basketball Reference tables can update, so refresh the generated CSVs before submitting a final project if current numbers matter.

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

- Salary rows: **{total:,}**
- Matched salary + stat rows: **{matched:,}**
- Qualified value-rank players: **{qualified:,}**
- Pace-adjusted player rows: **{len(player_pace):,}**
- Player shooting-profile rows: **{len(player_shooting):,}**
- Team context rows: **{len(team_context):,}**
- Top team by team value score: **{best_team["TeamName"]}**

## Early Insight Starters

Top qualified players by value score in the current extract:

{top_table}

Use these as starting points, not final conclusions. In the report, add slicers for conference, team, position, and qualified-player status so the audience can test the story.
"""

    dax = """# Suggested Power BI DAX Measures

Create these measures on the `Fact_Player_Value` table after importing the CSVs or workbook.

```DAX
Total Salary = SUM(Fact_Player_Value[Salary])

Salary Millions = DIVIDE([Total Salary], 1000000)

Total Points = SUM(Fact_Player_Value[TotalPoints])

Total Rebounds = SUM(Fact_Player_Value[TotalRebounds])

Total Assists = SUM(Fact_Player_Value[TotalAssists])

Estimated Win Shares = SUM(Fact_Player_Value[EstimatedWinShares])

Total VORP = SUM(Fact_Player_Value[VORP])

Production Score = SUM(Fact_Player_Value[ProductionScore])

Cost Per Point = DIVIDE([Total Salary], [Total Points])

Cost Per Estimated Win Share = DIVIDE([Total Salary], [Estimated Win Shares])

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
"""

    build_guide = """# Power BI Build Guide

## 1. Import Data

Use **Get Data > Text/CSV** and import these files from the `data` folder:

- `fact_player_value.csv`
- `player_pace_adjusted.csv`
- `player_shooting_profile.csv`
- `team_efficiency.csv`
- `team_context.csv`
- `dim_player.csv`
- `dim_team.csv`
- `dim_position.csv`

You can also import `NBA_Contract_Value_Analysis.xlsx` if you prefer a single workbook source.

## 2. Set Data Types

In Power Query:

- Set `Salary`, `GuaranteedSalary`, `CostPerPoint`, and `CostPerWinShare` to decimal number or currency.
- Set `QualifiedForValueRank` and `IsMatchedToStats` to true/false.
- Set rank columns to whole number.
- Set `AvgShotDistance`, ratings, pace, and percentage/frequency columns to decimal number.
- Keep `PlayerKey`, `TeamKey`, `SalaryTeam`, `StatsTeam`, and `Position` as text.

## 3. Create Relationships

Recommended model:

- `Dim_Player[PlayerKey]` one-to-many to `Fact_Player_Value[PlayerKey]`
- `Dim_Player[PlayerKey]` one-to-one or one-to-many to `Player_Pace_Adjusted[PlayerKey]`
- `Dim_Player[PlayerKey]` one-to-one or one-to-many to `Player_Shooting_Profile[PlayerKey]`
- `Dim_Team[TeamKey]` one-to-many to `Fact_Player_Value[SalaryTeam]`
- `Dim_Team[TeamKey]` one-to-many to `Team_Efficiency[TeamKey]`
- `Dim_Team[TeamKey]` one-to-one or one-to-many to `Team_Context[TeamKey]`
- `Dim_Position[Position]` one-to-many to `Fact_Player_Value[Position]`

Set relationship direction to single direction from dimension to fact.

## 4. Add Measures

Paste the measures from `docs/dax_measures.md`.

## 5. Build Report Pages

Use `docs/report_wireframe.md` for a clean 5-page report:

1. League Overview
2. Player Value Rankings
3. Shot Profile and Play Style
4. Team Payroll Efficiency
5. Contract Outliers

Import `theme/nba-contract-value-theme.json` from **View > Browse for themes** before building visuals.

## 6. Suggested Filters

Add slicers for:

- Team
- Conference
- Position group
- Qualified for value rank
- All-Star flag

For the cleanest analysis, set `QualifiedForValueRank = TRUE` on player ranking visuals.
"""

    wireframe = """# Report Wireframe

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
"""

    ui_style = """# UI Style Guide

## Visual Direction

Target feel: premium sports analytics desk. Dark, sharp, and data-first, with just enough broadcast energy to feel basketball-specific.

## Theme

Import `theme/nba-contract-value-theme.json` in Power BI:

1. Open the report.
2. Go to **View > Browse for themes**.
3. Select `theme/nba-contract-value-theme.json`.

## Layout System

- Canvas: 16:9.
- Page background: `#07111F`.
- Use a 24 px outer margin and 16 px gutters.
- Header height: 64-76 px.
- KPI row height: 104-120 px.
- Use 4 KPI cards max per page.
- Put slicers in a left rail or a compact top strip, never scattered through the canvas.

## Components

- KPI cards: dark surface, large value, small uppercase label, no heavy border.
- Tables/matrices: dark header, subtle row grid, high-contrast text.
- Scatter plots: cyan points, amber highlight for selected outliers.
- Bar charts: sort descending, show data labels only when they add clarity.
- Tooltips: include salary, value score, win shares, ORtg/DRtg, and shot-profile fields.

## Color Tokens

- Background: `#07111F`
- Surface: `#102033`
- Elevated surface: `#172A42`
- Primary text: `#F8FAFC`
- Muted text: `#A8B3C5`
- Primary accent: `#38BDF8`
- Secondary accent: `#FBBF24`
- Positive: `#22C55E`
- Negative: `#F43F5E`

## Typography

- Title: 24-30 pt, bold.
- Section headers: 13-15 pt, semibold.
- KPI values: 26-34 pt.
- Body/table text: 9-11 pt.

## Polish Checklist

- Every page has one clear analytical question.
- Every chart title explains the metric, not the chart type.
- Values are formatted: salary in `$M`, percentages as `%`, ranks as whole numbers.
- Use `QualifiedForValueRank = TRUE` on value ranking visuals.
- Avoid team-color overload. Use team filters for interaction, not page-wide color chaos.
"""

    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "README.md").write_text(readme, encoding="utf-8")
    (DOCS_OUTPUT / "dax_measures.md").write_text(dax, encoding="utf-8")
    (DOCS_OUTPUT / "powerbi_build_guide.md").write_text(build_guide, encoding="utf-8")
    (DOCS_OUTPUT / "report_wireframe.md").write_text(wireframe, encoding="utf-8")
    (DOCS_OUTPUT / "ui_style_guide.md").write_text(ui_style, encoding="utf-8")


def write_theme_assets() -> None:
    THEME_OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSETS_OUTPUT.mkdir(parents=True, exist_ok=True)

    theme = {
        "name": "NBA Contract Value Dark Court",
        "dataColors": [
            "#38BDF8",
            "#FBBF24",
            "#22C55E",
            "#F43F5E",
            "#A78BFA",
            "#FB7185",
            "#2DD4BF",
            "#F97316",
        ],
        "background": "#07111F",
        "foreground": "#F8FAFC",
        "tableAccent": "#38BDF8",
        "visualStyles": {
            "*": {
                "*": {
                    "title": [
                        {
                            "show": True,
                            "fontColor": {"solid": {"color": "#F8FAFC"}},
                            "fontSize": 12,
                            "fontFamily": "Segoe UI Semibold",
                        }
                    ],
                    "background": [
                        {
                            "show": True,
                            "color": {"solid": {"color": "#102033"}},
                            "transparency": 0,
                        }
                    ],
                    "border": [
                        {
                            "show": True,
                            "color": {"solid": {"color": "#1E3A5F"}},
                            "radius": 6,
                        }
                    ],
                    "visualHeader": [{"show": False}],
                    "legend": [
                        {
                            "labelColor": {"solid": {"color": "#A8B3C5"}},
                            "fontSize": 9,
                        }
                    ],
                    "categoryAxis": [
                        {
                            "labelColor": {"solid": {"color": "#A8B3C5"}},
                            "titleColor": {"solid": {"color": "#A8B3C5"}},
                            "gridlineColor": {"solid": {"color": "#243B55"}},
                        }
                    ],
                    "valueAxis": [
                        {
                            "labelColor": {"solid": {"color": "#A8B3C5"}},
                            "titleColor": {"solid": {"color": "#A8B3C5"}},
                            "gridlineColor": {"solid": {"color": "#243B55"}},
                        }
                    ],
                    "labels": [
                        {
                            "color": {"solid": {"color": "#F8FAFC"}},
                            "fontSize": 9,
                        }
                    ],
                }
            },
            "card": {
                "*": {
                    "labels": [
                        {
                            "color": {"solid": {"color": "#F8FAFC"}},
                            "fontSize": 28,
                            "fontFamily": "Segoe UI Semibold",
                        }
                    ],
                    "categoryLabels": [
                        {
                            "color": {"solid": {"color": "#A8B3C5"}},
                            "fontSize": 10,
                        }
                    ],
                }
            },
            "tableEx": {
                "*": {
                    "grid": [
                        {
                            "gridVertical": False,
                            "gridHorizontal": True,
                            "outlineColor": {"solid": {"color": "#243B55"}},
                        }
                    ],
                    "columnHeaders": [
                        {
                            "fontColor": {"solid": {"color": "#F8FAFC"}},
                            "backColor": {"solid": {"color": "#172A42"}},
                            "fontSize": 10,
                        }
                    ],
                    "values": [
                        {
                            "fontColor": {"solid": {"color": "#E5E7EB"}},
                            "backColorPrimary": {"solid": {"color": "#102033"}},
                            "backColorSecondary": {"solid": {"color": "#0D1A2A"}},
                            "fontSize": 9,
                        }
                    ],
                }
            },
            "slicer": {
                "*": {
                    "items": [
                        {
                            "fontColor": {"solid": {"color": "#E5E7EB"}},
                            "background": {"solid": {"color": "#102033"}},
                        }
                    ]
                }
            },
        },
        "textClasses": {
            "title": {
                "fontFace": "Segoe UI Semibold",
                "fontSize": 24,
                "color": "#F8FAFC",
            },
            "header": {
                "fontFace": "Segoe UI Semibold",
                "fontSize": 14,
                "color": "#F8FAFC",
            },
            "label": {
                "fontFace": "Segoe UI",
                "fontSize": 10,
                "color": "#A8B3C5",
            },
        },
    }
    (THEME_OUTPUT / "nba-contract-value-theme.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")

    mockup = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#07111F"/>
  <rect x="24" y="24" width="1232" height="72" rx="8" fill="#0B1623"/>
  <text x="48" y="68" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="30" font-weight="700">NBA Contract Value Analysis</text>
  <text x="1030" y="66" fill="#A8B3C5" font-family="Segoe UI, Arial" font-size="16">2025-26 Season</text>
  <rect x="24" y="116" width="214" height="580" rx="8" fill="#102033"/>
  <text x="48" y="154" fill="#FBBF24" font-family="Segoe UI, Arial" font-size="14" font-weight="700">FILTERS</text>
  <rect x="48" y="180" width="166" height="36" rx="5" fill="#172A42"/>
  <rect x="48" y="232" width="166" height="36" rx="5" fill="#172A42"/>
  <rect x="48" y="284" width="166" height="36" rx="5" fill="#172A42"/>
  <text x="64" y="204" fill="#E5E7EB" font-family="Segoe UI, Arial" font-size="13">Conference</text>
  <text x="64" y="256" fill="#E5E7EB" font-family="Segoe UI, Arial" font-size="13">Team</text>
  <text x="64" y="308" fill="#E5E7EB" font-family="Segoe UI, Arial" font-size="13">Position Group</text>
  <g>
    <rect x="262" y="116" width="226" height="104" rx="8" fill="#102033" stroke="#1E3A5F"/>
    <rect x="506" y="116" width="226" height="104" rx="8" fill="#102033" stroke="#1E3A5F"/>
    <rect x="750" y="116" width="226" height="104" rx="8" fill="#102033" stroke="#1E3A5F"/>
    <rect x="994" y="116" width="262" height="104" rx="8" fill="#102033" stroke="#1E3A5F"/>
    <text x="286" y="150" fill="#A8B3C5" font-family="Segoe UI, Arial" font-size="13">TOTAL SALARY</text>
    <text x="530" y="150" fill="#A8B3C5" font-family="Segoe UI, Arial" font-size="13">WIN SHARES</text>
    <text x="774" y="150" fill="#A8B3C5" font-family="Segoe UI, Arial" font-size="13">VALUE SCORE</text>
    <text x="1018" y="150" fill="#A8B3C5" font-family="Segoe UI, Arial" font-size="13">PAYROLL PER WIN</text>
    <text x="286" y="188" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="34" font-weight="700">$5.1B</text>
    <text x="530" y="188" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="34" font-weight="700">2,490</text>
    <text x="774" y="188" fill="#38BDF8" font-family="Segoe UI, Arial" font-size="34" font-weight="700">128.6</text>
    <text x="1018" y="188" fill="#FBBF24" font-family="Segoe UI, Arial" font-size="34" font-weight="700">$2.4M</text>
  </g>
  <rect x="262" y="244" width="578" height="298" rx="8" fill="#102033" stroke="#1E3A5F"/>
  <text x="286" y="278" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="15" font-weight="700">Salary vs Production Score</text>
  <line x1="300" y1="502" x2="806" y2="502" stroke="#243B55"/>
  <line x1="300" y1="304" x2="300" y2="502" stroke="#243B55"/>
  <circle cx="382" cy="452" r="6" fill="#38BDF8"/>
  <circle cx="510" cy="394" r="8" fill="#38BDF8"/>
  <circle cx="658" cy="342" r="10" fill="#FBBF24"/>
  <circle cx="734" cy="430" r="6" fill="#22C55E"/>
  <circle cx="450" cy="330" r="5" fill="#A78BFA"/>
  <rect x="864" y="244" width="392" height="298" rx="8" fill="#102033" stroke="#1E3A5F"/>
  <text x="888" y="278" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="15" font-weight="700">Top Teams by Value Score</text>
  <rect x="900" y="468" width="28" height="34" fill="#38BDF8"/>
  <rect x="952" y="430" width="28" height="72" fill="#38BDF8"/>
  <rect x="1004" y="382" width="28" height="120" fill="#FBBF24"/>
  <rect x="1056" y="408" width="28" height="94" fill="#38BDF8"/>
  <rect x="1108" y="352" width="28" height="150" fill="#22C55E"/>
  <rect x="1160" y="396" width="28" height="106" fill="#38BDF8"/>
  <rect x="262" y="566" width="994" height="130" rx="8" fill="#102033" stroke="#1E3A5F"/>
  <text x="286" y="600" fill="#F8FAFC" font-family="Segoe UI, Arial" font-size="15" font-weight="700">Player Value Ranking Table</text>
  <line x1="286" y1="622" x2="1230" y2="622" stroke="#243B55"/>
  <line x1="286" y1="654" x2="1230" y2="654" stroke="#243B55"/>
  <line x1="286" y1="682" x2="1230" y2="682" stroke="#243B55"/>
</svg>
"""
    (ASSETS_OUTPUT / "report_layout_mockup.svg").write_text(mockup, encoding="utf-8")


def write_csvs(tables: dict[str, pd.DataFrame]) -> None:
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    file_map = {
        "Fact_Player_Value": "fact_player_value.csv",
        "Player_Pace_Adjusted": "player_pace_adjusted.csv",
        "Player_Shooting_Profile": "player_shooting_profile.csv",
        "Team_Efficiency": "team_efficiency.csv",
        "Team_Context": "team_context.csv",
        "Dim_Player": "dim_player.csv",
        "Dim_Team": "dim_team.csv",
        "Dim_Position": "dim_position.csv",
        "Data_Dictionary": "data_dictionary.csv",
        "Measure_Catalog": "measure_catalog.csv",
        "Source_Notes": "source_notes.csv",
        "Unmatched_Salaries": "unmatched_salaries.csv",
    }
    for table_name, file_name in file_map.items():
        tables[table_name].to_csv(DATA_OUTPUT / file_name, index=False)


def write_summary(tables: dict[str, pd.DataFrame]) -> None:
    fact = tables["Fact_Player_Value"]
    team_eff = tables["Team_Efficiency"]
    summary = {
        "season": SEASON,
        "pulled_at": PULLED_AT,
        "sources": SOURCES,
        "salary_rows": int(len(fact)),
        "matched_rows": int(fact["IsMatchedToStats"].sum()),
        "unmatched_rows": int((~fact["IsMatchedToStats"]).sum()),
        "qualified_players": int(fact["QualifiedForValueRank"].sum()),
        "player_pace_adjusted_rows": int(len(tables["Player_Pace_Adjusted"])),
        "player_shooting_profile_rows": int(len(tables["Player_Shooting_Profile"])),
        "team_context_rows": int(len(tables["Team_Context"])),
        "top_value_players": fact[fact["QualifiedForValueRank"]]
        .sort_values("ValueScore", ascending=False)
        .head(10)[["PlayerName", "SalaryTeam", "ValueScore", "ValueGap"]]
        .to_dict(orient="records"),
        "top_team_value": team_eff.sort_values("ValueScore", ascending=False)
        .head(1)[["TeamName", "TeamKey", "ValueScore"]]
        .to_dict(orient="records"),
    }
    (OUTPUT / "project_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


SEASON_CONFIGS = [
    {"season": "2021-22", "year": 2022, "playoffs_available": True},
    {"season": "2022-23", "year": 2023, "playoffs_available": True},
    {"season": "2023-24", "year": 2024, "playoffs_available": True},
    {"season": "2024-25", "year": 2025, "playoffs_available": True},
    {"season": "2025-26", "year": 2026, "playoffs_available": False},
]

SALARY_CAPS = {
    "2021-22": 112_414_000,
    "2022-23": 123_655_000,
    "2023-24": 136_021_000,
    "2024-25": 140_588_000,
    "2025-26": 154_647_000,
}

SEASON_SOURCE_TEMPLATES = {
    "totals": "https://www.basketball-reference.com/leagues/NBA_{year}_totals.html",
    "per_game": "https://www.basketball-reference.com/leagues/NBA_{year}_per_game.html",
    "advanced": "https://www.basketball-reference.com/leagues/NBA_{year}_advanced.html",
    "per_poss": "https://www.basketball-reference.com/leagues/NBA_{year}_per_poss.html",
    "shooting": "https://www.basketball-reference.com/leagues/NBA_{year}_shooting.html",
    "team_summary": "https://www.basketball-reference.com/leagues/NBA_{year}.html",
    "team_ratings": "https://www.basketball-reference.com/leagues/NBA_{year}_ratings.html",
    "playoff_totals": "https://www.basketball-reference.com/playoffs/NBA_{year}_totals.html",
    "playoff_advanced": "https://www.basketball-reference.com/playoffs/NBA_{year}_advanced.html",
    "espn_salaries": "https://www.espn.com/nba/salaries/_/page/{page}/year/{year}",
}


def read_html_tables(url: str, attempts: int = 4, wait_seconds: int = 8) -> list[pd.DataFrame]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return pd.read_html(url)
        except Exception as error:  # noqa: BLE001 - pandas wraps HTTP errors inconsistently.
            last_error = error
            message = str(error)
            if "429" not in message and "timed out" not in message.lower() and attempt == attempts:
                break
            if attempt < attempts:
                time.sleep(wait_seconds * attempt)
    raise last_error if last_error else RuntimeError(f"Unable to read {url}")


def read_stat_table_v3(url: str) -> pd.DataFrame:
    df = read_html_tables(url)[0]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    return clean_numeric_columns(df, {"Player", "Team", "Tm", "Pos", "Awards", "PlayerKeyRaw"})


def read_per_possession_table_v3(url: str) -> pd.DataFrame:
    df = choose_player_total_rows(read_stat_table_v3(url))
    df = df.rename(
        columns={
            "PTS": "PTSPer100",
            "TRB": "TRBPer100",
            "AST": "ASTPer100",
            "STL": "STLPer100",
            "BLK": "BLKPer100",
            "TOV": "TOVPer100",
            "ORtg": "PlayerORtg",
            "DRtg": "PlayerDRtg",
        }
    )
    return df[
        [
            "PlayerKeyRaw",
            "PTSPer100",
            "TRBPer100",
            "ASTPer100",
            "STLPer100",
            "BLKPer100",
            "TOVPer100",
            "PlayerORtg",
            "PlayerDRtg",
        ]
    ]


def read_player_shooting_table_v3(url: str) -> pd.DataFrame:
    df = read_html_tables(url)[0]
    df.columns = [flatten_column(col) for col in df.columns]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    df = clean_numeric_columns(df, {"Player", "Team", "Pos", "Awards", "PlayerKeyRaw"})
    df = choose_player_total_rows(df)
    df = df.rename(
        columns={
            "Dist.": "AvgShotDistance",
            "% of FGA by Distance_2P": "FGA_2P_Frequency",
            "% of FGA by Distance_0-3": "FGA_0_3_Frequency",
            "% of FGA by Distance_3-10": "FGA_3_10_Frequency",
            "% of FGA by Distance_10-16": "FGA_10_16_Frequency",
            "% of FGA by Distance_16-3P": "FGA_16_3P_Frequency",
            "% of FGA by Distance_3P": "FGA_3P_Frequency",
            "FG% by Distance_2P": "FG_2P_Pct",
            "FG% by Distance_0-3": "FG_0_3_Pct",
            "FG% by Distance_3-10": "FG_3_10_Pct",
            "FG% by Distance_10-16": "FG_10_16_Pct",
            "FG% by Distance_16-3P": "FG_16_3P_Pct",
            "FG% by Distance_3P": "FG_3P_Pct",
            "% of FG Ast'd_2P": "Assisted2P_Pct",
            "% of FG Ast'd_3P": "Assisted3P_Pct",
            "Dunks_%FGA": "Dunk_FGA_Pct",
            "Dunks_#": "DunksMade",
            "Corner 3s_%3PA": "Corner3_Frequency",
            "Corner 3s_3P%": "Corner3Pct",
            "1/2 Court_Att.": "HalfCourtAttempts",
            "1/2 Court_Md.": "HalfCourtMakes",
        }
    )
    return df[
        [
            "PlayerKeyRaw",
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
            "DunksMade",
            "Corner3_Frequency",
            "Corner3Pct",
            "HalfCourtAttempts",
            "HalfCourtMakes",
        ]
    ]


def prep_team_table_v3(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [flatten_column(col) for col in df.columns]
    df = df[df["Team"].astype(str) != "Team"].copy()
    df["TeamName"] = df["Team"].map(normalize_team_name)
    df["TeamKey"] = df["TeamName"].map(TEAM_NAME_TO_KEY)
    df = df.dropna(subset=["TeamKey"])
    return clean_numeric_columns(df, {"Team", "TeamName", "TeamKey", "Conf", "Div", "Arena"})


def read_team_context_v3(season: str, year: int) -> pd.DataFrame:
    summary_url = SEASON_SOURCE_TEMPLATES["team_summary"].format(year=year)
    ratings_url = SEASON_SOURCE_TEMPLATES["team_ratings"].format(year=year)
    ratings = prep_team_table_v3(read_html_tables(ratings_url)[0]).rename(
        columns={
            "W/L%": "WinPct",
            "Unadjusted_MOV": "MOV",
            "Unadjusted_ORtg": "UnadjustedORtg",
            "Unadjusted_DRtg": "UnadjustedDRtg",
            "Unadjusted_NRtg": "UnadjustedNetRtg",
            "Adjusted_MOV/A": "AdjustedMOV",
            "Adjusted_ORtg/A": "AdjustedORtg",
            "Adjusted_DRtg/A": "AdjustedDRtg",
            "Adjusted_NRtg/A": "AdjustedNetRtg",
        }
    )
    summary_tables = read_html_tables(summary_url)
    advanced = prep_team_table_v3(summary_tables[10]).rename(
        columns={
            "Age": "AvgAge",
            "PW": "PythagoreanWins",
            "PL": "PythagoreanLosses",
            "SOS": "StrengthOfSchedule",
            "FTr": "FreeThrowRate",
            "3PAr": "ThreePointAttemptRate",
            "TS%": "TrueShootingPct",
            "Offense Four Factors_eFG%": "Off_eFGPct",
            "Offense Four Factors_TOV%": "Off_TOVPct",
            "Offense Four Factors_ORB%": "Off_ORBPct",
            "Offense Four Factors_FT/FGA": "Off_FTPerFGA",
            "Defense Four Factors_eFG%": "Def_eFGPct",
            "Defense Four Factors_TOV%": "Def_TOVPct",
            "Defense Four Factors_DRB%": "Def_DRBPct",
            "Defense Four Factors_FT/FGA": "Def_FTPerFGA",
            "Attend.": "Attendance",
            "Attend./G": "AttendancePerGame",
        }
    )
    team_shooting = prep_team_table_v3(summary_tables[11]).rename(
        columns={
            "Dist.": "TeamAvgShotDistance",
            "% of FGA by Distance_0-3": "TeamRimFrequency",
            "% of FGA by Distance_3P": "Team3P_Frequency",
            "FG% by Distance_0-3": "TeamRimFGPct",
            "FG% by Distance_3P": "Team3P_Pct",
            "Dunks_%FGA": "TeamDunk_FGA_Pct",
            "Layups_%FGA": "TeamLayup_FGA_Pct",
            "Corner_%3PA": "TeamCorner3_Frequency",
            "Corner_3P%": "TeamCorner3Pct",
        }
    )
    opponent_shooting = prep_team_table_v3(summary_tables[12]).rename(
        columns={
            "Dist.": "OppAvgShotDistance",
            "% of FGA by Distance_0-3": "OppRimFrequency",
            "% of FGA by Distance_3P": "Opp3P_Frequency",
            "FG% by Distance_0-3": "OppRimFGPct",
            "FG% by Distance_3P": "Opp3P_Pct",
            "Dunks_%FGA": "OppDunk_FGA_Pct",
            "Layups_%FGA": "OppLayup_FGA_Pct",
            "Corner_%3PA": "OppCorner3_Frequency",
            "Corner_3P%": "OppCorner3Pct",
        }
    )
    context = (
        ratings[
            [
                "TeamKey",
                "TeamName",
                "Conf",
                "Div",
                "W",
                "L",
                "WinPct",
                "MOV",
                "UnadjustedORtg",
                "UnadjustedDRtg",
                "UnadjustedNetRtg",
                "AdjustedMOV",
                "AdjustedORtg",
                "AdjustedDRtg",
                "AdjustedNetRtg",
            ]
        ]
        .merge(
            advanced[
                [
                    "TeamKey",
                    "AvgAge",
                    "PythagoreanWins",
                    "PythagoreanLosses",
                    "StrengthOfSchedule",
                    "SRS",
                    "Pace",
                    "FreeThrowRate",
                    "ThreePointAttemptRate",
                    "TrueShootingPct",
                    "Off_eFGPct",
                    "Off_TOVPct",
                    "Off_ORBPct",
                    "Off_FTPerFGA",
                    "Def_eFGPct",
                    "Def_TOVPct",
                    "Def_DRBPct",
                    "Def_FTPerFGA",
                    "Arena",
                    "Attendance",
                    "AttendancePerGame",
                ]
            ],
            on="TeamKey",
            how="left",
        )
        .merge(
            team_shooting[
                [
                    "TeamKey",
                    "TeamAvgShotDistance",
                    "TeamRimFrequency",
                    "Team3P_Frequency",
                    "TeamRimFGPct",
                    "Team3P_Pct",
                    "TeamDunk_FGA_Pct",
                    "TeamLayup_FGA_Pct",
                    "TeamCorner3_Frequency",
                    "TeamCorner3Pct",
                ]
            ],
            on="TeamKey",
            how="left",
        )
        .merge(
            opponent_shooting[
                [
                    "TeamKey",
                    "OppAvgShotDistance",
                    "OppRimFrequency",
                    "Opp3P_Frequency",
                    "OppRimFGPct",
                    "Opp3P_Pct",
                    "OppDunk_FGA_Pct",
                    "OppLayup_FGA_Pct",
                    "OppCorner3_Frequency",
                    "OppCorner3Pct",
                ]
            ],
            on="TeamKey",
            how="left",
        )
    )
    context.insert(0, "SeasonEndYear", year)
    context.insert(0, "Season", season)
    return context.sort_values(["SeasonEndYear", "AdjustedNetRtg"], ascending=[True, False]).reset_index(drop=True)


def parse_espn_name(value: object) -> tuple[str, str]:
    text = "" if pd.isna(value) else str(value).strip()
    if ", " in text:
        name, position = text.rsplit(", ", 1)
        return name.strip(), position.strip()
    return text, ""


def read_espn_salary_season(season: str, year: int, max_pages: int = 20) -> pd.DataFrame:
    rows = []
    for page in range(1, max_pages + 1):
        url = SEASON_SOURCE_TEMPLATES["espn_salaries"].format(page=page, year=year)
        table = read_html_tables(url, attempts=3, wait_seconds=4)[0]
        if table.empty or len(table) <= 1:
            break
        data = table.iloc[1:].copy()
        data.columns = ["SalaryRank", "NamePosition", "SalaryTeamName", "Salary"]
        data = data.dropna(subset=["NamePosition"])
        if data.empty:
            break
        data[["SalaryPlayer", "SalaryPosition"]] = data["NamePosition"].apply(
            lambda value: pd.Series(parse_espn_name(value))
        )
        data["Season"] = season
        data["SeasonEndYear"] = year
        data["PlayerKeyRaw"] = data["SalaryPlayer"].map(normalize_name)
        data["SalaryTeamName"] = data["SalaryTeamName"].map(normalize_team_name)
        data["SalaryTeam"] = data["SalaryTeamName"].map(TEAM_NAME_TO_KEY)
        data["Salary"] = data["Salary"].map(parse_money)
        data["SalaryRank"] = pd.to_numeric(data["SalaryRank"], errors="coerce")
        data["SalarySource"] = "ESPN NBA salaries"
        rows.append(
            data[
                [
                    "Season",
                    "SeasonEndYear",
                    "PlayerKeyRaw",
                    "SalaryPlayer",
                    "SalaryPosition",
                    "SalaryTeamName",
                    "SalaryTeam",
                    "Salary",
                    "SalaryRank",
                    "SalarySource",
                ]
            ]
        )
        if len(data) < 40:
            break
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame(
            columns=[
                "Season",
                "SeasonEndYear",
                "PlayerKeyRaw",
                "SalaryPlayer",
                "SalaryPosition",
                "SalaryTeamName",
                "SalaryTeam",
                "Salary",
                "SalaryRank",
                "SalarySource",
            ]
        )
    salaries = pd.concat(rows, ignore_index=True)
    salaries = salaries.sort_values(["SeasonEndYear", "SalaryRank"]).drop_duplicates(
        ["Season", "PlayerKeyRaw"], keep="first"
    )
    return salaries.reset_index(drop=True)


ESPN_ABBREV_TO_TEAM = {
    "ATL": "ATL",
    "BKN": "BRK",
    "BOS": "BOS",
    "CHA": "CHO",
    "CHI": "CHI",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GS": "GSW",
    "HOU": "HOU",
    "IND": "IND",
    "LAC": "LAC",
    "LAL": "LAL",
    "MEM": "MEM",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NO": "NOP",
    "NY": "NYK",
    "OKC": "OKC",
    "ORL": "ORL",
    "PHI": "PHI",
    "PHX": "PHO",
    "POR": "POR",
    "SAC": "SAC",
    "SA": "SAS",
    "TOR": "TOR",
    "UTAH": "UTA",
    "WSH": "WAS",
}

ESPN_ABBREV_PATTERN = "|".join(sorted(ESPN_ABBREV_TO_TEAM, key=len, reverse=True))


def parse_espn_player_team(value: object) -> tuple[str, str, str]:
    text = "" if pd.isna(value) else str(value).strip()
    pattern = rf"((?:{ESPN_ABBREV_PATTERN})(?:/(?:{ESPN_ABBREV_PATTERN}))*)$"
    match = re.search(pattern, text)
    if not match:
        return text, "", ""
    raw_team = match.group(1)
    player = text[: match.start()].strip()
    team_parts = raw_team.split("/")
    mapped = [ESPN_ABBREV_TO_TEAM.get(part, part) for part in team_parts]
    return player, raw_team, mapped[-1]


def read_espn_player_stats(season: str, year: int, season_type: int = 2, max_pages: int = 20) -> pd.DataFrame:
    rows = []
    for page in range(1, max_pages + 1):
        url = (
            "https://www.espn.com/nba/stats/player/_/"
            f"season/{year}/seasontype/{season_type}/table/offensive/sort/avgPoints/dir/desc/page/{page}"
        )
        tables = read_html_tables(url, attempts=3, wait_seconds=4)
        if len(tables) < 2 or tables[0].empty:
            break
        names = tables[0].copy().reset_index(drop=True)
        stats = tables[1].copy().reset_index(drop=True)
        if names.empty or stats.empty:
            break
        page_df = pd.concat([names, stats], axis=1)
        page_df[["PlayerName", "StatsTeamRaw", "StatsTeam"]] = page_df["Name"].apply(
            lambda value: pd.Series(parse_espn_player_team(value))
        )
        page_df["Season"] = season
        page_df["SeasonEndYear"] = year
        rows.append(page_df)
        if len(page_df) < 50:
            break
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True)
    df["PlayerKeyRaw"] = df["PlayerName"].map(normalize_name)
    numeric_cols = [
        "GP",
        "MIN",
        "PTS",
        "FGM",
        "FGA",
        "FG%",
        "3PM",
        "3PA",
        "3P%",
        "FTM",
        "FTA",
        "FT%",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TO",
        "DD2",
        "TD3",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.drop_duplicates(["Season", "PlayerKeyRaw"], keep="first").reset_index(drop=True)


def espn_regular_to_fact(stats: pd.DataFrame) -> pd.DataFrame:
    df = stats.copy()
    games = df["GP"].fillna(0)
    df["Player"] = df["PlayerName"]
    df["Age"] = np.nan
    df["Pos"] = df["POS"].map(first_position)
    df["G"] = df["GP"]
    df["GS"] = np.nan
    df["MPG"] = df["MIN"]
    df["TotalMinutes"] = df["MIN"] * games
    df["FG"] = df["FGM"] * games
    df["FGA"] = df["FGA"] * games
    df["3P"] = df["3PM"] * games
    df["3PA"] = df["3PA"] * games
    df["2P"] = df["FG"] - df["3P"]
    df["2PA"] = df["FGA"] - df["3PA"]
    df["FT"] = df["FTM"] * games
    df["TotalRebounds"] = df["REB"] * games
    df["TotalAssists"] = df["AST"] * games
    df["TotalSteals"] = df["STL"] * games
    df["TotalBlocks"] = df["BLK"] * games
    df["TotalTurnovers"] = df["TO"] * games
    df["TotalPoints"] = df["PTS"] * games
    df["PPG"] = df["PTS"]
    df["RPG"] = df["REB"]
    df["APG"] = df["AST"]
    df["SPG"] = df["STL"]
    df["BPG"] = df["BLK"]
    df["TPG"] = df["TO"]
    df["FG%"] = df["FG%"] / 100
    df["3P%"] = df["3P%"] / 100
    df["FT%"] = df["FT%"] / 100
    df["2P%"] = safe_divide(df["2P"], df["2PA"])
    df["eFG%"] = safe_divide(df["FG"] + 0.5 * df["3P"], df["FGA"])
    df["FTA"] = df["FTA"] * games
    df["TS_Pct"] = safe_divide(df["TotalPoints"], 2 * (df["FGA"] + 0.44 * df["FTA"]))
    df["PER"] = np.nan
    df["USG_Pct"] = np.nan
    df["WS"] = np.nan
    df["WS/48"] = np.nan
    df["BPM"] = np.nan
    df["VORP"] = np.nan
    df["PF"] = np.nan
    df["ORB"] = np.nan
    df["DRB"] = np.nan
    df["Awards"] = np.nan
    df["Trp-Dbl"] = df["TD3"]
    return df


def espn_rate_stats(stats: pd.DataFrame) -> pd.DataFrame:
    df = stats.copy()
    minutes = df["MIN"].replace(0, np.nan)
    rate = pd.DataFrame(
        {
            "Season": df["Season"],
            "SeasonEndYear": df["SeasonEndYear"],
            "PlayerKeyRaw": df["PlayerKeyRaw"],
            "PTSPer36": df["PTS"] / minutes * 36,
            "TRBPer36": df["REB"] / minutes * 36,
            "ASTPer36": df["AST"] / minutes * 36,
            "STLPer36": df["STL"] / minutes * 36,
            "BLKPer36": df["BLK"] / minutes * 36,
            "TOVPer36": df["TO"] / minutes * 36,
        }
    )
    rate["BoxScoreRateScorePer36"] = (
        rate["PTSPer36"].fillna(0)
        + 1.2 * rate["TRBPer36"].fillna(0)
        + 1.5 * rate["ASTPer36"].fillna(0)
        + 3 * rate["STLPer36"].fillna(0)
        + 3 * rate["BLKPer36"].fillna(0)
        - rate["TOVPer36"].fillna(0)
    )
    return rate


def espn_shooting_profile(stats: pd.DataFrame) -> pd.DataFrame:
    df = espn_regular_to_fact(stats)
    return pd.DataFrame(
        {
            "Season": df["Season"],
            "SeasonEndYear": df["SeasonEndYear"],
            "PlayerKeyRaw": df["PlayerKeyRaw"],
            "FGA_3P_Frequency": safe_divide(df["3PA"], df["FGA"]),
            "FreeThrowRate": safe_divide(df["FTA"], df["FGA"]),
            "FG_Pct": df["FG%"],
            "FG_3P_Pct": df["3P%"],
            "FT_Pct": df["FT%"],
            "eFG_Pct": df["eFG%"],
            "TS_Pct": df["TS_Pct"],
            "DoubleDoubles": df["DD2"],
            "TripleDoubles": df["TD3"],
        }
    )


def read_espn_standings(season: str, year: int) -> pd.DataFrame:
    url = f"https://www.espn.com/nba/standings/_/season/{year}/group/league"
    tables = read_html_tables(url, attempts=3, wait_seconds=4)
    names_table = tables[0]
    stats_table = tables[1].copy()
    team_strings = [str(names_table.columns[0])] + names_table.iloc[:, 0].dropna().astype(str).tolist()
    team_rows = []
    for raw in team_strings[: len(stats_table)]:
        after_marker = raw.split("--", 1)[-1]
        espn_key = ""
        team_name = normalize_team_name(after_marker)
        for candidate in sorted(ESPN_ABBREV_TO_TEAM, key=len, reverse=True):
            if after_marker.startswith(candidate):
                espn_key = candidate
                team_name = normalize_team_name(after_marker[len(candidate) :])
                break
        team_rows.append({"TeamRaw": raw, "EspnTeamKey": espn_key, "TeamKey": ESPN_ABBREV_TO_TEAM.get(espn_key), "TeamName": team_name})
    teams = pd.DataFrame(team_rows)
    standings = pd.concat([teams.reset_index(drop=True), stats_table.reset_index(drop=True)], axis=1)
    standings.insert(0, "SeasonEndYear", year)
    standings.insert(0, "Season", season)
    standings = standings.rename(columns={"PCT": "WinPct", "PPG": "PointsPerGame", "OPP PPG": "OpponentPointsPerGame", "DIFF": "NetPointDiff"})
    for col in ["W", "L", "WinPct", "PointsPerGame", "OpponentPointsPerGame", "NetPointDiff"]:
        standings[col] = pd.to_numeric(standings[col], errors="coerce")
    return standings.dropna(subset=["TeamKey"]).reset_index(drop=True)


def read_espn_playoff_table(season: str, year: int) -> pd.DataFrame:
    stats = read_espn_player_stats(season, year, season_type=3, max_pages=12)
    if stats.empty:
        return pd.DataFrame()
    regular = espn_regular_to_fact(stats)
    playoff = regular.rename(
        columns={
            "StatsTeam": "PlayoffTeam",
            "G": "PlayoffGames",
            "GS": "PlayoffGamesStarted",
            "TotalMinutes": "PlayoffMinutes",
            "TotalPoints": "PlayoffPoints",
            "TotalRebounds": "PlayoffRebounds",
            "TotalAssists": "PlayoffAssists",
            "TotalSteals": "PlayoffSteals",
            "TotalBlocks": "PlayoffBlocks",
            "TotalTurnovers": "PlayoffTurnovers",
            "TS_Pct": "PlayoffTS_Pct",
        }
    )
    playoff["PlayoffProductionScore"] = (
        playoff["PlayoffPoints"].fillna(0)
        + 1.2 * playoff["PlayoffRebounds"].fillna(0)
        + 1.5 * playoff["PlayoffAssists"].fillna(0)
        + 3.0 * playoff["PlayoffSteals"].fillna(0)
        + 3.0 * playoff["PlayoffBlocks"].fillna(0)
        - playoff["PlayoffTurnovers"].fillna(0)
    )
    playoff["PlayoffEstimatedWinShares"] = playoff["PlayoffProductionScore"] / 300
    return playoff[
        [
            "Season",
            "SeasonEndYear",
            "PlayerKeyRaw",
            "PlayerName",
            "PlayoffTeam",
            "Pos",
            "PlayoffGames",
            "PlayoffGamesStarted",
            "PlayoffMinutes",
            "PlayoffPoints",
            "PlayoffRebounds",
            "PlayoffAssists",
            "PlayoffSteals",
            "PlayoffBlocks",
            "PlayoffTurnovers",
            "PlayoffTS_Pct",
            "PlayoffProductionScore",
            "PlayoffEstimatedWinShares",
        ]
    ]


def contract_tier(row: pd.Series) -> str:
    salary = row.get("Salary")
    cap = row.get("SalaryCap")
    age = row.get("Age")
    if pd.isna(salary) or pd.isna(cap) or cap == 0:
        return "Salary Unavailable"
    salary_pct = salary / cap
    if salary_pct >= 0.30:
        return "Max / Supermax-Level"
    if pd.notna(age) and age <= 24 and salary_pct <= 0.12:
        return "Likely Rookie-Scale / Early Career"
    if salary_pct >= 0.18:
        return "High-Salary Starter"
    if salary_pct >= 0.08:
        return "Mid-Tier Rotation Contract"
    if salary_pct >= 0.03:
        return "Low-Cost Rotation Contract"
    return "Minimum / Two-Way / Replacement"


def value_tier(row: pd.Series) -> str:
    if not row.get("SalaryAvailable", False):
        return "Salary Unavailable"
    salary_pctile = row.get("SalaryPercentile")
    production_pctile = row.get("ProductionPercentile")
    value_pctile = row.get("ValuePercentile")
    age = row.get("Age")
    salary_cap_pct = row.get("SalaryCapPct")
    if pd.isna(value_pctile) or pd.isna(production_pctile):
        return "Insufficient Minutes / Context"
    if production_pctile >= 0.85 and value_pctile >= 0.70:
        return "Bargain Star"
    if production_pctile >= 0.85 and salary_pctile >= 0.70:
        return "Expensive but Worth It"
    if salary_pctile >= 0.70 and value_pctile <= 0.30:
        return "High-Cost Low-Return"
    if value_pctile >= 0.75 and production_pctile < 0.85:
        return "Efficient Role Player"
    if pd.notna(age) and age <= 24 and pd.notna(salary_cap_pct) and salary_cap_pct <= 0.10:
        return "Development Bet"
    return "Market Neutral"


def prediction_tier(value: object) -> str:
    if pd.isna(value):
        return "No Salary Baseline"
    value = float(value)
    if value >= 900:
        return "Projected Bargain"
    if value >= 500:
        return "Projected Positive Value"
    if value >= 250:
        return "Projected Neutral Value"
    return "Projected Value Risk"


def build_regular_stats_for_season(season: str, year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    totals = choose_player_total_rows(read_stat_table_v3(SEASON_SOURCE_TEMPLATES["totals"].format(year=year)))
    per_game = choose_player_total_rows(read_stat_table_v3(SEASON_SOURCE_TEMPLATES["per_game"].format(year=year)))
    advanced = choose_player_total_rows(read_stat_table_v3(SEASON_SOURCE_TEMPLATES["advanced"].format(year=year)))
    per_poss = read_per_possession_table_v3(SEASON_SOURCE_TEMPLATES["per_poss"].format(year=year))
    shooting = read_player_shooting_table_v3(SEASON_SOURCE_TEMPLATES["shooting"].format(year=year))

    totals = totals.rename(
        columns={
            "Team": "StatsTeam",
            "PTS": "TotalPoints",
            "TRB": "TotalRebounds",
            "AST": "TotalAssists",
            "STL": "TotalSteals",
            "BLK": "TotalBlocks",
            "TOV": "TotalTurnovers",
            "MP": "TotalMinutes",
        }
    )
    per_game = per_game.rename(
        columns={
            "PTS": "PPG",
            "TRB": "RPG",
            "AST": "APG",
            "STL": "SPG",
            "BLK": "BPG",
            "TOV": "TPG",
            "MP": "MPG",
        }
    )
    advanced = advanced.rename(
        columns={
            "TS%": "TS_Pct",
            "USG%": "USG_Pct",
            "TRB%": "TRB_Pct",
            "AST%": "AST_Pct",
            "STL%": "STL_Pct",
            "BLK%": "BLK_Pct",
            "TOV%": "TOV_Pct",
        }
    )

    total_cols = [
        "PlayerKeyRaw",
        "Player",
        "Age",
        "StatsTeam",
        "Pos",
        "G",
        "GS",
        "TotalMinutes",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "3P%",
        "2P",
        "2PA",
        "2P%",
        "eFG%",
        "FT",
        "FTA",
        "FT%",
        "ORB",
        "DRB",
        "TotalRebounds",
        "TotalAssists",
        "TotalSteals",
        "TotalBlocks",
        "TotalTurnovers",
        "PF",
        "TotalPoints",
        "Trp-Dbl",
        "Awards",
    ]
    per_game_cols = ["PlayerKeyRaw", "MPG", "PPG", "RPG", "APG", "SPG", "BPG", "TPG"]
    advanced_cols = [
        "PlayerKeyRaw",
        "PER",
        "TS_Pct",
        "USG_Pct",
        "TRB_Pct",
        "AST_Pct",
        "STL_Pct",
        "BLK_Pct",
        "TOV_Pct",
        "OWS",
        "DWS",
        "WS",
        "WS/48",
        "OBPM",
        "DBPM",
        "BPM",
        "VORP",
    ]
    stats = (
        totals[total_cols]
        .merge(per_game[per_game_cols], on="PlayerKeyRaw", how="left")
        .merge(advanced[advanced_cols], on="PlayerKeyRaw", how="left")
    )
    stats.insert(0, "SeasonEndYear", year)
    stats.insert(0, "Season", season)
    per_poss.insert(0, "SeasonEndYear", year)
    per_poss.insert(0, "Season", season)
    shooting.insert(0, "SeasonEndYear", year)
    shooting.insert(0, "Season", season)
    return stats, per_poss, shooting


def add_player_keys(
    fact: pd.DataFrame,
    per_poss: pd.DataFrame,
    shooting: pd.DataFrame,
    playoffs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    player_names = (
        fact.sort_values(["SeasonEndYear", "TotalMinutes"], ascending=[False, False])
        .drop_duplicates("PlayerKeyRaw")[["PlayerKeyRaw", "PlayerName"]]
        .sort_values("PlayerName")
        .reset_index(drop=True)
    )
    player_names["PlayerKey"] = ["P" + str(i + 1).zfill(5) for i in range(len(player_names))]
    key_map = player_names[["PlayerKeyRaw", "PlayerKey"]]
    fact = fact.merge(key_map, on="PlayerKeyRaw", how="left")
    fact["PlayerSeasonKey"] = fact["PlayerKey"] + "-" + fact["SeasonEndYear"].astype(str)

    for frame in [per_poss, shooting, playoffs]:
        if not frame.empty:
            frame.drop(columns=[col for col in ["PlayerKey", "PlayerSeasonKey"] if col in frame.columns], inplace=True)
            frame["PlayerKeyRaw"] = frame["PlayerKeyRaw"].map(normalize_name)
            frame_tmp = frame.merge(key_map, on="PlayerKeyRaw", how="left")
            frame_tmp["PlayerSeasonKey"] = frame_tmp["PlayerKey"] + "-" + frame_tmp["SeasonEndYear"].astype(str)
            frame.drop(frame.index, inplace=True)
            for column in frame_tmp.columns:
                frame[column] = frame_tmp[column]

    dim_player = fact[
        [
            "PlayerKey",
            "PlayerName",
            "Position",
            "PositionGroup",
            "Awards",
        ]
    ].copy()
    dim_player = (
        dim_player.sort_values("PlayerName")
        .groupby("PlayerKey", as_index=False)
        .agg(
            PlayerName=("PlayerName", "first"),
            PrimaryPosition=("Position", lambda values: values.mode().iat[0] if not values.mode().empty else "Unknown"),
            PrimaryPositionGroup=("PositionGroup", lambda values: values.mode().iat[0] if not values.mode().empty else "Unknown"),
            Awards=("Awards", lambda values: ",".join(sorted(set(v for v in values.dropna().astype(str) if v)))),
        )
    )
    dim_player["EverAllStarInDataset"] = dim_player["Awards"].fillna("").str.contains(r"\bAS\b", regex=True)
    return fact, per_poss, shooting, playoffs, dim_player


def calculate_value_metrics(fact: pd.DataFrame) -> pd.DataFrame:
    fact = fact.copy()
    fact["SalaryCap"] = fact["Season"].map(SALARY_CAPS)
    fact["SalaryAvailable"] = fact["Salary"].notna()
    fact["SalaryMillions"] = fact["Salary"] / 1_000_000
    fact["SalaryCapPct"] = safe_divide(fact["Salary"], fact["SalaryCap"])
    fact["ProductionScore"] = (
        fact["TotalPoints"].fillna(0)
        + 1.2 * fact["TotalRebounds"].fillna(0)
        + 1.5 * fact["TotalAssists"].fillna(0)
        + 3.0 * fact["TotalSteals"].fillna(0)
        + 3.0 * fact["TotalBlocks"].fillna(0)
        - fact["TotalTurnovers"].fillna(0)
    )
    fact["EstimatedWinShares"] = fact["ProductionScore"] / 300
    if "WS" not in fact.columns:
        fact["WS"] = fact["EstimatedWinShares"]
    else:
        fact["WS"] = fact["WS"].fillna(fact["EstimatedWinShares"])
    fact["CostPerPoint"] = safe_divide(fact["Salary"], fact["TotalPoints"])
    fact["CostPerEstimatedWinShare"] = safe_divide(
        fact["Salary"], fact["EstimatedWinShares"].where(fact["EstimatedWinShares"] > 0)
    )
    fact["CostPerWinShare"] = fact["CostPerEstimatedWinShare"]
    fact["PointsPerMillion"] = safe_divide(fact["TotalPoints"], fact["SalaryMillions"])
    fact["EstimatedWinSharesPerMillion"] = safe_divide(fact["EstimatedWinShares"], fact["SalaryMillions"])
    fact["WinSharesPerMillion"] = fact["EstimatedWinSharesPerMillion"]
    fact["ValueScore"] = safe_divide(fact["ProductionScore"], fact["SalaryMillions"])
    fact["QualifiedForValueRank"] = (
        (fact["G"].fillna(0) >= 20)
        & (fact["TotalMinutes"].fillna(0) >= 500)
        & (fact["Salary"].fillna(0) > 0)
    )
    fact["ContractTier"] = fact.apply(contract_tier, axis=1)
    fact["SalaryMissingReason"] = np.where(
        fact["SalaryAvailable"], "", "No matching ESPN salary row for this player-season"
    )

    fact["ProductionPercentile"] = np.nan
    fact["SalaryPercentile"] = np.nan
    fact["ValuePercentile"] = np.nan
    fact["SalaryRank"] = np.nan
    fact["ProductionRank"] = np.nan
    fact["ValueRank"] = np.nan
    for season, idx in fact.groupby("Season").groups.items():
        season_rows = fact.loc[idx]
        qualified = season_rows["QualifiedForValueRank"]
        qidx = season_rows[qualified].index
        fact.loc[qidx, "ProductionPercentile"] = season_rows.loc[qidx, "ProductionScore"].rank(pct=True)
        fact.loc[qidx, "SalaryPercentile"] = season_rows.loc[qidx, "Salary"].rank(pct=True)
        fact.loc[qidx, "ValuePercentile"] = season_rows.loc[qidx, "ValueScore"].rank(pct=True)
        fact.loc[qidx, "SalaryRank"] = season_rows.loc[qidx, "Salary"].rank(method="dense", ascending=False)
        fact.loc[qidx, "ProductionRank"] = season_rows.loc[qidx, "ProductionScore"].rank(
            method="dense", ascending=False
        )
        fact.loc[qidx, "ValueRank"] = season_rows.loc[qidx, "ValueScore"].rank(method="dense", ascending=False)
    fact["ValueGap"] = fact["SalaryRank"] - fact["ProductionRank"]
    fact["PlayerValueTier"] = fact.apply(value_tier, axis=1)
    fact["IsAllStar"] = fact["Awards"].fillna("").str.contains(r"\bAS\b", regex=True)
    return fact


def build_team_efficiency(fact: pd.DataFrame, team_context: pd.DataFrame, dim_team: pd.DataFrame) -> pd.DataFrame:
    team_fact = fact.copy()
    team_fact["TeamKey"] = team_fact["SalaryTeam"].fillna(team_fact["StatsTeam"])
    team_eff = (
        team_fact.groupby(["Season", "SeasonEndYear", "TeamKey"], dropna=False)
        .agg(
            Payroll=("Salary", "sum"),
            SalaryCoveredPlayers=("SalaryAvailable", "sum"),
            PlayerSeasonCount=("PlayerSeasonKey", "nunique"),
            QualifiedPlayers=("QualifiedForValueRank", "sum"),
            TotalPoints=("TotalPoints", "sum"),
            TotalRebounds=("TotalRebounds", "sum"),
            TotalAssists=("TotalAssists", "sum"),
            TotalEstimatedWinShares=("EstimatedWinShares", "sum"),
            ProductionScore=("ProductionScore", "sum"),
        )
        .reset_index()
    )
    team_eff["PayrollMillions"] = team_eff["Payroll"] / 1_000_000
    team_eff["SalaryCoveragePct"] = safe_divide(team_eff["SalaryCoveredPlayers"], team_eff["PlayerSeasonCount"])
    team_eff["CostPerPoint"] = safe_divide(team_eff["Payroll"], team_eff["TotalPoints"])
    team_eff["CostPerEstimatedWinShare"] = safe_divide(
        team_eff["Payroll"], team_eff["TotalEstimatedWinShares"].where(team_eff["TotalEstimatedWinShares"] > 0)
    )
    team_eff["PointsPerMillion"] = safe_divide(team_eff["TotalPoints"], team_eff["PayrollMillions"])
    team_eff["EstimatedWinSharesPerMillion"] = safe_divide(
        team_eff["TotalEstimatedWinShares"], team_eff["PayrollMillions"]
    )
    team_eff["ValueScore"] = safe_divide(team_eff["ProductionScore"], team_eff["PayrollMillions"])
    team_eff = team_eff.merge(dim_team, on="TeamKey", how="left")
    team_eff = team_eff.merge(
        team_context[
            [
                "Season",
                "TeamKey",
                "W",
                "L",
                "WinPct",
                "Pace",
                "AdjustedORtg",
                "AdjustedDRtg",
                "AdjustedNetRtg",
                "Team3P_Frequency",
                "TeamRimFrequency",
            ]
        ],
        on=["Season", "TeamKey"],
        how="left",
    )
    team_eff["PayrollPerWin"] = safe_divide(team_eff["Payroll"], team_eff["W"])
    return team_eff.sort_values(["SeasonEndYear", "ValueScore"], ascending=[True, False])


def build_team_payroll_allocation(fact: pd.DataFrame, dim_team: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (season, year, team_key), group in fact.assign(TeamKey=fact["SalaryTeam"].fillna(fact["StatsTeam"])).groupby(
        ["Season", "SeasonEndYear", "TeamKey"], dropna=False
    ):
        salary_group = group.dropna(subset=["Salary"]).sort_values("Salary", ascending=False)
        payroll = salary_group["Salary"].sum()
        if payroll <= 0:
            continue
        shares = {}
        for n in [1, 3, 5]:
            shares[f"Top{n}SalaryShare"] = salary_group.head(n)["Salary"].sum() / payroll
        position_pay = salary_group.groupby("PositionGroup")["Salary"].sum()
        rows.append(
            {
                "Season": season,
                "SeasonEndYear": year,
                "TeamKey": team_key,
                "Payroll": payroll,
                "PayrollMillions": payroll / 1_000_000,
                "SalaryCoveredPlayers": int(len(salary_group)),
                "MedianSalary": salary_group["Salary"].median(),
                "Top1SalaryShare": shares["Top1SalaryShare"],
                "Top3SalaryShare": shares["Top3SalaryShare"],
                "Top5SalaryShare": shares["Top5SalaryShare"],
                "GuardSalaryShare": position_pay.get("Guard", 0) / payroll,
                "WingSalaryShare": position_pay.get("Wing", 0) / payroll,
                "ForwardSalaryShare": position_pay.get("Forward", 0) / payroll,
                "CenterSalaryShare": position_pay.get("Center", 0) / payroll,
                "MaxTierPlayers": int((salary_group["ContractTier"] == "Max / Supermax-Level").sum()),
                "RookieEarlyCareerPlayers": int(
                    (salary_group["ContractTier"] == "Likely Rookie-Scale / Early Career").sum()
                ),
            }
        )
    allocation = pd.DataFrame(rows)
    if allocation.empty:
        return allocation
    return allocation.merge(dim_team, on="TeamKey", how="left").sort_values(["SeasonEndYear", "Payroll"], ascending=[True, False])


def read_playoff_table(season: str, year: int) -> pd.DataFrame:
    totals_url = SEASON_SOURCE_TEMPLATES["playoff_totals"].format(year=year)
    advanced_url = SEASON_SOURCE_TEMPLATES["playoff_advanced"].format(year=year)
    try:
        totals = choose_player_total_rows(read_stat_table_v3(totals_url))
        advanced = choose_player_total_rows(read_stat_table_v3(advanced_url))
    except Exception:
        return pd.DataFrame()
    totals = totals.rename(
        columns={
            "Team": "PlayoffTeam",
            "PTS": "PlayoffPoints",
            "TRB": "PlayoffRebounds",
            "AST": "PlayoffAssists",
            "STL": "PlayoffSteals",
            "BLK": "PlayoffBlocks",
            "TOV": "PlayoffTurnovers",
            "MP": "PlayoffMinutes",
        }
    )
    advanced = advanced.rename(
        columns={
            "TS%": "PlayoffTS_Pct",
            "USG%": "PlayoffUSG_Pct",
            "WS": "PlayoffWS",
            "BPM": "PlayoffBPM",
            "VORP": "PlayoffVORP",
        }
    )
    playoff = totals[
        [
            "PlayerKeyRaw",
            "Player",
            "Age",
            "PlayoffTeam",
            "Pos",
            "G",
            "GS",
            "PlayoffMinutes",
            "PlayoffPoints",
            "PlayoffRebounds",
            "PlayoffAssists",
            "PlayoffSteals",
            "PlayoffBlocks",
            "PlayoffTurnovers",
        ]
    ].merge(
        advanced[
            [
                "PlayerKeyRaw",
                "PER",
                "PlayoffTS_Pct",
                "PlayoffUSG_Pct",
                "PlayoffWS",
                "PlayoffBPM",
                "PlayoffVORP",
            ]
        ],
        on="PlayerKeyRaw",
        how="left",
    )
    playoff = playoff.rename(columns={"Player": "PlayerName", "G": "PlayoffGames", "GS": "PlayoffGamesStarted", "PER": "PlayoffPER"})
    playoff.insert(0, "SeasonEndYear", year)
    playoff.insert(0, "Season", season)
    playoff["PlayoffProductionScore"] = (
        playoff["PlayoffPoints"].fillna(0)
        + 1.2 * playoff["PlayoffRebounds"].fillna(0)
        + 1.5 * playoff["PlayoffAssists"].fillna(0)
        + 3.0 * playoff["PlayoffSteals"].fillna(0)
        + 3.0 * playoff["PlayoffBlocks"].fillna(0)
        - playoff["PlayoffTurnovers"].fillna(0)
    )
    return playoff


def enrich_playoffs(playoffs: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    if playoffs.empty:
        return playoffs
    salary_cols = fact[
        [
            "Season",
            "PlayerKeyRaw",
            "PlayerKey",
            "PlayerSeasonKey",
            "Salary",
            "SalaryMillions",
            "ContractTier",
            "PlayerValueTier",
        ]
    ]
    playoffs = playoffs.merge(salary_cols, on=["Season", "PlayerKeyRaw"], how="left", suffixes=("", "_Fact"))
    playoffs["PlayoffValueScore"] = safe_divide(playoffs["PlayoffProductionScore"], playoffs["SalaryMillions"])
    playoffs["CostPerPlayoffPoint"] = safe_divide(playoffs["Salary"], playoffs["PlayoffPoints"])
    playoffs["CostPerPlayoffEstimatedWinShare"] = safe_divide(
        playoffs["Salary"], playoffs["PlayoffEstimatedWinShares"].where(playoffs["PlayoffEstimatedWinShares"] > 0)
    )
    return playoffs


def get_future_contract_salaries() -> pd.DataFrame:
    try:
        df = read_html_tables(SOURCES["salaries"], attempts=2, wait_seconds=6)[0]
    except Exception:
        return pd.DataFrame(columns=["PlayerKeyRaw", "FutureSalaryTeam", "NextSeasonSalary", "GuaranteedSalary"])
    df.columns = [flatten_salary_column(col) for col in df.columns]
    df = df[df["Player"].astype(str) != "Player"].copy()
    df["PlayerKeyRaw"] = df["Player"].map(normalize_name)
    next_salary_col = "2026-27"
    if next_salary_col not in df.columns:
        return pd.DataFrame(columns=["PlayerKeyRaw", "FutureSalaryTeam", "NextSeasonSalary", "GuaranteedSalary"])
    result = df[["PlayerKeyRaw", "Tm", next_salary_col, "Guaranteed"]].rename(
        columns={"Tm": "FutureSalaryTeam", next_salary_col: "NextSeasonSalary", "Guaranteed": "GuaranteedSalary"}
    )
    result["NextSeasonSalary"] = result["NextSeasonSalary"].map(parse_money)
    result["GuaranteedSalary"] = result["GuaranteedSalary"].map(parse_money)
    return result.dropna(subset=["NextSeasonSalary"]).reset_index(drop=True)


def linear_predict(train: pd.DataFrame, predict: pd.DataFrame, features: list[str], target: str) -> tuple[np.ndarray, dict]:
    train_data = train[features + [target]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(train_data) < len(features) + 5:
        return np.full(len(predict), np.nan), {"target": target, "training_rows": len(train_data), "rmse": None, "mae": None}
    means = train_data[features].mean()
    stds = train_data[features].std().replace(0, 1)
    x_train = ((train_data[features] - means) / stds).to_numpy()
    x_train = np.column_stack([np.ones(len(x_train)), x_train])
    y_train = train_data[target].to_numpy()
    beta = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
    fitted = x_train @ beta
    errors = fitted - y_train
    predict_x = predict[features].replace([np.inf, -np.inf], np.nan).fillna(means)
    predict_x = ((predict_x - means) / stds).to_numpy()
    predict_x = np.column_stack([np.ones(len(predict_x)), predict_x])
    predictions = predict_x @ beta
    metrics = {
        "target": target,
        "training_rows": int(len(train_data)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "mae": float(np.mean(np.abs(errors))),
    }
    return predictions, metrics


def build_predictions(fact: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = fact.sort_values(["PlayerKey", "SeasonEndYear"]).copy()
    next_rows = ordered[
        [
            "PlayerKey",
            "SeasonEndYear",
            "EstimatedWinShares",
            "ProductionScore",
            "ValueScore",
        ]
    ].copy()
    next_rows["SeasonEndYear"] = next_rows["SeasonEndYear"] - 1
    next_rows = next_rows.rename(
        columns={
            "EstimatedWinShares": "ActualNextSeasonEstimatedWinShares",
            "ProductionScore": "ActualNextSeasonProductionScore",
            "ValueScore": "ActualNextSeasonValueScore",
        }
    )
    modeling = ordered.merge(next_rows, on=["PlayerKey", "SeasonEndYear"], how="left")
    modeling["SalaryMillionsFilled"] = modeling["SalaryMillions"].fillna(modeling["SalaryMillions"].median())
    modeling["ValueScoreFilled"] = modeling["ValueScore"].fillna(modeling["ValueScore"].median())
    features = [
        "G",
        "TotalMinutes",
        "PPG",
        "RPG",
        "APG",
        "SPG",
        "BPG",
        "TPG",
        "FG%",
        "3P%",
        "FT%",
        "eFG%",
        "TS_Pct",
        "ProductionScore",
        "EstimatedWinShares",
        "SalaryMillionsFilled",
        "ValueScoreFilled",
    ]
    train = modeling[modeling["ActualNextSeasonEstimatedWinShares"].notna()].copy()
    latest_year = int(modeling["SeasonEndYear"].max())
    latest = modeling[modeling["SeasonEndYear"] == latest_year].copy()

    pred_ws, metrics_ws = linear_predict(train, latest, features, "ActualNextSeasonEstimatedWinShares")
    pred_prod, metrics_prod = linear_predict(train, latest, features, "ActualNextSeasonProductionScore")
    backtest_ws, _ = linear_predict(train, train, features, "ActualNextSeasonEstimatedWinShares")
    backtest_prod, _ = linear_predict(train, train, features, "ActualNextSeasonProductionScore")

    future_salaries = get_future_contract_salaries()
    predictions = latest[
        [
            "PlayerSeasonKey",
            "PlayerKey",
            "PlayerKeyRaw",
            "Season",
            "SeasonEndYear",
            "PlayerName",
            "StatsTeam",
            "Salary",
            "SalaryMillions",
            "Age",
            "Position",
            "PositionGroup",
            "EstimatedWinShares",
            "ProductionScore",
            "ValueScore",
            "PlayerValueTier",
        ]
    ].copy()
    predictions["PredictedNextSeasonEstimatedWinShares"] = np.maximum(pred_ws, 0)
    predictions["PredictedNextSeasonProductionScore"] = np.maximum(pred_prod, 0)
    if not future_salaries.empty:
        predictions = predictions.merge(future_salaries, on="PlayerKeyRaw", how="left")
    else:
        predictions["NextSeasonSalary"] = np.nan
        predictions["GuaranteedSalary"] = np.nan
        predictions["FutureSalaryTeam"] = np.nan
    predictions["PredictionSalaryBaseline"] = predictions["NextSeasonSalary"].fillna(predictions["Salary"])
    predictions["PredictionSalaryBaselineMillions"] = predictions["PredictionSalaryBaseline"] / 1_000_000
    predictions["PredictedNextSeasonValueScore"] = safe_divide(
        predictions["PredictedNextSeasonProductionScore"], predictions["PredictionSalaryBaselineMillions"]
    )
    predictions["PredictionTier"] = predictions["PredictedNextSeasonValueScore"].map(prediction_tier)

    backtest = train[
        [
            "PlayerSeasonKey",
            "PlayerKey",
            "Season",
            "SeasonEndYear",
            "PlayerName",
            "StatsTeam",
            "Age",
            "Position",
            "EstimatedWinShares",
            "ProductionScore",
            "ValueScore",
            "ActualNextSeasonEstimatedWinShares",
            "ActualNextSeasonProductionScore",
            "ActualNextSeasonValueScore",
        ]
    ].copy()
    backtest["PredictedNextSeasonEstimatedWinShares"] = np.maximum(backtest_ws, 0)
    backtest["PredictedNextSeasonProductionScore"] = np.maximum(backtest_prod, 0)
    backtest["NextSeasonEstimatedWinShareError"] = (
        backtest["PredictedNextSeasonEstimatedWinShares"] - backtest["ActualNextSeasonEstimatedWinShares"]
    )
    backtest["NextSeasonProductionError"] = (
        backtest["PredictedNextSeasonProductionScore"] - backtest["ActualNextSeasonProductionScore"]
    )
    model_metrics = pd.DataFrame([metrics_ws, metrics_prod])
    model_metrics.insert(0, "ModelName", "Baseline linear next-season forecast")
    model_metrics["FeatureSet"] = ", ".join(features)
    model_metrics["LatestPredictionSeason"] = latest_year
    return predictions, backtest, model_metrics


def build_tables_v3() -> dict[str, pd.DataFrame]:
    stats_frames = []
    per_poss_frames = []
    shooting_frames = []
    salary_frames = []
    team_context_frames = []
    playoff_frames = []

    for config in SEASON_CONFIGS:
        season = config["season"]
        year = config["year"]
        stats, per_poss, shooting = build_regular_stats_for_season(season, year)
        stats_frames.append(stats)
        per_poss_frames.append(per_poss)
        shooting_frames.append(shooting)
        salary_frames.append(read_espn_salary_season(season, year))
        team_context_frames.append(read_team_context_v3(season, year))
        if config["playoffs_available"]:
            playoff = read_playoff_table(season, year)
            if not playoff.empty:
                playoff_frames.append(playoff)
        time.sleep(0.75)

    stats = pd.concat(stats_frames, ignore_index=True)
    salaries = pd.concat(salary_frames, ignore_index=True)
    per_poss = pd.concat(per_poss_frames, ignore_index=True)
    shooting = pd.concat(shooting_frames, ignore_index=True)
    team_context = pd.concat(team_context_frames, ignore_index=True)
    playoffs = pd.concat(playoff_frames, ignore_index=True) if playoff_frames else pd.DataFrame()

    fact = stats.merge(salaries, on=["Season", "SeasonEndYear", "PlayerKeyRaw"], how="left")
    fact["PlayerName"] = fact["Player"].fillna(fact["SalaryPlayer"])
    fact["Position"] = fact["Pos"].map(first_position)
    fact["PositionGroup"] = fact["Pos"].map(position_group)
    fact["StatsTeamName"] = fact["StatsTeam"].map(lambda key: TEAM_META.get(str(key), ("Multiple Teams", "", ""))[0])
    fact["SalaryTeam"] = fact["SalaryTeam"].fillna(np.nan)
    fact["SourceSeasonNote"] = "Basketball Reference regular-season stats; ESPN salary row when available."
    fact = calculate_value_metrics(fact)

    fact, per_poss, shooting, playoffs, dim_player = add_player_keys(fact, per_poss, shooting, playoffs)
    fact = fact.sort_values(["SeasonEndYear", "PlayerName", "StatsTeam"]).reset_index(drop=True)
    per_poss = per_poss.sort_values(["SeasonEndYear", "PlayerSeasonKey"]).reset_index(drop=True)
    shooting = shooting.sort_values(["SeasonEndYear", "PlayerSeasonKey"]).reset_index(drop=True)
    playoffs = enrich_playoffs(playoffs, fact).sort_values(["SeasonEndYear", "PlayoffProductionScore"], ascending=[True, False]) if not playoffs.empty else playoffs

    dim_team = pd.DataFrame(
        [
            {"TeamKey": key, "TeamName": name, "Conference": conference, "Division": division}
            for key, (name, conference, division) in TEAM_META.items()
        ]
    )
    dim_position = pd.DataFrame(
        [{"Position": position, "PositionGroup": meta[1], "SortOrder": meta[0]} for position, meta in POSITION_SORT.items()]
    )
    dim_season = pd.DataFrame(
        [
            {
                "Season": config["season"],
                "SeasonEndYear": config["year"],
                "SalaryCap": SALARY_CAPS[config["season"]],
                "PlayoffsAvailable": config["playoffs_available"],
            }
            for config in SEASON_CONFIGS
        ]
    )

    team_efficiency = build_team_efficiency(fact, team_context, dim_team)
    team_payroll_allocation = build_team_payroll_allocation(fact, dim_team)
    predictions, prediction_backtest, model_metrics = build_predictions(fact)

    salary_unmatched = salaries.merge(
        fact[["Season", "PlayerKeyRaw", "PlayerSeasonKey"]], on=["Season", "PlayerKeyRaw"], how="left"
    )
    salary_unmatched = salary_unmatched[salary_unmatched["PlayerSeasonKey"].isna()].drop(columns=["PlayerSeasonKey"])

    fact_columns = [
        "PlayerSeasonKey",
        "PlayerKey",
        "Season",
        "SeasonEndYear",
        "PlayerName",
        "StatsTeam",
        "StatsTeamName",
        "SalaryTeam",
        "SalaryTeamName",
        "Position",
        "PositionGroup",
        "Age",
        "Salary",
        "SalaryMillions",
        "SalaryCap",
        "SalaryCapPct",
        "SalaryRank",
        "SalaryAvailable",
        "SalaryMissingReason",
        "ContractTier",
        "PlayerValueTier",
        "G",
        "GS",
        "TotalMinutes",
        "MPG",
        "TotalPoints",
        "PPG",
        "TotalRebounds",
        "RPG",
        "TotalAssists",
        "APG",
        "TotalSteals",
        "SPG",
        "TotalBlocks",
        "BPG",
        "TotalTurnovers",
        "TPG",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "3P%",
        "2P",
        "2PA",
        "2P%",
        "eFG%",
        "FT",
        "FTA",
        "FT%",
        "PER",
        "TS_Pct",
        "USG_Pct",
        "WS",
        "WS/48",
        "BPM",
        "VORP",
        "ProductionScore",
        "CostPerPoint",
        "CostPerWinShare",
        "PointsPerMillion",
        "WinSharesPerMillion",
        "ValueScore",
        "ProductionPercentile",
        "SalaryPercentile",
        "ValuePercentile",
        "SalaryRank",
        "ProductionRank",
        "ValueRank",
        "ValueGap",
        "QualifiedForValueRank",
        "IsAllStar",
        "Awards",
        "SalarySource",
        "SourceSeasonNote",
    ]
    fact = fact[[col for col in fact_columns if col in fact.columns]]

    data_dictionary = pd.DataFrame(
        [
            ("Fact_Player_Value", "PlayerSeasonKey", "Text", "Unique player-season key."),
            ("Fact_Player_Value", "PlayerKey", "Text", "Stable player key across seasons."),
            ("Fact_Player_Value", "Season", "Text", "NBA season label."),
            ("Fact_Player_Value", "Salary", "Currency", "ESPN listed player salary when matched."),
            ("Fact_Player_Value", "SalaryAvailable", "Boolean", "True when salary matched for the player-season."),
            ("Fact_Player_Value", "ContractTier", "Text", "Salary-cap based contract bucket."),
            ("Fact_Player_Value", "PlayerValueTier", "Text", "Analytical player value segment based on salary, production, and value percentiles."),
            ("Fact_Player_Value", "ProductionScore", "Number", "PTS + 1.2*REB + 1.5*AST + 3*STL + 3*BLK - TOV."),
            ("Fact_Player_Value", "ValueScore", "Number", "Production score per salary million."),
            ("Player_Pace_Adjusted", "PTSPer100", "Number", "Points per 100 possessions."),
            ("Player_Shooting_Profile", "AvgShotDistance", "Number", "Average field goal attempt distance."),
            ("Player_Playoff_Performance", "PlayoffValueScore", "Number", "Playoff production per salary million."),
            ("Player_Predictions", "PredictedNextSeasonWS", "Number", "Baseline linear forecast for next-season win shares."),
            ("Player_Predictions", "PredictionTier", "Text", "Predicted next-season value segment."),
            ("Team_Efficiency", "PayrollPerWin", "Currency", "Team payroll divided by regular-season wins."),
            ("Team_Payroll_Allocation", "Top3SalaryShare", "Number", "Share of team payroll held by the three highest-paid players."),
            ("Team_Context", "AdjustedNetRtg", "Number", "Basketball Reference adjusted net rating."),
            ("Dim_Season", "SalaryCap", "Currency", "NBA salary cap used for contract tier approximation."),
        ],
        columns=["TableName", "ColumnName", "DataType", "Description"],
    )

    measure_catalog = pd.DataFrame(
        [
            ("Total Salary", "SUM(Fact_Player_Value[Salary])", "Currency", "Total salary in context."),
            ("Salary Millions", "DIVIDE([Total Salary], 1000000)", "Decimal", "Salary in millions."),
            ("Total Points", "SUM(Fact_Player_Value[TotalPoints])", "Whole number", "Total regular-season points."),
            ("Total Win Shares", "SUM(Fact_Player_Value[WS])", "Decimal", "Total regular-season win shares."),
            ("Production Score", "SUM(Fact_Player_Value[ProductionScore])", "Decimal", "Weighted box-score production."),
            ("Value Score", "DIVIDE([Production Score], [Salary Millions])", "Decimal", "Production per salary million."),
            ("Cost Per Win Share", "DIVIDE([Total Salary], [Total Win Shares])", "Currency", "Salary per win share."),
            ("Payroll Per Win", "DIVIDE([Total Salary], SUM(Team_Efficiency[W]))", "Currency", "Team payroll per win."),
            ("Salary Coverage %", "DIVIDE(CALCULATE(COUNTROWS(Fact_Player_Value), Fact_Player_Value[SalaryAvailable] = TRUE()), COUNTROWS(Fact_Player_Value))", "Percentage", "Share of player-seasons with salary data."),
            ("Avg Shot Distance", "AVERAGE(Player_Shooting_Profile[AvgShotDistance])", "Decimal", "Average shot distance."),
            ("Avg 3P Attempt Share", "AVERAGE(Player_Shooting_Profile[FGA_3P_Frequency])", "Percentage", "Average 3P attempt share."),
            ("Playoff Value Score", "DIVIDE(SUM(Player_Playoff_Performance[PlayoffProductionScore]), DIVIDE(SUM(Player_Playoff_Performance[Salary]), 1000000))", "Decimal", "Playoff production per salary million."),
            ("Predicted Next WS", "SUM(Player_Predictions[PredictedNextSeasonWS])", "Decimal", "Forecast next-season win shares."),
            ("Predicted Next Value Score", "AVERAGE(Player_Predictions[PredictedNextSeasonValueScore])", "Decimal", "Forecast value score."),
            ("Top 3 Payroll Share", "AVERAGE(Team_Payroll_Allocation[Top3SalaryShare])", "Percentage", "Average top-three payroll concentration."),
        ],
        columns=["MeasureName", "DAX", "Format", "Description"],
    )

    source_notes = pd.DataFrame(
        [
            ("PulledAtLocalTime", PULLED_AT),
            ("SeasonRange", f"{SEASON_CONFIGS[0]['season']} through {SEASON_CONFIGS[-1]['season']}"),
            ("Regular-season player rows", str(len(fact))),
            ("Salary-covered player rows", str(int(fact["SalaryAvailable"].sum()))),
            ("Salary source", "ESPN NBA salaries paginated by season."),
            ("Regular season stats source", "Basketball Reference totals, per-game, advanced, per-100, and shooting tables."),
            ("Team source", "Basketball Reference team summary, ratings, four factors, and shooting tables."),
            ("Playoff source", "Basketball Reference playoff totals and advanced tables for completed playoff seasons."),
            ("Prediction note", "Baseline linear model trained on prior player-seasons with next-season outcomes. Use as directional, not betting/decision advice."),
            ("Contract tier note", "Contract tiers are approximations based on salary as a share of salary cap plus age heuristics."),
        ],
        columns=["Item", "Value"],
    )

    return {
        "Fact_Player_Value": fact,
        "Player_Pace_Adjusted": per_poss,
        "Player_Shooting_Profile": shooting,
        "Player_Playoff_Performance": playoffs,
        "Player_Predictions": predictions,
        "Prediction_Backtest": prediction_backtest,
        "Prediction_Model_Metrics": model_metrics,
        "Team_Efficiency": team_efficiency,
        "Team_Context": team_context,
        "Team_Payroll_Allocation": team_payroll_allocation,
        "Dim_Player": dim_player,
        "Dim_Team": dim_team,
        "Dim_Position": dim_position,
        "Dim_Season": dim_season,
        "Data_Dictionary": data_dictionary,
        "Measure_Catalog": measure_catalog,
        "Source_Notes": source_notes,
        "Salary_Unmatched": salary_unmatched,
    }


def write_csvs_v3(tables: dict[str, pd.DataFrame]) -> None:
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    file_map = {
        "Fact_Player_Value": "fact_player_value.csv",
        "Player_Pace_Adjusted": "player_pace_adjusted.csv",
        "Player_Shooting_Profile": "player_shooting_profile.csv",
        "Player_Playoff_Performance": "player_playoff_performance.csv",
        "Player_Predictions": "player_predictions.csv",
        "Prediction_Backtest": "prediction_backtest.csv",
        "Prediction_Model_Metrics": "prediction_model_metrics.csv",
        "Team_Efficiency": "team_efficiency.csv",
        "Team_Context": "team_context.csv",
        "Team_Payroll_Allocation": "team_payroll_allocation.csv",
        "Dim_Player": "dim_player.csv",
        "Dim_Team": "dim_team.csv",
        "Dim_Position": "dim_position.csv",
        "Dim_Season": "dim_season.csv",
        "Data_Dictionary": "data_dictionary.csv",
        "Measure_Catalog": "measure_catalog.csv",
        "Source_Notes": "source_notes.csv",
        "Salary_Unmatched": "salary_unmatched.csv",
    }
    for table_name, file_name in file_map.items():
        tables[table_name].to_csv(DATA_OUTPUT / file_name, index=False)


def write_summary_v3(tables: dict[str, pd.DataFrame]) -> None:
    fact = tables["Fact_Player_Value"]
    team_eff = tables["Team_Efficiency"]
    predictions = tables["Player_Predictions"]
    latest_season = fact["SeasonEndYear"].max()
    latest_label = fact.loc[fact["SeasonEndYear"] == latest_season, "Season"].iloc[0]
    top_values = (
        fact[fact["QualifiedForValueRank"]]
        .sort_values(["SeasonEndYear", "ValueScore"], ascending=[False, False])
        .groupby("Season")
        .head(5)[["Season", "PlayerName", "StatsTeam", "SalaryMillions", "EstimatedWinShares", "ValueScore", "PlayerValueTier"]]
        .to_dict(orient="records")
    )
    summary = {
        "season_range": f"{SEASON_CONFIGS[0]['season']} through {SEASON_CONFIGS[-1]['season']}",
        "latest_season": latest_label,
        "pulled_at": PULLED_AT,
        "regular_season_player_rows": int(len(fact)),
        "unique_players": int(fact["PlayerKey"].nunique()),
        "salary_covered_rows": int(fact["SalaryAvailable"].sum()),
        "salary_coverage_pct": float(fact["SalaryAvailable"].mean()),
        "playoff_rows": int(len(tables["Player_Playoff_Performance"])),
        "team_context_rows": int(len(tables["Team_Context"])),
        "prediction_rows": int(len(predictions)),
        "top_value_players_by_season": top_values,
        "latest_top_team_value": team_eff[team_eff["SeasonEndYear"] == latest_season]
        .sort_values("ValueScore", ascending=False)
        .head(1)[["Season", "TeamName", "TeamKey", "ValueScore"]]
        .to_dict(orient="records"),
        "sources": {
            "espn_player_stats": "https://www.espn.com/nba/stats/player/_/season/{year}/seasontype/{season_type}/table/offensive/page/{page}",
            "espn_salaries": "https://www.espn.com/nba/salaries/_/page/{page}/year/{year}",
            "espn_standings": "https://www.espn.com/nba/standings/_/season/{year}/group/league",
            "basketball_reference_contracts_fallback": "https://www.basketball-reference.com/contracts/players.html",
        },
    }
    (OUTPUT / "project_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_docs_v3(tables: dict[str, pd.DataFrame]) -> None:
    fact = tables["Fact_Player_Value"]
    summary_rows = {
        "regular": len(fact),
        "players": fact["PlayerKey"].nunique(),
        "salary": int(fact["SalaryAvailable"].sum()),
        "playoffs": len(tables["Player_Playoff_Performance"]),
        "predictions": len(tables["Player_Predictions"]),
        "teams": len(tables["Team_Context"]),
    }
    top_latest = (
        fact[(fact["QualifiedForValueRank"]) & (fact["Season"] == SEASON_CONFIGS[-1]["season"])]
        .sort_values("ValueScore", ascending=False)
        .head(10)[["PlayerName", "StatsTeam", "SalaryMillions", "EstimatedWinShares", "ValueScore", "PlayerValueTier"]]
    )
    top_table = markdown_table(top_latest)

    readme = f"""# NBA Contract Value Analysis

## Project Question

Which NBA players, teams, and contract types generated the most value across the **{SEASON_CONFIGS[0]["season"]} through {SEASON_CONFIGS[-1]["season"]}** seasons, and which players look like future value opportunities?

This Power BI portfolio project now includes all ESPN regular-season player-seasons over the selected seasons, historical ESPN salary rows when matched, ESPN playoff performance, team-building payroll allocation, contract/value tiers, and baseline prediction outputs.

## Data Sources

- ESPN NBA player stats: regular season and playoffs, paginated by season.
- ESPN NBA salary pages: paginated historical salary tables by season.
- ESPN NBA standings: wins, losses, points per game, opponent points per game, and point differential.
- Basketball Reference current contracts: attempted as a next-season salary baseline where reachable.

Data was pulled locally on **{PULLED_AT}**. Public pages can update or throttle automated reads, so refresh before submitting final work if current numbers matter.

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

- Regular-season player rows: **{summary_rows["regular"]:,}**
- Unique players: **{summary_rows["players"]:,}**
- Salary-covered rows: **{summary_rows["salary"]:,}**
- Playoff rows: **{summary_rows["playoffs"]:,}**
- Team context rows: **{summary_rows["teams"]:,}**
- Prediction rows: **{summary_rows["predictions"]:,}**

## Latest-Season Value Starters

{top_table}

Use these as analytical starting points. The report should let the viewer switch between raw value rankings, contract tiers, playoff value, team payroll strategy, and predicted future value.
"""

    dax = """# Suggested Power BI DAX Measures

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
"""

    build_guide = """# Power BI Build Guide

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
"""

    wireframe = """# Report Wireframe

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
"""

    ui_style = """# UI Style Guide

## Visual Direction

Premium sports analytics desk: dark, sharp, calm, and data-first.

## Theme

Import `theme/nba-contract-value-theme.json` in Power BI.

## Layout

- Canvas: 16:9.
- Background: `#07111F`.
- Outer margin: 24 px.
- Gutter: 16 px.
- Header: 64-76 px.
- Left navigation rail: 72-96 px if using icons/buttons.
- KPI cards: 4 max per page.

## Navigation

- Use page navigation buttons for Overview, Trends, Players, Contracts, Shot Profile, Playoffs, Prediction, Methodology.
- Use a consistent active-page accent in cyan.
- Keep slicers in one location across pages.

## Tooltip Page

Create a tooltip page named `Player Tooltip` with:

- Player name, season, team
- Salary and contract tier
- PPG/RPG/APG
- Estimated Win Shares, Production Score, eFG%, TS%, 3P attempt share
- Value Score and Value Tier
- Free throw rate, 3P attempt share, double-doubles/triple-doubles
- Prediction tier when available

## Color Tokens

- Background: `#07111F`
- Surface: `#102033`
- Elevated surface: `#172A42`
- Primary text: `#F8FAFC`
- Muted text: `#A8B3C5`
- Primary accent: `#38BDF8`
- Secondary accent: `#FBBF24`
- Positive: `#22C55E`
- Negative: `#F43F5E`

## Formatting Rules

- Salary: `$0.0M`
- Percentages: `0.0%`
- Value scores: one decimal
- Ranks: whole numbers
- Sort ranking visuals descending by value score unless intentionally showing risks
"""

    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "README.md").write_text(readme, encoding="utf-8")
    (DOCS_OUTPUT / "dax_measures.md").write_text(dax, encoding="utf-8")
    (DOCS_OUTPUT / "powerbi_build_guide.md").write_text(build_guide, encoding="utf-8")
    (DOCS_OUTPUT / "report_wireframe.md").write_text(wireframe, encoding="utf-8")
    (DOCS_OUTPUT / "ui_style_guide.md").write_text(ui_style, encoding="utf-8")


def build_tables_espn_v3() -> dict[str, pd.DataFrame]:
    regular_frames = []
    rate_frames = []
    shooting_frames = []
    salary_frames = []
    standings_frames = []
    playoff_frames = []

    for config in SEASON_CONFIGS:
        season = config["season"]
        year = config["year"]
        regular_raw = read_espn_player_stats(season, year, season_type=2)
        regular = espn_regular_to_fact(regular_raw)
        regular_frames.append(regular)
        rate_frames.append(espn_rate_stats(regular_raw))
        shooting_frames.append(espn_shooting_profile(regular_raw))
        salary_frames.append(read_espn_salary_season(season, year))
        standings_frames.append(read_espn_standings(season, year))
        playoff_frames.append(read_espn_playoff_table(season, year))
        time.sleep(0.4)

    stats = pd.concat(regular_frames, ignore_index=True)
    salaries = pd.concat(salary_frames, ignore_index=True)
    per_poss = pd.concat(rate_frames, ignore_index=True)
    shooting = pd.concat(shooting_frames, ignore_index=True)
    team_context = pd.concat(standings_frames, ignore_index=True)
    playoffs = pd.concat([frame for frame in playoff_frames if not frame.empty], ignore_index=True)

    fact = stats.merge(salaries, on=["Season", "SeasonEndYear", "PlayerKeyRaw"], how="left")
    fact["PlayerName"] = fact["PlayerName"].fillna(fact["SalaryPlayer"])
    fact["Position"] = fact["Pos"].map(first_position)
    fact["PositionGroup"] = fact["Pos"].map(position_group)
    fact["StatsTeamName"] = fact["StatsTeam"].map(lambda key: TEAM_META.get(str(key), ("Multiple Teams", "", ""))[0])
    fact["SourceSeasonNote"] = "ESPN regular-season player stats and ESPN salary row when available."
    fact = calculate_value_metrics(fact)
    fact, per_poss, shooting, playoffs, dim_player = add_player_keys(fact, per_poss, shooting, playoffs)
    fact = fact.sort_values(["SeasonEndYear", "PlayerName", "StatsTeam"]).reset_index(drop=True)
    per_poss = per_poss.sort_values(["SeasonEndYear", "PlayerSeasonKey"]).reset_index(drop=True)
    shooting = shooting.sort_values(["SeasonEndYear", "PlayerSeasonKey"]).reset_index(drop=True)
    playoffs = enrich_playoffs(playoffs, fact).sort_values(["SeasonEndYear", "PlayoffProductionScore"], ascending=[True, False])

    dim_team = pd.DataFrame(
        [
            {"TeamKey": key, "TeamName": name, "Conference": conference, "Division": division}
            for key, (name, conference, division) in TEAM_META.items()
        ]
    )
    dim_position = pd.DataFrame(
        [{"Position": position, "PositionGroup": meta[1], "SortOrder": meta[0]} for position, meta in POSITION_SORT.items()]
    )
    dim_season = pd.DataFrame(
        [
            {
                "Season": config["season"],
                "SeasonEndYear": config["year"],
                "SalaryCap": SALARY_CAPS[config["season"]],
                "PlayoffsAvailable": True,
            }
            for config in SEASON_CONFIGS
        ]
    )
    team_context = team_context.merge(dim_team[["TeamKey", "Conference", "Division"]], on="TeamKey", how="left")
    team_context["AdjustedNetRtg"] = team_context["NetPointDiff"]
    team_context["AdjustedORtg"] = team_context["PointsPerGame"]
    team_context["AdjustedDRtg"] = team_context["OpponentPointsPerGame"]
    team_context["Pace"] = np.nan
    team_context["Team3P_Frequency"] = np.nan
    team_context["TeamRimFrequency"] = np.nan

    team_efficiency = build_team_efficiency(fact, team_context, dim_team)
    team_payroll_allocation = build_team_payroll_allocation(fact, dim_team)
    predictions, prediction_backtest, model_metrics = build_predictions(fact)
    salary_unmatched = salaries.merge(
        fact[["Season", "PlayerKeyRaw", "PlayerSeasonKey"]], on=["Season", "PlayerKeyRaw"], how="left"
    )
    salary_unmatched = salary_unmatched[salary_unmatched["PlayerSeasonKey"].isna()].drop(columns=["PlayerSeasonKey"])

    fact_columns = [
        "PlayerSeasonKey",
        "PlayerKey",
        "Season",
        "SeasonEndYear",
        "PlayerName",
        "StatsTeam",
        "StatsTeamRaw",
        "StatsTeamName",
        "SalaryTeam",
        "SalaryTeamName",
        "Position",
        "PositionGroup",
        "Salary",
        "SalaryMillions",
        "SalaryCap",
        "SalaryCapPct",
        "SalaryRank",
        "SalaryAvailable",
        "SalaryMissingReason",
        "ContractTier",
        "PlayerValueTier",
        "G",
        "TotalMinutes",
        "MPG",
        "TotalPoints",
        "PPG",
        "TotalRebounds",
        "RPG",
        "TotalAssists",
        "APG",
        "TotalSteals",
        "SPG",
        "TotalBlocks",
        "BPG",
        "TotalTurnovers",
        "TPG",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "3P%",
        "2P",
        "2PA",
        "2P%",
        "eFG%",
        "FT",
        "FTA",
        "FT%",
        "TS_Pct",
        "EstimatedWinShares",
        "ProductionScore",
        "CostPerPoint",
        "CostPerEstimatedWinShare",
        "PointsPerMillion",
        "EstimatedWinSharesPerMillion",
        "ValueScore",
        "ProductionPercentile",
        "SalaryPercentile",
        "ValuePercentile",
        "ProductionRank",
        "ValueRank",
        "ValueGap",
        "QualifiedForValueRank",
        "SalarySource",
        "SourceSeasonNote",
    ]
    fact = fact[[col for col in fact_columns if col in fact.columns]]

    data_dictionary = pd.DataFrame(
        [
            ("Fact_Player_Value", "PlayerSeasonKey", "Text", "Unique player-season key."),
            ("Fact_Player_Value", "Salary", "Currency", "ESPN listed player salary when matched."),
            ("Fact_Player_Value", "EstimatedWinShares", "Number", "Estimated win-share-style proxy from production score; not official Basketball Reference WS."),
            ("Fact_Player_Value", "CostPerEstimatedWinShare", "Currency", "Salary divided by estimated win shares. Lower is better."),
            ("Fact_Player_Value", "ContractTier", "Text", "Salary-cap based contract bucket."),
            ("Fact_Player_Value", "PlayerValueTier", "Text", "Salary-adjusted value segment."),
            ("Player_Pace_Adjusted", "PTSPer36", "Number", "Points per 36 minutes."),
            ("Player_Shooting_Profile", "FGA_3P_Frequency", "Number", "Share of FGA from three-point range."),
            ("Player_Shooting_Profile", "FreeThrowRate", "Number", "Free throw attempts per field goal attempt."),
            ("Player_Playoff_Performance", "PlayoffEstimatedWinShares", "Number", "Estimated playoff win-share-style proxy from playoff production score."),
            ("Player_Playoff_Performance", "PlayoffValueScore", "Number", "Playoff production per salary million."),
            ("Player_Predictions", "PredictedNextSeasonEstimatedWinShares", "Number", "Baseline linear forecast for next-season estimated win shares."),
            ("Player_Predictions", "PredictedNextSeasonValueScore", "Number", "Baseline next-season value forecast."),
            ("Team_Efficiency", "TotalEstimatedWinShares", "Number", "Team sum of estimated player win-share proxy."),
            ("Team_Efficiency", "CostPerEstimatedWinShare", "Currency", "Team payroll divided by total estimated win shares."),
            ("Team_Payroll_Allocation", "Top3SalaryShare", "Number", "Share of payroll held by top three salaries."),
            ("Team_Context", "NetPointDiff", "Number", "ESPN standings point differential per game."),
        ],
        columns=["TableName", "ColumnName", "DataType", "Description"],
    )
    measure_catalog = pd.DataFrame(
        [
            ("Total Salary", "SUM(Fact_Player_Value[Salary])", "Currency", "Total salary in context."),
            ("Salary Millions", "DIVIDE([Total Salary], 1000000)", "Decimal", "Salary in millions."),
            ("Salary Coverage %", "DIVIDE(CALCULATE(COUNTROWS(Fact_Player_Value), Fact_Player_Value[SalaryAvailable] = TRUE()), COUNTROWS(Fact_Player_Value))", "Percentage", "Share of rows with salary."),
            ("Total Points", "SUM(Fact_Player_Value[TotalPoints])", "Whole number", "Total points."),
            ("Estimated Win Shares", "SUM(Fact_Player_Value[EstimatedWinShares])", "Decimal", "Estimated win-share-style proxy."),
            ("Production Score", "SUM(Fact_Player_Value[ProductionScore])", "Decimal", "Weighted production."),
            ("Value Score", "DIVIDE([Production Score], [Salary Millions])", "Decimal", "Production per salary million."),
            ("Cost Per Point", "DIVIDE([Total Salary], [Total Points])", "Currency", "Salary per point."),
            ("Payroll Per Win", "DIVIDE([Total Salary], SUM(Team_Efficiency[W]))", "Currency", "Team payroll per win."),
            ("Average 3P Attempt Share", "AVERAGE(Player_Shooting_Profile[FGA_3P_Frequency])", "Percentage", "Average 3P attempt share."),
            ("Playoff Value Score", "DIVIDE(SUM(Player_Playoff_Performance[PlayoffProductionScore]), DIVIDE(SUM(Player_Playoff_Performance[Salary]), 1000000))", "Decimal", "Playoff production per salary million."),
            ("Top 3 Payroll Share", "AVERAGE(Team_Payroll_Allocation[Top3SalaryShare])", "Percentage", "Top-three payroll concentration."),
            ("Predicted Next Estimated Win Shares", "SUM(Player_Predictions[PredictedNextSeasonEstimatedWinShares])", "Decimal", "Forecast next estimated win shares."),
            ("Predicted Next Value Score", "AVERAGE(Player_Predictions[PredictedNextSeasonValueScore])", "Decimal", "Forecast next value."),
        ],
        columns=["MeasureName", "DAX", "Format", "Description"],
    )
    source_notes = pd.DataFrame(
        [
            ("PulledAtLocalTime", PULLED_AT),
            ("SeasonRange", f"{SEASON_CONFIGS[0]['season']} through {SEASON_CONFIGS[-1]['season']}"),
            ("Regular-season player rows", str(len(fact))),
            ("Salary-covered player rows", str(int(fact["SalaryAvailable"].sum()))),
            ("Primary source", "ESPN player stats, playoff stats, salaries, and standings."),
            ("Advanced metric note", "EstimatedWinShares is a transparent proxy from production score because ESPN does not provide official win shares."),
            ("Basketball Reference note", "Basketball Reference advanced source remains documented, but live multi-season refresh was blocked by HTTP 429 during this build."),
        ],
        columns=["Item", "Value"],
    )

    return {
        "Fact_Player_Value": fact,
        "Player_Pace_Adjusted": per_poss,
        "Player_Shooting_Profile": shooting,
        "Player_Playoff_Performance": playoffs,
        "Player_Predictions": predictions,
        "Prediction_Backtest": prediction_backtest,
        "Prediction_Model_Metrics": model_metrics,
        "Team_Efficiency": team_efficiency,
        "Team_Context": team_context,
        "Team_Payroll_Allocation": team_payroll_allocation,
        "Dim_Player": dim_player,
        "Dim_Team": dim_team,
        "Dim_Position": dim_position,
        "Dim_Season": dim_season,
        "Data_Dictionary": data_dictionary,
        "Measure_Catalog": measure_catalog,
        "Source_Notes": source_notes,
        "Salary_Unmatched": salary_unmatched,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tables = build_tables_espn_v3()
    write_csvs_v3(tables)
    write_docs_v3(tables)
    write_theme_assets()
    write_summary_v3(tables)

    fact = tables["Fact_Player_Value"]
    print(f"Built NBA Power BI source tables in {OUTPUT}")
    print(f"Regular-season player rows: {len(fact):,}")
    print(f"Unique players: {fact['PlayerKey'].nunique():,}")
    print(f"Salary-covered rows: {int(fact['SalaryAvailable'].sum()):,}")


if __name__ == "__main__":
    main()
