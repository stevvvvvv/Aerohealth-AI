"""Download the NASA C-MAPSS turbofan dataset (12 text files, ~45 MB).

Original source: NASA Prognostics Center of Excellence data repository
(https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/).
A plain-text GitHub mirror is used here for a scriptable download.

Usage:  python -m scripts.download_data
"""
from __future__ import annotations

import urllib.request

from aerohealth import config

MIRROR = "https://raw.githubusercontent.com/hankroark/Turbofan-Engine-Degradation/master/CMAPSSData"


def main() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for kind in ("train", "test", "RUL"):
        for ds in config.DATASET_INFO:
            name = f"{kind}_{ds}.txt"
            target = config.DATA_DIR / name
            if target.exists():
                continue
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(f"{MIRROR}/{name}", target)
    print(f"C-MAPSS ready in {config.DATA_DIR}")


if __name__ == "__main__":
    main()
