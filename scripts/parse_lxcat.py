import argparse
import re
from pathlib import Path

import pandas as pd


COLLISION_KEYWORDS = ("ELASTIC", "EFFECTIVE", "EXCITATION", "IONIZATION", "ATTACHMENT")


def _is_collision_keyword(text):
    return text.strip().upper() in COLLISION_KEYWORDS


def _is_dash_line(text):
    return bool(re.fullmatch(r"[-\s]{5,}", text.strip()))


def _first_float(text):
    if text is None:
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", str(text))
    return float(match.group(0)) if match else None


def _clean_metadata_key(key):
    return key.strip().lower().replace(".", "").replace(" ", "_")


def _collect_global_metadata(lines):
    metadata = {}
    for line in lines:
        stripped = line.strip()
        if _is_collision_keyword(stripped):
            break
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            clean_key = _clean_metadata_key(key)
            clean_value = value.strip()
            if clean_key and clean_value:
                metadata[clean_key] = clean_value
    return metadata


def _parse_block_metadata(lines):
    metadata = {}
    comments = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            clean_key = _clean_metadata_key(key)
            clean_value = value.strip()
            if clean_key in metadata:
                metadata[clean_key] = f"{metadata[clean_key]} {clean_value}".strip()
            else:
                metadata[clean_key] = clean_value
        else:
            comments.append(stripped)
    if comments:
        metadata["comments"] = " ".join(comments)
    return metadata


def _make_process_label(block):
    process = block.get("process") or block.get("target") or f"Process {block['index'] + 1}"
    process = re.sub(r"\s+", " ", str(process)).strip()
    process = process.replace("E + ", "e + ")
    if len(process) > 92:
        process = f"{process[:89]}..."
    return f"{block.get('collision_type', 'Process').title()}: {process}"


def _fallback_numeric_block(raw_lines, file_path):
    rows = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        pieces = re.split(r"\s+", stripped)
        if len(pieces) < 2:
            continue
        try:
            rows.append((float(pieces[0]), float(pieces[1])))
        except ValueError:
            continue

    if not rows:
        raise ValueError(f"No numeric cross-section table data found in LXCat file: {file_path}")

    df = pd.DataFrame(rows, columns=["energy", "cross_section"])
    block = {
        "index": 0,
        "collision_type": "Unspecified",
        "target": "Unspecified LXCat cross section",
        "parameter": None,
        "threshold_eV": None,
        "mass_ratio": None,
        "process": "Unspecified LXCat cross section",
        "species": "",
        "metadata": {},
        "comments": "",
        "data_frame": df,
        "numeric": rows,
        "preview": df.head(10).values.tolist(),
        "rows": len(df),
        "energy_min": float(df["energy"].min()),
        "energy_max": float(df["energy"].max()),
        "cross_section_min": float(df["cross_section"].min()),
        "cross_section_max": float(df["cross_section"].max()),
    }
    block["label"] = _make_process_label(block)
    return block


def _finalize_block(index, collision_type, target, parameter, metadata_lines, table_rows):
    df = pd.DataFrame(table_rows, columns=["energy", "cross_section"])
    metadata = _parse_block_metadata(metadata_lines)
    parameter_value = _first_float(parameter)
    threshold_eV = parameter_value if collision_type in ("EXCITATION", "IONIZATION") else None
    mass_ratio = parameter_value if collision_type in ("ELASTIC", "EFFECTIVE") else None

    process = metadata.get("process") or target or f"{collision_type.title()} process"
    block = {
        "index": index,
        "collision_type": collision_type,
        "target": target or "",
        "parameter": parameter,
        "threshold_eV": threshold_eV,
        "mass_ratio": mass_ratio,
        "process": process,
        "species": metadata.get("species", ""),
        "metadata": metadata,
        "comments": metadata.get("comments", ""),
        "data_frame": df,
        "numeric": table_rows,
        "preview": df.head(10).values.tolist(),
        "rows": len(df),
        "energy_min": float(df["energy"].min()),
        "energy_max": float(df["energy"].max()),
        "cross_section_min": float(df["cross_section"].min()),
        "cross_section_max": float(df["cross_section"].max()),
    }
    block["label"] = _make_process_label(block)
    return block


def parse_lxcat_file(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"LXCat file not found: {file_path}")

    raw_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    global_metadata = _collect_global_metadata(raw_lines)
    blocks = []
    i = 0

    while i < len(raw_lines):
        stripped = raw_lines[i].strip()
        if not _is_collision_keyword(stripped):
            i += 1
            continue

        collision_type = stripped.upper()
        i += 1

        while i < len(raw_lines) and not raw_lines[i].strip():
            i += 1
        target = raw_lines[i].strip() if i < len(raw_lines) else ""
        i += 1

        parameter = None
        if collision_type != "ATTACHMENT":
            while i < len(raw_lines) and not raw_lines[i].strip():
                i += 1
            if i < len(raw_lines):
                candidate = raw_lines[i].strip()
                if (
                    candidate
                    and not _is_collision_keyword(candidate)
                    and not _is_dash_line(candidate)
                    and ":" not in candidate
                ):
                    parameter = candidate
                    i += 1

        metadata_lines = []
        table_rows = []
        in_table = False

        while i < len(raw_lines):
            line = raw_lines[i].strip()

            if not in_table and _is_collision_keyword(line):
                break

            if _is_dash_line(line):
                if in_table:
                    i += 1
                    break
                in_table = True
                i += 1
                continue

            if in_table:
                parts = re.split(r"\s+", line)
                if len(parts) >= 2:
                    try:
                        table_rows.append((float(parts[0]), float(parts[1])))
                    except ValueError:
                        pass
            else:
                metadata_lines.append(line)

            i += 1

        if table_rows:
            blocks.append(
                _finalize_block(
                    index=len(blocks),
                    collision_type=collision_type,
                    target=target,
                    parameter=parameter,
                    metadata_lines=metadata_lines,
                    table_rows=table_rows,
                )
            )

    if not blocks:
        blocks = [_fallback_numeric_block(raw_lines, file_path)]

    data_frame = blocks[0]["data_frame"] if blocks else pd.DataFrame(columns=["energy", "cross_section"])
    return {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "rows": sum(block["rows"] for block in blocks),
        "processes": [block["label"] for block in blocks],
        "header": None,
        "metadata": global_metadata,
        "preview": blocks[0]["preview"] if blocks else [],
        "data_frame": data_frame,
        "blocks": blocks,
    }


def process_summary_dataframe(summary):
    rows = []
    for block in summary.get("blocks", []):
        rows.append(
            {
                "index": block["index"],
                "type": block["collision_type"].title(),
                "target": block.get("target", ""),
                "process": block.get("process", ""),
                "threshold_eV": block.get("threshold_eV"),
                "rows": block.get("rows", 0),
                "energy_min_eV": block.get("energy_min"),
                "energy_max_eV": block.get("energy_max"),
                "max_cross_section_m2": block.get("cross_section_max"),
            }
        )
    return pd.DataFrame(rows)


def long_cross_section_dataframe(blocks, selected_indices=None, max_points_per_process=None):
    selected = set(selected_indices) if selected_indices is not None else None
    frames = []
    for block in blocks:
        if selected is not None and block["index"] not in selected:
            continue
        df = block["data_frame"].copy()
        if max_points_per_process and len(df) > max_points_per_process:
            step = max(1, len(df) // max_points_per_process)
            df = df.iloc[::step, :].copy()
        df["process"] = block["label"]
        df["process_index"] = block["index"]
        df["collision_type"] = block["collision_type"].title()
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["energy", "cross_section", "process", "process_index", "collision_type"])
    return pd.concat(frames, ignore_index=True)


def save_lxcat_preview(file_path, csv_path):
    summary = parse_lxcat_file(file_path)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    process_summary_dataframe(summary).to_csv(csv_path, index=False)
    return csv_path


def export_for_bolsig(file_path, out_path):
    """Export the largest numeric process table as a two-column collision table."""
    summary = parse_lxcat_file(file_path)
    blocks = summary.get("blocks", [])
    if not blocks:
        raise ValueError("No process blocks available for export.")
    block = max(blocks, key=lambda item: item.get("rows", 0))
    return export_block_for_bolsig(file_path, block["index"], out_path)


def export_block_for_bolsig(file_path, block_index, out_path):
    summary = parse_lxcat_file(file_path)
    blocks = summary.get("blocks", [])
    if not blocks:
        raise ValueError("No blocks available in LXCat file to export.")
    if block_index < 0 or block_index >= len(blocks):
        raise IndexError("Block index out of range.")

    df = blocks[block_index]["data_frame"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, sep=" ", header=False, index=False, float_format="%.8e")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse LXCat cross-section text files.")
    parser.add_argument("lxcat_file", help="Path to an LXCat cross-section file (.txt)")
    parser.add_argument("--csv", help="Optional CSV output path for the process summary")
    args = parser.parse_args()

    parsed = parse_lxcat_file(args.lxcat_file)
    print("File:", parsed["file_name"])
    print("Rows:", parsed["rows"])
    print("Processes:")
    for process in parsed["processes"][:25]:
        print(" -", process)
    if len(parsed["processes"]) > 25:
        print(f" ... {len(parsed['processes']) - 25} more")
    if args.csv:
        csv_out = save_lxcat_preview(args.lxcat_file, args.csv)
        print("Saved process summary CSV to", csv_out)
