#!/usr/bin/env python3
"""Synthetic-tone test of the sub-bin frequency estimator in iq_to_tdm.py.

A noise-free complex tone of known frequency is swept across one FFT bin.
The estimator must place it on the correct side of the bin centre and stay
within 0.15 Hz for 7.63 Hz bins (Hann window, log-power interpolation).

Run:  python3 tests/test_parabolic.py
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("iq_to_tdm", HERE.parent / "iq_to_tdm.py")
iq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iq)

SR, N = 500_000, 65_536
BIN = SR / N
LIMIT_HZ = 0.15


def main():
    worst = 0.0
    for off in np.linspace(-0.5, 0.5, 41):
        f = 1000 * BIN + off * BIN
        x = np.exp(2j * np.pi * f * np.arange(N) / SR) * np.hanning(N)
        psd = np.abs(np.fft.fft(x)) ** 2
        k = int(np.argmax(psd))
        err = iq._parabolic(psd, k, N, SR) - f
        worst = max(worst, abs(err))
    print(f"bin {BIN:.2f} Hz, worst error {worst:.3f} Hz (limit {LIMIT_HZ} Hz)")
    if worst > LIMIT_HZ:
        print("FAIL")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
