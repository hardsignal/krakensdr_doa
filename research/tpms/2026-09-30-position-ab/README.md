# Hardsignal Labs: controlled TPMS Position A/B observations

Experiment date: **2026-09-30**. This artifact reproduces descriptive statistics
from the existing KrakenSDR CSV captures. The tested Position-A and Position-B
conditions produced reproducibly different RF/DoA observations in this dataset.

## Objective and controls

Document repeated controlled activation observations at two tested positions,
including unsuccessful capture attempts and the distinction between separate
single-activation trials and multiple activations in one file.

The operator reports the same owned Autel MX-Sensor, the same intended sensor
orientation and height, an unchanged KrakenSDR five-channel array, and unchanged
RF settings. These are experimental setup records, not identity inferred from RF.
The receiver settings were 433868160 Hz, MUSIC, UCA, antenna spacing 0.21 m,
uniform gain 15.7, and manual squelch -45 dB. Phase-1 notes specify a recording
interval of 1 s; this is a configured interval, not a claim of exact row cadence.
Phase 2 records unchanged RF settings but does not separately state its recording
interval.

The controlled change was an approximately 1.0 m lateral sensor displacement
from Position A to Position B. Orientation and height were intended to remain
approximately constant. Exact surveyed coordinates, displacement uncertainty,
absolute reference bearings, and activation-window durations are not documented
in these sources. This package reproduces the analysis; it cannot reconstruct
undocumented physical geometry.

The operator reports that the workstation was rebooted and the Kraken stack
restarted between Position A and Position B. Reported RF settings were checked
after restart and matched the intended baseline. **Position and acquisition run
changed together.** The observations support a descriptive A/B comparison, not
isolation of the effect of the approximately 1 m displacement. This clarification
is recorded in this research package; the original `PHASE2_SUMMARY.txt` remains
unchanged.

## Acquisition procedure and provenance

1. Configure the receiver and intended sensor geometry as recorded above.
2. At Position A, perform five controlled activation attempts, recording each
   attempt to its own CSV. Retain all five files and their acquisition notes,
   including the zero-byte Trial 002 file.
3. Between phases, the workstation was rebooted and the Kraken stack restarted;
   reported RF settings were checked and matched the intended baseline. The
   sensor was moved approximately 1.0 m laterally to Position B with the intended
   orientation and height retained. B001 contains two activations in one file.
4. Acquire B002 and B003 as separate, clean single activations. Use these as the
   primary Position-B single-activation trials. Their separation does not prove
   statistical independence. Preserve B001 as supplementary.
5. Analyze every final recorded row; do not trim, filter, normalize, or infer
   activation boundaries. One row is a receiver observation, not an independent
   activation. No additional capture or transmission is performed by this code.

This procedure describes the supplied records, rather than adding an unrecorded
trigger method or timing protocol. Phase-1 acquisition notes and the two existing
summaries are included in the manifest. Phase-2 setup and activation grouping
come from `tpms_phase2_position_B/PHASE2_SUMMARY.txt` and the operator's supplied
experiment facts; no individual Phase-2 notes were present.

## Phase 1: Position A

| Trial | Rows | Mean bearing (deg) | Observed range (deg) |
| --- | ---: | ---: | --- |
| 001 | 5 | 279.8 | 279–281 |
| 002 | 0 | undefined | null capture |
| 003 | 4 | 277.5 | 277–278 |
| 004 | 4 | 287.25 | 285–288 |
| 005 | 4 | 291.75 | 291–293 |

**Four of five attempted recordings contained DoA rows (4/5, 80%).** There are
**17** recorded rows, spanning **277–293 deg**. Observation windows and manual
stopping times were not identical. This recording-level count is not a
packet-detection probability or calibrated sensitivity. The analysis output's
`successful_captures` and `successful_capture_rate` fields and its “successful
captures” label refer only to recordings containing at least one DoA row.

Trial 002 remains a valid zero-row/null observation in the denominator. Its
statistics are `null` in JSON and `NA` in text. No cause is assigned: the absence
of qualifying written rows does not establish whether a transmission occurred,
was missed, or met receiver gating conditions.

## Phase 2: Position B

| Capture | Role | Activations | Rows | Mean (deg) | Range (deg) | Population std (deg) |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| B001 | supplementary | 2 | 10 | 251.4 | 247–255 | 2.289105 |
| B002 | primary single-activation trial | 1 | 5 | 248.8 | 248–249 | 0.4 |
| B003 | primary single-activation trial | 1 | 5 | 249.2 | 249–250 | 0.4 |

B002 and B003 trial means differ by **0.4 deg**; their rows occupy 248–250 deg.
They are separate single-activation trials, not proof of statistical independence.
Their close agreement describes these observations under the Position-B run.
B001's mean and spread describe its combined two-activation file. It is neither
silently counted as one single-activation trial nor split into inferred trials.
No Position-B capture-success probability is estimated.

## Analysis definitions and scientific boundaries

`analyze.py` uses only the Python standard library. The headerless captures have
377 fields: 17 metadata fields followed by 360 numeric spectrum values. Zero-based
columns 1, 2, and 3 are bearing, receiver confidence, and receiver power. This
mapping was checked by read-only inspection of the local Kraken CSV writer.
Column 0 is timestamp, 4 frequency, and 5 array type. All rows are validated for
field count, nonempty fields, finite numeric fields, bearing range, and expected
frequency/array metadata. A blank line is malformed; a zero-byte file is a null
capture. Only A002 is allowed to be empty in this fixed experiment.

Means are unweighted arithmetic row means. Bearing spread is population standard
deviation (denominator N), not sample standard deviation or an uncertainty of
absolute direction. Arithmetic bearing statistics suit these observed ranges,
which do not cross 0/360; the script is not a general circular-statistics tool.
Confidence is the receiver's recorded metric, not a calibrated probability.
Power mean is an arithmetic mean of recorded power values in their native log
scale, not a mean of converted linear power or a calibrated field-strength claim.
Text shows six decimal places for deterministic presentation, not measurement
precision. JSON retains computed floating-point values; a 0.4 difference may
appear with ordinary binary floating-point rounding.

Interpretation is restricted to the descriptive difference under these tested
conditions in this dataset. The observations do **not** establish:

- true/absolute bearing accuracy or calibration-grade absolute direction;
- transmitter/device identity or RF fingerprint identity;
- that the 1 m displacement caused a particular angular shift;
- multipath, environmental, or propagation causality;
- general classification or discrimination capability.

Multiple CSV rows from one activation are not independent experiments.
The small dataset and intended controls do not support those broader claims.

## Files and integrity

- `manifest.json`: relative source paths, byte-level SHA256 values, source kinds,
  configuration, and explicit activation roles. Paths resolve relative to this
  artifact directory, three levels below the repository root.
- `analyze.py`: read-only hash verification, parsing, statistics, text/JSON output.
- `tests/test_analysis.py`: measurement, null, malformed-input, integrity,
  activation-role, and deterministic-output regression checks.
- `statistics.json`: derived computed statistics and grouping metadata only;
  no raw rows. Reproducible byte-for-byte using `--json`.

The manifest lists eight raw captures, five acquisition notes, and two existing
derived summaries. All five pre-existing capture SHA256 values in Phase-1 notes
were verified before packaging and are retained as evidence. The operator has
also supplied earlier terminal-recorded references for B001, B002, B003, and
`tpms_phase2_position_B/PHASE2_SUMMARY.txt`. All four current files match those
references and the unchanged expected hashes in the manifest. Their provenance is:
**“Earlier terminal-recorded reference supplied by the operator and matched during
packaging.”** These references were not necessarily stored in the source notes;
they are not claimed to be independently timestamped or digitally signed. The
earlier description of these four hashes as new packaging baselines is corrected.
Hashes for the five Phase-1 notes and Phase-1 summary remain newly recorded
packaging baselines. Every analysis run checks all 15 source hashes and
rechecks the five recorded hash statements. A mismatch is an error; the program
never repairs hashes or source files.

Reproduction requires the original source directories. No byte-identical source
copies are included in this package. Raw files stay in their original locations
and are not copied or rewritten. All 15 original sources are currently untracked;
the manifest lists every required raw capture, note, and summary for eventual
backup and version control, including the zero-byte Trial 002. Preserve all of
them together with the package; tracking only this research directory is insufficient.
For transfer, include the manifest-listed sources with the same relative layout;
this directory alone is not a self-contained raw-data archive. Existing summaries
remain derived evidence, distinct from captures. No Kraken application code or
released Sentinel repository is modified by this artifact.

## Exact reproduction and verification commands

Run with Python 3.9 or later (no external dependencies), from the existing checkout:

```sh
cd ~/krakensdr_doa
git status --short
python3 research/tpms/2026-09-30-position-ab/analyze.py
python3 -m unittest discover -s research/tpms/2026-09-30-position-ab/tests -v
python3 -m py_compile research/tpms/2026-09-30-position-ab/analyze.py research/tpms/2026-09-30-position-ab/tests/test_analysis.py
python3 research/tpms/2026-09-30-position-ab/analyze.py --json | diff -u research/tpms/2026-09-30-position-ab/statistics.json -
git diff --check
git status --short
```

The test suite also verifies hashes, compares the derived JSON byte-for-byte,
and checks output from a different working directory. Malformed-input tests use
temporary files, never the original captures. `py_compile` creates only Python
bytecode caches beside the new scripts. `git diff --check` checks tracked changes;
new artifact files should additionally be reviewed while untracked. No command
above creates a commit or changes raw evidence.
