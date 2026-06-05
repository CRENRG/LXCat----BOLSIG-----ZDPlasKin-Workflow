import argparse
import os
import subprocess
from pathlib import Path


KB_J_PER_K = 1.380649e-23
TORR_TO_PA = 133.322368


def gas_density_from_pressure(pressure_torr=5.0, gas_temperature_k=300.0):
    return float(pressure_torr) * TORR_TO_PA / (KB_J_PER_K * float(gas_temperature_k))


def write_bolsig_collision_table(rows, out_path, species='D2', mass_ratio=2.724e-4, collision_type='EFFECTIVE', max_points=1500):
    """Write a simple BOLSIG+ collision table from clean numeric rows."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = []
    for energy, cross_section in rows:
        try:
            energy = float(energy)
            cross_section = float(cross_section)
        except (TypeError, ValueError):
            continue
        if energy >= 0 and cross_section >= 0:
            cleaned.append((energy, cross_section))
    if len(cleaned) < 2:
        raise ValueError("At least two nonnegative energy/cross-section rows are required for BOLSIG+.")
    cleaned = sorted(cleaned, key=lambda row: row[0])
    if max_points and len(cleaned) > max_points:
        final_row = cleaned[-1]
        step = max(1, len(cleaned) // max_points)
        cleaned = cleaned[::step]
        if cleaned[-1] != final_row:
            cleaned.append(final_row)
    with out_path.open('w', encoding='utf-8') as f:
        f.write(f'{collision_type}\n')
        f.write(f'{species}\n')
        f.write(f'{mass_ratio:.8e} / mass ratio\n')
        f.write('COMMENT: Generated from parsed LXCat numeric table\n')
        f.write('------\n')
        last_energy = None
        for energy, cross_section in cleaned:
            if last_energy is not None and energy == last_energy:
                continue
            f.write(f'{energy:.8e} {cross_section:.8e}\n')
            last_energy = energy
        f.write('------\n')
    return out_path


def make_bolsig_script(
    collision_file,
    script_path,
    output_name='bolsig_output.dat',
    species='Ar',
    reduced_field_td=150.0,
    gas_temperature_k=300.0,
    pressure_torr=5.0,
):
    script_path = Path(script_path)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    gas_density = gas_density_from_pressure(pressure_torr, gas_temperature_k)
    contents = [
        '/NOSCREEN',
        '/NOLOGFILE',
        'READCOLLISIONS',
        f'{collision_file}   / File',
        f'{species}                  / Species',
        '1                    / Extrapolate: 0= No 1= Yes',
        '',
        'CONDITIONS',
        f'{float(reduced_field_td):.8e}',
        '0.0',
        '0.0',
        f'{float(gas_temperature_k):.8e}',
        f'{float(gas_temperature_k):.8e}',
        '0.0',
        '0',
        f'{gas_density:.15e}',
        '1.0',
        '1',
        '3',
        '1',
        '3',
        '0.0',
        '400',
        '0',
        '200.0',
        '1e-10',
        '1e-4',
        '1000',
        '1.0',
        '1',
        '',
        'RUN',
        '',
        'SAVERESULTS',
        f'{output_name}        / File',
        '4        / Format: 1=Run by run; 2=Combined; 3=Separate; 4=E/N; 5=Energy; 6=SIGLO; 7=PLASIMO',
        '1        / Conditions: 0=No; 1=Yes',
        '1        / Transport coefficients: 0=No; 1=Yes',
        '1        / Rate coefficients: 0=No; 1=Yes',
        '0        / Reverse rate coefficients: 0=No; 1=Yes',
        '0        / Energy loss coefficients: 0=No; 1=Yes',
        '1        / Distribution function: 0=No; 1=Yes',
        '0        / Skip failed runs: 0=No; 1=Yes',
        '1        / Include cross sections: 0=No; 1=Yes',
    ]
    script_path.write_text('\n'.join(contents) + '\n', encoding='utf-8')
    return script_path


def run_bolsig(bolsig_executable, script_path, work_dir=None, timeout=120):
    bolsig_executable = Path(bolsig_executable)
    script_path = Path(script_path)
    if not bolsig_executable.exists():
        raise FileNotFoundError(f'BOLSIG+ executable not found at {bolsig_executable}')
    if not script_path.exists():
        raise FileNotFoundError(f'BOLSIG+ script file not found at {script_path}')

    work_dir = Path(work_dir or script_path.parent)
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(bolsig_executable.resolve()), script_path.name]
    try:
        result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, input='\n', timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        # Provide helpful diagnostic text so the user can run the command manually
        abs_exe = Path(bolsig_executable).resolve()
        abs_script = Path(work_dir or Path(script_path).parent) / Path(script_path).name
        msg = (
            f"BOLSIG+ did not finish within {timeout} seconds.\n"
            "You can try running it manually to see interactive prompts or errors:\n"
            f"PowerShell:\n& \"{abs_exe}\" {abs_script.name} (run from {abs_script.parent})\n"
            f"Command Prompt:\n\"{abs_exe}\" {abs_script.name} (run from {abs_script.parent})\n"
        )
        return -1, '', msg


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run BOLSIG+ with a generated input script.')
    parser.add_argument('--bolsig', required=True, help='Path to the BOLSIG+ executable')
    parser.add_argument('--collision-file', required=True, help='Path to the collision cross section file')
    parser.add_argument('--output-dir', default='.', help='Directory where BOLSIG+ will run and write output')
    parser.add_argument('--output-name', default='bolsig_output.dat', help='Name of the BOLSIG+ output file')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout in seconds for BOLSIG+ run')
    parser.add_argument('--species', default='Ar', help='Species name to pass to BOLSIG+')
    parser.add_argument('--reduced-field-td', type=float, default=150.0, help='Reduced electric field E/N in Td')
    parser.add_argument('--gas-temperature-k', type=float, default=300.0, help='Gas temperature in K')
    parser.add_argument('--pressure-torr', type=float, default=5.0, help='Pressure in torr')
    args = parser.parse_args()
    script_path = Path(args.output_dir) / 'bolsig_input.dat'
    # ensure the script references only the collision filename (not a long path)
    collision_name = Path(args.collision_file).name
    make_bolsig_script(
        collision_name,
        script_path,
        output_name=args.output_name,
        species=args.species,
        reduced_field_td=args.reduced_field_td,
        gas_temperature_k=args.gas_temperature_k,
        pressure_torr=args.pressure_torr,
    )
    code, out, err = run_bolsig(args.bolsig, script_path, work_dir=args.output_dir, timeout=args.timeout)
    print('RETURN_CODE', code)
    if out:
        print('STDOUT')
        print(out)
    if err:
        print('STDERR')
        print(err)
