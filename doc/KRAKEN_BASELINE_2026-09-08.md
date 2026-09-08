# KrakenSDR Baseline — 2026-09-08

Known-good KrakenSDR + GPS configuration after DAQ/GUI debugging.

- 5× RTL-SDR detected and DAQ chain running
- Shared-memory DAQ chain stable
- Delay synchronizer and HWC running without errors
- GUI running on port 8080
- Data server running on port 8081
- Kraken Python 3.9 environment required for GUI
- gpsd 3.25 + u-blox GPS verified on `/dev/ttyACM0`
- Valid 3D GPS fix with ~19 satellites during outdoor test
- GPS is now part of the Kraken measurement baseline
- 6th antenna remains a separate single-RTL reference system

## Recovery

A clean `daq_stop.sh` → `daq_start_sm.sh` cycle resolved the
shared-memory/FIFO startup failure.

`gui_run.sh` was updated to explicitly use the Kraken Python environment.

**Status: KNOWN-GOOD BASELINE**
