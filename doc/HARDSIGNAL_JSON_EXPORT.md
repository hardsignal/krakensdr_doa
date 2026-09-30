# Hardsignal local JSON snapshot

`SignalProcessor.run()` calls `wr_hardsignal_json()` once after the existing XML
write in the qualifying output block (`data_ready` and nonempty result list).
It does not depend on CSV recording being enabled or its recording interval.
Existing output behavior is unchanged; failures before this call remain ordinary
Kraken behavior. No historical STAGE, DOA_GATE, or TRACE instrumentation is used.

`_share/hardsignal_live.json` is a live local snapshot, **not evidentiary storage**.
Consumers must check timestamp freshness: no qualifying result or failed export
leaves the previous snapshot in place. Publication uses a closed temporary file
in `_share` followed by `os.replace()`. Readers see complete old/new files; this
is not a power-loss durability guarantee. No fsync or history is provided.

All metrics use numeric JSON types. `tStamp` copies the receiver's integer Unix
epoch timestamp (the existing application uses milliseconds); this does not
certify receiver clock accuracy. `freq` is the receiver frequency in Hz.
`radioBearing` uses the CSV/app convention **360 - theta_0**, in degrees, without
modulo: theta_0=0 exports 360. `bearingConvention` labels this explicitly.
This differs from the historical experimental JSON's internal theta_0 convention
and string-valued bearing/confidence/power. Confidence and power now retain their
stored numeric precision instead of display rounding.

`resultIndex` is always 0: the first accepted result, **not necessarily configured
VFO 0**. Other results are not exported. Empty or unequal result-list lengths
reject the snapshot; SNR/source-count lists may otherwise include estimates
rejected before a bearing was appended. This check does not repair upstream lists.

`conf` is the receiver DoA PAPR metric, not a probability. `power` is the stored
receiver log-power metric, including existing upstream clipping. `snr_db` is the
receiver's SNR estimate. `num_corr_sources` is its matrix-rank-deficiency result,
not an established count of transmitters. These metrics are not calibrated
physical quantities. `doaArray` preserves internal bin order and the existing
offset `abs(min(spectrum))`; bin indices must not be assumed to be exported
bearings. No source/transmitter identity, classification, or interpretation claim
is made.

Serialization rejects NaN/Infinity (`allow_nan=False`). Ordinary conversion,
serialization, and I/O exceptions are contained locally and logged as warnings.
Temporary-file cleanup is attempted on failure; cleanup errors are also contained.
Repeated failures can produce repeated warnings. Process termination or an
unlink failure may leave a temporary file. Previous published JSON is preserved
when publication fails. Shutdown exceptions are not swallowed.

## Local permissions and deployment assumption

`shared_path` is already imported by the processor and resolves to the checkout's
`_share`, which the normal launcher creates. No directory is created by this
optional exporter. The launcher runs the Python process as its invoking user.
At implementation time no Kraken writer/reader process was running; the original
snapshot was owned by `maciejduranczyk:maciejduranczyk` with mode 0644. No explicit
in-repository consumer was found; the launcher's data server serves `_share`
generically. The intended external reader account remains unconfirmed.

This implementation assumes an owner-account local reader. NamedTemporaryFile
creates mode **0600**, and replacement retains 0600 even over an existing 0644
file. Tests verify both modes, ownership, and owner readability on the actual
filesystem. No chmod, global permission change, or assumed group access is added.
Before deployment to a different reader account, identify that account and test
a narrowly scoped group/ACL policy; do not enable world-write access. This file
can also be exposed by the existing shared-directory server, so file mode alone
is not a network-access policy.

## Hardware-free verification

From the isolated checkout, with Python 3.9+ and NumPy installed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s research/tpms/2026-09-30-position-ab/tests -v
git diff --check
```

Focused tests compile the actual method AST with real NumPy and standard-library
I/O, without importing or initializing the hardware stack. They execute the
actual qualifying guard with a mock exporter and verify that removing the new
method/import/call restores the base commit's AST (`86528c0`). The baseline is
pinned so committing this candidate does not invalidate the check. This is not a
hardware integration test; deliberate future processor changes require review
of the pinned preservation check.

## Hardware integration validation — 2026-10-01

Validated on KrakenSDR hardware using an owned Autel MX-Sensor.

Observed:
- Kraken DAQ healthy after startup transient cleared.
- Frequency: 433868160 Hz.
- Hardsignal JSON snapshot created during a qualifying DoA burst.
- Output file mode: 0600.
- Local HTTP data server returned HTTP 200 for `hardsignal_live.json`.
- Served JSON contained the expected numeric fields, resultIndex=0, and
  bearingConvention=`csv_app_360_minus_theta_0_deg`.
- No `Hardsignal JSON export failed` warnings were observed.

This validates local publication and serving behavior for the tested setup.
It does not establish calibrated bearing accuracy, transmitter identity,
or operation under every multi-VFO/runtime configuration.
