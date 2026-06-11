from __future__ import annotations

import json
import math
import re
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
    fact["CostPerPoint"] = safe_divide(fact["Salary"], fact["TotalPoints"])
    fact["CostPerWinShare"] = safe_divide(fact["Salary"], fact["WS"].where(fact["WS"] > 0))
    fact["PointsPerMillion"] = safe_divide(fact["TotalPoints"], fact["SalaryMillions"])
    fact["WinSharesPerMillion"] = safe_divide(fact["WS"], fact["SalaryMillions"])
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
            TotalWinShares=("WS", "sum"),
            TotalVORP=("VORP", "sum"),
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


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tables = build_tables()
    write_csvs(tables)
    write_docs(tables)
    write_theme_assets()
    write_summary(tables)

    fact = tables["Fact_Player_Value"]
    print(f"Built NBA Power BI source tables in {OUTPUT}")
    print(f"Salary rows: {len(fact):,}")
    print(f"Matched salary + stat rows: {int(fact['IsMatchedToStats'].sum()):,}")
    print(f"Unmatched salary rows: {int((~fact['IsMatchedToStats']).sum()):,}")


if __name__ == "__main__":
    main()
