# iq-to-tdm

Convert SDR IQ recordings (SigMF / GQRX) to NASA CCSDS TDM v2.0 Doppler tracking files.

Designed for amateur radio stations participating in NASA Artemis and lunar mission tracking (KPLO/Danuri, Artemis I/II).

---

## Features

- Reads **SigMF** (`.sigmf-meta` + `.sigmf-data`) and **GQRX** raw recordings
- Supported IQ formats: `cf32_le`, `cf64_le`, `ci16_le`, `ci8`, `cu8`
- Weak-signal carrier detection via **Welch averaged periodogram** + parabolic sub-bin interpolation
- Outputs **CCSDS TDM v2.0 KVN** (`RECEIVE_FREQ_2`) — ready for submission to NASA
- Memory-mapped I/O for files >2 GB (`np.memmap`)
- Optional carrier hint + narrow search window (`--carrier-hint`, `--hint-bw`) for recordings with nearby sidebands
- Optional Welch spectrum plot (`--plot`)

---

## Requirements

```
python >= 3.9
numpy >= 1.24
scipy >= 1.10
matplotlib >= 3.7   # optional, only for --plot
```

Install:

```bash
pip install -r requirements.txt
```

---

## Quick Start

### SigMF recording (e.g. CAMRAS Artemis I)

```bash
python iq_to_tdm.py \
  --input  camras-2022_12_01_21_42_38_2216.500MHz_2.0Msps_ci16_le.sigmf-meta \
  --station MY_CALLSIGN \
  --participant-1 ORION \
  --integration 1.0 \
  --output my_station_20221201.tdm
```

### GQRX recording (e.g. KPLO / Danuri)

```bash
python iq_to_tdm.py \
  --input  examples/gqrx_20260221_151916_2260790300_125000_fc.sigmf-meta \
  --station SP5LOT \
  --participant-1 KPLO \
  --integration 1.0 \
  --output SP5LOT_KPLO_20260221.tdm
```

See [`examples/kplo_20260221.tdm`](examples/kplo_20260221.tdm) for the actual output (6851 measurements, 1h 54min).

### Weak signal with sideband interference (CAMRAS / Artemis I)

Use `--carrier-hint` (offset from center in Hz) and `--hint-bw` to narrow the search window:

```bash
python iq_to_tdm.py \
  --input  examples/small.sigmf-meta \
  --station MY_CALLSIGN \
  --integration 0.3 \
  --carrier-hint -45617 \
  --hint-bw 15000 \
  --output artemis_small.tdm
```

See [`examples/generated_small.tdm`](examples/generated_small.tdm) for the actual output.

---

## All Options

```
--input,   -i   .sigmf-meta or GQRX .sigmf-meta / raw file  [required]
--station, -s   Your station name / callsign               [required]
--output,  -o   Output TDM filename (auto-generated if omitted)
--participant-1  Spacecraft name: ORION, KPLO, etc.        [default: ORION]
--originator     Originator field in TDM header            [default: station]
--dsn-station    DSN uplink station (3-way mode, e.g. DSS-26)
--integration    Integration interval in seconds           [default: 1.0]
--fft-size       FFT size                                  [default: 65536]
--welch-sub      Number of Welch sub-blocks                [default: 20]
--min-snr        Minimum SNR to accept a measurement [dB]  [default: 3.0]
--search-bw      Carrier search bandwidth [Hz]
--carrier-hint   Approximate carrier offset from center [Hz]
--hint-bw        Half-bandwidth around carrier-hint [Hz]   [default: 50000]
--no-excl-sidebands  Do not exclude sideband regions
--max-samples    Load only N samples (for testing on large files)
--freq           Override center frequency [Hz]
--rate           Override sample rate [Sps]
--start          Override recording start time (ISO-8601 UTC)
--dtype          Override IQ data type
--plot           Save Welch spectrum to PNG (requires matplotlib)
--comment        Custom COMMENT line in TDM header
```

---

## Output Format

Standard CCSDS TDM v2.0 KVN:

```
CCSDS_TDM_VERS = 2.0
CREATION_DATE  = 2026-052T15:19:17.000Z
ORIGINATOR     = SP5LOT

COMMENT Artemis II one-way Doppler tracking
COMMENT Source: gqrx_20260221_151916_2260790300_125000_fc.sigmf-meta
COMMENT HW: HackRF One | FFT=65536 Welch=20 int=1.0s

META_START
TIME_SYSTEM            = UTC
PARTICIPANT_1          = KPLO
PARTICIPANT_2          = SP5LOT
MODE                   = SEQUENTIAL
PATH                   = 1,2
INTEGRATION_INTERVAL   = 1.0
INTEGRATION_REF        = END
FREQ_OFFSET            = 2260790300.0
START_TIME             = 2026-052T15:19:17.687
STOP_TIME              = 2026-052T17:13:27.687
TURNAROUND_NUMERATOR   = 240
TURNAROUND_DENOMINATOR = 221
META_STOP

DATA_START
RECEIVE_FREQ_2 = 2026-052T15:19:17.687  +0.000
RECEIVE_FREQ_2 = 2026-052T15:19:18.687  +34287.441
...
DATA_STOP
```

---

## Real Results

### KPLO / Danuri — SP5LOT, 2026-02-21

Recording: 1h 54min, HackRF One, 125 kSps, center 2260.7903 MHz.

| Phase | UTC | Doppler offset |
|-------|-----|---------------|
| Near zero | 15:19 – 15:49 | ~0 Hz |
| Drift | 15:49 – 17:03 | +34400 → +27979 Hz |
| Near zero | 17:03 – 17:13 | ~0 Hz |

6851 measurements, integration 1.0 s, SNR 7–12 dB.

### Artemis I — CAMRAS reference validation

`small.sigmf-meta` (DRO departure burn, 2022-12-01, 2.0 Msps, 0.625s):

| Window | Our result | CAMRAS reference | Δ |
|--------|-----------|-----------------|---|
| T+0.3s | −45627.529 Hz | −45627.5 Hz | ~0 Hz |
| T+0.6s | −45627.549 Hz | −45627.5 Hz | ~0 Hz |

Used: `--carrier-hint -45617 --hint-bw 15000 --integration 0.3`
(PCM/NRZ sideband at −22890 Hz, Rb ≈ 22.7 kbps)

---

## How It Works

1. Load IQ samples (memory-mapped for files >2 GB)
2. Split into integration windows
3. For each window: Welch averaged periodogram (N sub-blocks → +10·log₁₀(N) dB SNR gain)
4. Parabolic interpolation around FFT peak → sub-bin frequency accuracy
5. SNR check, optional sideband exclusion
6. Write CCSDS TDM v2.0 KVN

---

## License

MIT — see [LICENSE](LICENSE)

## Author

SP5LOT — amateur radio station, Warsaw, Poland
GitHub: [abraxasneo](https://github.com/abraxasneo)
