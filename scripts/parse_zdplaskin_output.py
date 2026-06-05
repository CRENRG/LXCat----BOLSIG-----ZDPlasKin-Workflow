import argparse
from pathlib import Path

import pandas as pd


def parse_zdplaskin_output(output_file):
    output_file = Path(output_file)
    if not output_file.exists():
        raise FileNotFoundError(f'ZDPlasKin output file not found: {output_file}')

    try:
        df = pd.read_csv(output_file, comment='#', delim_whitespace=True)
    except Exception:
        text = output_file.read_text(encoding='utf-8', errors='ignore').splitlines()
        rows = [line.strip() for line in text if line.strip() and not line.strip().startswith('#')]
        if not rows:
            raise ValueError('Unable to read ZDPlasKin output file or file is empty.')
        df = pd.read_csv(output_file, comment='#', delim_whitespace=True, header=None)

    species_columns = [col for col in df.columns if any(name in str(col).lower() for name in ('electron', 'e-', 'd2+', 'd3+', 'd2', 'd+', 'd'))]
    time_column = None
    for col in df.columns:
        if str(col).lower() in ('time', 't', 'seconds', 's'):
            time_column = col
            break
    if time_column is None and len(df.columns) > 0:
        time_column = df.columns[0]

    selected = df[[time_column] + species_columns] if species_columns else df.iloc[:, :min(6, len(df.columns))]
    parsed = {
        'data_frame': df,
        'selected': selected,
        'time_column': time_column,
        'species_columns': species_columns,
    }
    return parsed


def save_csv(parsed, csv_path):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    parsed['selected'].to_csv(csv_path, index=False)
    return csv_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse a ZDPlasKin species-density output file.')
    parser.add_argument('output_file', help='Path to the ZDPlasKin output text file')
    parser.add_argument('--csv', help='Optional CSV export path')
    args = parser.parse_args()
    parsed = parse_zdplaskin_output(args.output_file)
    print('Parsed rows:', len(parsed['data_frame']))
    print('Columns:', parsed['data_frame'].columns.tolist())
    if args.csv:
        csv_path = save_csv(parsed, args.csv)
        print('Saved CSV to', csv_path)
