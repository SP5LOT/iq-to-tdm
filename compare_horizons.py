#!/usr/bin/env python3
"""Compare KPLO TDM vs JPL Horizons range-rate -> Doppler."""

import re
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone, timedelta

CENTER_FREQ = 2_260_790_300.0   # Hz
C_KMS       = 299_792.458       # km/s


def parse_tdm(path):
    times, freqs = [], []
    with open(path) as f:
        for line in f:
            m = re.match(r'RECEIVE_FREQ_2\s*=\s*(\S+)\s+([\d.eE+-]+)', line.strip())
            if not m:
                continue
            ts = re.sub(r'T(\d{2}:\d{2}:\d{2}):(\d+)', r'T\1.\2', m.group(1))
            mp = re.match(r'(\d{4})-(\d{3})T(\d{2}):(\d{2}):(\d{2})(?:[.,](\d+))?', ts)
            if not mp:
                continue
            year, doy, hh, mm, ss, frac = mp.groups()
            base = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy)-1)
            t = base.replace(hour=int(hh), minute=int(mm), second=0) + \
                timedelta(seconds=int(ss) + (float('0.'+frac) if frac else 0.0))
            times.append(t)
            freqs.append(float(m.group(2)))
    return times, freqs


def query_horizons():
    """Fetch KPLO range-rate from JPL Horizons for SQ3DHO observer location."""
    params = {
        'format':       'json',
        'COMMAND':      "'-155'",
        'OBJ_DATA':     "'NO'",
        'MAKE_EPHEM':   "'YES'",
        'TABLE_TYPE':   "'OBSERVER'",
        'CENTER':       "'coord@399'",
        'COORD_TYPE':   "'GEODETIC'",
        'SITE_COORD':   "'16.6752,52.3699,0.07'",
        'START_TIME':   "'2026-02-21 15:47'",
        'STOP_TIME':    "'2026-02-21 17:06'",
        'STEP_SIZE':    "'1m'",
        'QUANTITIES':   "'20'",
        'CAL_FORMAT':   "'CAL'",
        'TIME_DIGITS':  "'MINUTES'",
    }
    url = 'https://ssd.jpl.nasa.gov/api/horizons.api?' + \
          urllib.parse.urlencode(params)
    print("Querying JPL Horizons...")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode())

    result = data.get('result', '')

    # Parse table rows: $$SOE ... $$EOE
    rows = []
    in_data = False
    for line in result.splitlines():
        if '$$SOE' in line:
            in_data = True
            continue
        if '$$EOE' in line:
            break
        if not in_data:
            continue
        # Format: " 2026-Feb-21 15:47 *m  0.002...  -0.274..."  (delta_AU, deldot km/s)
        m = re.match(
            r'\s*(\d{4}-\w{3}-\d{2}\s+\d{2}:\d{2})'
            r'\s+\S+\s+([\d.]+)\s+([-\d.]+)',
            line
        )
        if m:
            dt = datetime.strptime(m.group(1), '%Y-%b-%d %H:%M').replace(tzinfo=timezone.utc)
            delta_au = float(m.group(2))
            deldot   = float(m.group(3))   # km/s, positive = receding
            rows.append((dt, delta_au, deldot))

    print(f"Fetched {len(rows)} rows from Horizons")
    return rows


def main():
    # -- Load TDM -------------------------------------------------------------
    tdm_times, tdm_freqs = parse_tdm('examples/kplo_20260221.tdm')
    active = [(t, f) for t, f in zip(tdm_times, tdm_freqs) if abs(f) > 10]
    print(f"TDM active measurements: {len(active)}")

    # -- Fetch Horizons -------------------------------------------------------
    hor = query_horizons()
    if not hor:
        print("No Horizons data!")
        return

    # -- Convert deldot -> Doppler offset -------------------------------------
    # deldot > 0 -> receding -> f_received < f_center -> negative offset
    # deldot < 0 -> approaching -> f_received > f_center -> positive offset
    hor_dop = [(t, -deldot * CENTER_FREQ / C_KMS) for t, _, deldot in hor]

    print("\n--- First 5 Horizons rows -> Doppler ---")
    for t, d in hor_dop[:5]:
        print(f"  {t.strftime('%H:%M')} UTC  dop={d:+.1f} Hz")

    # -- Match by time (+-60s) ------------------------------------------------
    pairs = []
    for t_tdm, f_tdm in active:
        best_dt, best_hor = None, None
        for t_h, d_h in hor_dop:
            dt = abs((t_tdm - t_h).total_seconds())
            if dt <= 60 and (best_dt is None or dt < best_dt):
                best_dt = dt
                best_hor = d_h
        if best_hor is not None:
            pairs.append((t_tdm, f_tdm, best_hor, f_tdm - best_hor))

    if not pairs:
        print("No matching pairs found!")
        return

    diffs = [p[3] for p in pairs]
    dc_offset = sum(diffs) / len(diffs)
    residuals = [d - dc_offset for d in diffs]
    rms_residual = (sum(r**2 for r in residuals) / len(residuals)) ** 0.5

    print(f"\n--- TDM vs Horizons comparison ({len(pairs)} pairs) ---")
    print(f"  DC offset (TDM - Horizons): {dc_offset:+.1f} Hz")
    print(f"  -> SDR center vs KPLO nominal: {CENTER_FREQ/1e6:.4f} MHz vs "
          f"{(CENTER_FREQ + dc_offset)/1e6:.4f} MHz")
    print(f"  RMS residual after removing DC: {rms_residual:.1f} Hz")
    print(f"\n  First 10 pairs (UTC | TDM | Horizons+DC | residual):")
    for (t, ft, fh, d), r in zip(pairs[:10], residuals[:10]):
        print(f"  {t.strftime('%H:%M:%S')}  TDM={ft:+.1f}  Hor={fh+dc_offset:+.1f}  res={r:+.1f} Hz")

    # -- Plot -----------------------------------------------------------------
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.suptitle('KPLO/Danuri — TDM vs JPL Horizons Doppler\n2026-02-21, SQ3DHO (52.37°N 16.68°E)',
                 fontsize=12, fontweight='bold')

    hor_t = [t for t, d in hor_dop]
    # Horizons shifted by DC offset (SDR center vs KPLO nominal frequency difference)
    hor_f_shifted = [d + dc_offset for t, d in hor_dop]
    ax.plot(hor_t, hor_f_shifted, color='steelblue', linewidth=2.0,
            label=f'JPL Horizons (shifted +{dc_offset:.0f} Hz, SDR tuning offset)')
    ax.plot([t for t, f, _, _ in pairs], [f for _, f, _, _ in pairs],
            color='darkorange', linewidth=1.0, alpha=0.8, label='SQ3DHO TDM (Welch)')

    ax.set_xlabel('UTC')
    ax.set_ylabel(f'Doppler offset from {CENTER_FREQ/1e6:.4f} MHz [Hz]')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 10)))
    ax.tick_params(axis='x', rotation=25)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:+.0f}'))

    ax.text(0.02, 0.05,
            f'SDR tuning offset: {dc_offset:+.0f} Hz  |  RMS residual: {rms_residual:.1f} Hz  |  n={len(pairs)}',
            transform=ax.transAxes, fontsize=10,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig('kplo_vs_horizons.png', dpi=150, bbox_inches='tight')
    print("\nSaved: kplo_vs_horizons.png")


if __name__ == '__main__':
    main()
