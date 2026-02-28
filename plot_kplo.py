#!/usr/bin/env python3
"""KPLO/Danuri Doppler — full pass and active tracking window."""

import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta


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
            base = datetime(int(year), 1, 1, tzinfo=timezone.utc) + timedelta(days=int(doy) - 1)
            t = base.replace(hour=int(hh), minute=int(mm), second=0) + \
                timedelta(seconds=int(ss) + (float('0.' + frac) if frac else 0.0))
            times.append(t)
            freqs.append(float(m.group(2)))
    return times, freqs


times, freqs = parse_tdm('examples/kplo_20260221.tdm')

active_t = [t for t, f in zip(times, freqs) if abs(f) > 10]
active_f = [f for t, f in zip(times, freqs) if abs(f) > 10]

# -- Plot --------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('KPLO/Danuri Doppler — 2026-02-21, SP5LOT\n'
             'IQ recorded by SQ3DHO, processed by SP5LOT with iq-to-tdm',
             fontsize=12, fontweight='bold')

# -- Left: full pass ---------------------------------------------------------
# Replace zeros with NaN to avoid vertical lines at signal transitions
import math
freqs_nan = [f if abs(f) > 10 else math.nan for f in freqs]
ax1.plot(times, freqs_nan, color='steelblue', linewidth=1.2)
ax1.set_title('Full pass — 6851 measurements\n(15:19–17:13 UTC)', fontsize=11)
ax1.set_xlabel('UTC')
ax1.set_ylabel('Doppler offset [Hz]')
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax1.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 10)))
ax1.tick_params(axis='x', rotation=30)
ax1.grid(True, alpha=0.35)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:+.0f}'))

# highlight active signal window
ax1.axvspan(active_t[0], active_t[-1], alpha=0.08, color='orange', label='Active signal')
ax1.legend(fontsize=9)

# -- Right: active tracking window -------------------------------------------
ax2.plot(active_t, active_f, color='darkorange', linewidth=1.0)
ax2.set_title(f'Active tracking — {len(active_t)} measurements\n'
              f'(15:47–17:05 UTC)', fontsize=11)
ax2.set_xlabel('UTC')
ax2.set_ylabel('Doppler offset [Hz]')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax2.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 10)))
ax2.tick_params(axis='x', rotation=30)
ax2.grid(True, alpha=0.35)
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:+.0f}'))

# drift annotations
ax2.annotate(f'{active_f[0]:+.0f} Hz',
             xy=(active_t[0], active_f[0]),
             xytext=(15, -20), textcoords='offset points',
             fontsize=9, color='darkorange',
             arrowprops=dict(arrowstyle='->', color='darkorange', lw=1.2))
ax2.annotate(f'{active_f[-1]:+.0f} Hz',
             xy=(active_t[-1], active_f[-1]),
             xytext=(-70, 15), textcoords='offset points',
             fontsize=9, color='darkorange',
             arrowprops=dict(arrowstyle='->', color='darkorange', lw=1.2))

plt.tight_layout()
out = 'kplo_doppler.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f'Saved: {out}')
