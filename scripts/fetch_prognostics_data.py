"""Fetch the NASA C-MAPSS turbofan degradation data into the local cache.

Idempotent. The raw archive is ~12 MB and stays out of the repo; only the trained
model and the measured results are committed.
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

CACHE = Path.home() / ".cache" / "prognostics"
CMAPSS = CACHE / "cmapss"
URL = (
    "https://phm-datasets.s3.amazonaws.com/NASA/"
    "6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
)

EXPECTED = [f"{kind}_FD00{i}.txt" for i in (1, 2, 3, 4) for kind in ("train", "test", "RUL")]


def already_present() -> bool:
    return CMAPSS.exists() and all((CMAPSS / f).exists() for f in EXPECTED)


def main() -> int:
    if already_present():
        print(f"C-MAPSS already in {CMAPSS}")
        return 0

    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    blob = urllib.request.urlopen(URL, timeout=180).read()
    print(f"  {len(blob) / 1e6:.1f} MB")

    outer = zipfile.ZipFile(io.BytesIO(blob))
    inner_name = next(n for n in outer.namelist() if n.endswith("CMAPSSData.zip"))
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
    inner.extractall(CMAPSS)

    missing = [f for f in EXPECTED if not (CMAPSS / f).exists()]
    if missing:
        print(f"ERROR: missing after extract: {missing}", file=sys.stderr)
        return 1

    print(f"extracted to {CMAPSS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
