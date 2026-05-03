"""
Combine all CSVs from a folder into a single Excel file, one tab per CSV.

Delimiter is auto-detected per file (handles comma, semicolon, tab, pipe, etc.).

Usage:
    python scripts/csvs_to_excel.py "C:/path/to/csv/folder"
    python scripts/csvs_to_excel.py "C:/path/to/csv/folder" --out "C:/path/to/output.xlsx"
    python scripts/csvs_to_excel.py "C:/path/to/csv/folder" --encoding cp1252
"""
import argparse
import csv
from pathlib import Path

import pandas as pd


def _detect_delimiter(csv_path: Path, encoding: str) -> str:
    """Sniff the delimiter from the first 4 KB of the file."""
    with open(csv_path, encoding=encoding, errors="replace") as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","  # default fallback


def _read_csv(csv_path: Path, encoding: str) -> pd.DataFrame:
    """Read a CSV with auto-detected delimiter, falling back to cp1252 on encoding errors."""
    for enc in [encoding, "cp1252"]:
        try:
            sep = _detect_delimiter(csv_path, enc)
            return pd.read_csv(csv_path, sep=sep, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read {csv_path.name} with any known encoding.")


def csvs_to_excel(folder: Path, output: Path, encoding: str = "utf-8-sig") -> None:
    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in: {folder}")
        return

    print(f"Found {len(csv_files)} CSV file(s) → {output}\n")

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for csv_path in csv_files:
            sheet_name = csv_path.stem[:31]  # Excel sheet name limit
            try:
                df = _read_csv(csv_path, encoding)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                sep = _detect_delimiter(csv_path, encoding)
                sep_label = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}.get(sep, sep)
                print(f"  {sheet_name:31s}  ({len(df)} rows, {len(df.columns)} cols)  [{sep_label}]")
            except Exception as e:
                print(f"  {sheet_name:31s}  ERROR: {e}")

    print(f"\nSaved: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine CSVs into one Excel file.")
    parser.add_argument("folder", help="Folder containing CSV files")
    parser.add_argument("--out", help="Output Excel file path (default: <folder>/combined.xlsx)")
    parser.add_argument("--encoding", default="utf-8-sig",
                        help="CSV encoding (default: utf-8-sig; try cp1252 for Windows exports)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: folder not found: {folder}")
        raise SystemExit(1)

    output = Path(args.out) if args.out else folder / "combined.xlsx"
    csvs_to_excel(folder, output, encoding=args.encoding)
