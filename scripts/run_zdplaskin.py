import argparse
import os
import subprocess
from pathlib import Path


def find_kinet_file(case_path):
    case_path = Path(case_path)
    if case_path.is_file() and case_path.name.lower().endswith('.inp'):
        return case_path
    if case_path.is_dir():
        candidate = case_path / 'kinet.inp'
        if candidate.exists():
            return candidate
        candidates = list(case_path.glob('*.inp'))
        if candidates:
            return candidates[0]
    raise FileNotFoundError(f'No ZDPlasKin case input file found at {case_path}')


def run_zdplaskin(zdplaskin_executable, case_path, work_dir=None, timeout=300):
    zdplaskin_executable = Path(zdplaskin_executable)
    if not zdplaskin_executable.exists():
        raise FileNotFoundError(f'ZDPlasKin executable not found at {zdplaskin_executable}')

    case_file = find_kinet_file(case_path)
    cwd = Path(work_dir or case_file.parent)
    cmd = [str(zdplaskin_executable), str(case_file)]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr, cwd


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run an existing ZDPlasKin case folder or input file.')
    parser.add_argument('--zdplaskin', required=True, help='Path to the ZDPlasKin executable')
    parser.add_argument('--case', required=True, help='Path to a ZDPlasKin case directory or kinet.inp file')
    args = parser.parse_args()
    code, out, err, cwd = run_zdplaskin(args.zdplaskin, args.case)
    print('RETURN_CODE', code)
    print('CWD', cwd)
    if out:
        print('STDOUT')
        print(out)
    if err:
        print('STDERR')
        print(err)
