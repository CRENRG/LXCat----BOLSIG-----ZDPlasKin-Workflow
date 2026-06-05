import argparse
import csv
import os
import re
from pathlib import Path

import pandas as pd


def parse_bolsig_output(output_path):
    output_path = Path(output_path)
    if not output_path.exists():
        raise FileNotFoundError(f'BOLSIG+ output file not found: {output_path}')

    raw = output_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    eedf_mode = False
    eedf_rows = []
    coefficients = []
    transport = []
    summary = []
    current_process = None

    for idx, line in enumerate(raw):
        text = line.strip()
        if not text:
            eedf_mode = False
            continue

        process_match = re.match(r'^(C\d+)\s+(.+)$', text)
        if process_match and 'Input cross section' not in text:
            current_process = re.sub(r'\s+', ' ', text).strip()
            continue

        if text.startswith('E/N (Td)') and idx + 1 < len(raw):
            name = text.split('\t', 1)[1].strip() if '\t' in text else text.replace('E/N (Td)', '').strip()
            next_text = raw[idx + 1].strip()
            parts = re.split(r'\s+', next_text)
            if len(parts) >= 2:
                try:
                    value = float(parts[1])
                except ValueError:
                    value = None
                if value is not None:
                    entry = {'parameter': name, 'value': value, 'reduced_field_td': float(parts[0])}
                    if 'rate coefficient' in name.lower():
                        entry['process'] = current_process or 'Unspecified process'
                        coefficients.append(entry)
                    elif any(token in name.lower() for token in ('mean energy', 'mobility', 'diffusion', 'drift', 'frequency', 'power', 'maximum energy')):
                        transport.append(entry)
                    else:
                        summary.append({'name': name, 'value': value})
            continue

        if 'EEDF' in text.upper() or 'DISTRIBUTION' in text.upper():
            eedf_mode = True
            continue

        if eedf_mode:
            parts = re.split(r'\s+', text)
            if len(parts) >= 2:
                try:
                    eedf_rows.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
            continue

        rate_match = re.search(r'([A-Za-z ]+?):\s*([0-9Ee.+-]+)', text)
        if rate_match:
            name = rate_match.group(1).strip()
            value = rate_match.group(2).strip()
            summary.append({'name': name, 'value': value})
            if 'mobility' in name.lower() or 'diffusion' in name.lower():
                transport.append({'parameter': name, 'value': value})
            elif 'rate' in name.lower() or 'coefficient' in name.lower():
                coefficients.append({'parameter': name, 'value': value})
            continue

    if eedf_rows:
        eedf_df = pd.DataFrame(eedf_rows, columns=['energy', 'eedf'])
    else:
        eedf_df = pd.DataFrame(columns=['energy', 'eedf'])

    transport_df = pd.DataFrame(transport)
    rate_df = pd.DataFrame(coefficients)
    summary_df = pd.DataFrame(summary)

    return {
        'raw_lines': raw,
        'summary': summary_df,
        'eedf': eedf_df,
        'transport': transport_df,
        'rates': rate_df,
    }


def save_csv(parsed, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['section', 'name', 'value'])
        for df_name in ('summary', 'transport', 'rates'):
            df = parsed.get(df_name)
            if df is not None and not df.empty:
                for row in df.itertuples(index=False):
                    writer.writerow([df_name, getattr(row, 'name', getattr(row, 'parameter', '')), getattr(row, 'value', '')])
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse a BOLSIG+ output file and export CSV summaries.')
    parser.add_argument('output_file', help='Path to the BOLSIG+ output text file')
    parser.add_argument('--csv', help='Optional CSV file to write parsed summary')
    args = parser.parse_args()
    parsed = parse_bolsig_output(args.output_file)
    print('Parsed BOLSIG+ output:')
    if not parsed['summary'].empty:
        print(parsed['summary'].to_string(index=False))
    if not parsed['transport'].empty:
        print('\nTransport coefficients:')
        print(parsed['transport'].to_string(index=False))
    if not parsed['rates'].empty:
        print('\nRate coefficients:')
        print(parsed['rates'].to_string(index=False))
    if args.csv:
        save_path = save_csv(parsed, args.csv)
        print('Saved CSV to', save_path)
