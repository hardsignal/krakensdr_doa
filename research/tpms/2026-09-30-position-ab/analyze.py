"""Read-only, standard-library analysis of the fixed 2026-09-30 experiment."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent


def verify_sources(manifest, base=HERE):
    for source in manifest['sources']:
        path = base / source['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != source['sha256']:
            raise ValueError(f"SHA256 mismatch: {source['path']}")
        if 'recorded_sha256' in source:
            note = (base / source['recorded_hash_note']).read_text(encoding='utf-8')
            match = re.search(r'^SHA256: ([a-f0-9]{64})$', note, re.MULTILINE)
            if not match or match[1] != actual or source['recorded_sha256'] != actual:
                raise ValueError(f"Recorded SHA256 mismatch: {source['path']}")


def read_capture(path):
    """Require the observed headerless 17 metadata + 360 spectrum field schema."""
    rows = []
    with Path(path).open(encoding='utf-8', newline='') as handle:
        reader = csv.reader(handle, skipinitialspace=True, strict=True)
        try:
            for row in reader:
                if len(row) != 377:
                    raise ValueError(f'expected 377 fields, got {len(row)}')
                if any(not value.strip() for value in row):
                    raise ValueError('empty field')
                numeric = [float(row[i]) for i in [0, 1, 2, 3, 4, 6, 8, 9, 10, 11, *range(17, 377)]]
                if not all(math.isfinite(value) for value in numeric):
                    raise ValueError('non-finite numeric field')
                if int(row[0]) < 0 or int(row[4]) != 433868160:
                    raise ValueError('invalid timestamp or unexpected frequency')
                if row[5].strip() != 'UCA' or [v.strip() for v in row[12:17]] != ['GPS', 'R', 'R', 'R', 'R']:
                    raise ValueError('unexpected metadata')
                bearing, confidence, power = map(float, row[1:4])
                if not 0 <= bearing <= 360:
                    raise ValueError('bearing outside [0, 360]')
                rows.append((bearing, confidence, power))
        except (ValueError, csv.Error) as exc:
            raise ValueError(f'{path}: line {reader.line_num}: malformed CSV: {exc}') from exc
    return rows


def summarize(rows):
    names = ['bearing_mean_deg', 'bearing_min_deg', 'bearing_max_deg',
             'bearing_population_std_deg', 'confidence_mean', 'power_mean']
    if not rows:
        return dict(row_count=0, null_capture=True, **dict.fromkeys(names))
    bearings, confidences, powers = zip(*rows)
    values = [statistics.mean(bearings), min(bearings), max(bearings),
              statistics.pstdev(bearings), statistics.mean(confidences), statistics.mean(powers)]
    return dict(row_count=len(rows), null_capture=False, **dict(zip(names, values)))


def analyze(manifest, base=HERE):
    verify_sources(manifest, base)
    trials = []
    a_rows = []
    for source in manifest['sources']:
        if source['kind'] != 'raw_capture':
            continue
        rows = read_capture(base / source['path'])
        if not rows and not source['allow_null']:
            raise ValueError(f"Unexpected empty capture: {source['trial']}")
        trials.append({key: source[key] for key in ['trial', 'position', 'role', 'activations']} | summarize(rows))
        if source['position'] == 'A':
            a_rows.extend(rows)
    trials.sort(key=lambda trial: trial['trial'])
    by_id = {trial['trial']: trial for trial in trials}
    if (by_id['B001']['role'], by_id['B001']['activations']) != ('supplementary_two_activations', 2):
        raise ValueError('B001 must remain supplementary with two activations')
    if manifest['primary_position_b_trials'] != ['B002', 'B003']:
        raise ValueError('Primary Position-B repeats must be B002/B003')
    for trial in ['B002', 'B003']:
        if (by_id[trial]['role'], by_id[trial]['activations']) != ('primary', 1):
            raise ValueError(f'{trial} must be a primary single activation')
    a_trials = [trial for trial in trials if trial['position'] == 'A']
    successes = sum(not trial['null_capture'] for trial in a_trials)
    return {'trials': trials, 'position_a': {
        'attempts': len(a_trials), 'successful_captures': successes,
        'successful_capture_rate': successes / len(a_trials),
        'successful_rows': len(a_rows),
        'bearing_min_deg': min(row[0] for row in a_rows),
        'bearing_max_deg': max(row[0] for row in a_rows)},
        'position_b_primary': {'trials': ['B002', 'B003'],
            'absolute_trial_mean_difference_deg': abs(by_id['B002']['bearing_mean_deg'] - by_id['B003']['bearing_mean_deg'])},
        'position_b_supplementary': ['B001']}


def render(result):
    lines = ['Hardsignal Labs | 2026-09-30 | verified source hashes',
             'trial role activations rows mean_deg min_deg max_deg population_std_deg confidence_mean power_mean']
    for trial in result['trials']:
        values = [trial[key] for key in ['bearing_mean_deg', 'bearing_min_deg', 'bearing_max_deg',
                  'bearing_population_std_deg', 'confidence_mean', 'power_mean']]
        stats = ' '.join('NA' if value is None else f'{value:.6f}' for value in values)
        lines.append(f"{trial['trial']} {trial['role']} {trial['activations']} {trial['row_count']} {stats}" + (' NULL' if trial['null_capture'] else ''))
    a = result['position_a']
    lines.append(f"Position A: {a['successful_captures']}/{a['attempts']} successful captures ({a['successful_capture_rate']:.6f}); {a['successful_rows']} rows; range {a['bearing_min_deg']:.6f}-{a['bearing_max_deg']:.6f} deg")
    lines.append(f"Position B primary: B002/B003; trial mean difference {result['position_b_primary']['absolute_trial_mean_difference_deg']:.6f} deg")
    lines.append('B001: supplementary TWO activations; combined statistics only.')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='print computed statistics as JSON')
    args = parser.parse_args()
    try:
        manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
        result = analyze(manifest)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) if args.json else render(result), end='\n' if args.json else '')
    return 0


if __name__ == '__main__':
    sys.exit(main())
