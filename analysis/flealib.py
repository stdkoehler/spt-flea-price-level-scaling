"""Shared helpers for the flea-price-scaling analysis pipeline."""
from pathlib import Path
import numpy as np, pandas as pd

# ---------------------------------------------------------------- paths
ROOT      = Path(__file__).resolve().parents[1]
DATA      = ROOT / "live-data"          # immutable data basis
SNAPSHOTS = DATA / "snapshots"          # 948 raw prices-regular.json blobs
COMMITS   = DATA / "commits.tsv"
REFERENCE = DATA / "reference"          # SPT / tarkov.dev lookup data
OUT       = ROOT / "analysis" / "out"   # derived artefacts + plots
MOD_DATA  = ROOT / "src" / "data"       # what the mod actually ships
DOCS_IMG  = ROOT / "docs" / "img"       # figures embedded by docs/ and README
OUT.mkdir(parents=True, exist_ok=True)
DOCS_IMG.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- source
SOURCE_REPO = "DrakiaXYZ/SPT-LiveFleaPriceDB"
SOURCE_FILE = "prices-regular.json"     # PvE has markedly stronger inflation

# ---------------------------------------------------------------- season
# EFT 1.0 launch (full wipe) -> day before Kord Breach / patch 1.1.0.0
SEASON_START = pd.Timestamp("2025-11-15T11:00:00Z")
SEASON_END   = pd.Timestamp("2026-08-02T23:59:59Z")
SEASON_DAYS  = (SEASON_END - SEASON_START).total_seconds() / 86400

# Usable data range: the scraper went dark Nov 16-22 and Jul 22 - Aug 2.
DATA_DAY_LO, DATA_DAY_HI = 8.0, 249.0

# ---------------------------------------------------------------- mapping
# The shipped table is DAY-indexed, so the mapping below is only the DEFAULT -
# the mod exposes startDay/endDay as configuration.
# The season is spanned from the point the median player reaches the flea
# unlock (~day 10) to the last day with data; below 15 the flea is locked.
FLEA_UNLOCK  = 15
LVL_MAX      = 79
MAP_DAY_LO   = 10.0     # median player reaches level 15 (flea unlock) ~day 10
MAP_DAY_HI   = DATA_DAY_HI

# The season only ran 250 days, in which the live playerbase reached roughly
# level 50-70. So the price series was produced by an economy that never held a
# meaningful population above that, and stretching it to level 79 would assert a
# correspondence the data never had. The trend therefore spans levels 15-60 and
# is HELD FLAT above 60 - past the cap we have no observations, so only the
# fluctuation keeps moving. The 60 is a judgement about live progression, not a
# measurement: the snapshots carry prices, never player levels.
SCALING_MAX  = 60

# Day knots stored in the artefact: every 3 days over the usable range.
# Measured reconstruction error vs a daily curve: median 0.04%, p95 4.0%.
DAY_KNOTS = np.arange(DATA_DAY_LO, DATA_DAY_HI + 1e-9, 3.0)

# Tuned adaptive smoothing window (days) - see 05_tune_filter.py.
# Defined as data, not prose, so the shipped table can state the real values.
WINDOW_BASE, WINDOW_SLOPE, WINDOW_MAX = 5.0, 0.25, 60.0

def window_for(day):
    return np.clip(WINDOW_BASE + WINDOW_SLOPE * np.asarray(day, float),
                   WINDOW_BASE, WINDOW_MAX)

def level_to_day(level):
    lv = np.asarray(level, float)
    frac = np.clip((lv - FLEA_UNLOCK) / (SCALING_MAX - FLEA_UNLOCK), 0, 1)
    return MAP_DAY_LO + frac * (MAP_DAY_HI - MAP_DAY_LO)

def day_to_level(day):
    d = np.asarray(day, float)
    return FLEA_UNLOCK + (d - MAP_DAY_LO) / (MAP_DAY_HI - MAP_DAY_LO) * (SCALING_MAX - FLEA_UNLOCK)

LEVELS = np.arange(1, LVL_MAX + 1)

# ---------------------------------------------------------------- loading
def load():
    """Price matrix: rows = snapshot timestamps, cols = item template ids."""
    d = np.load(OUT / "price_matrix.npz", allow_pickle=True)
    # pandas 3.x stores datetime64 as microseconds - unit MUST be explicit
    ts = pd.to_datetime(d["ts"], unit="us", utc=True)
    df = pd.DataFrame(d["M"], index=ts, columns=d["items"]).sort_index()
    df.index.name = "ts"
    return df

def day_of_season(idx):
    return (idx - SEASON_START).total_seconds() / 86400

def classify(df):
    """core = usable live-traded | pegged = no tarkov.dev data | sparse = rarely listed."""
    stale = (df.diff() == 0).sum() / df.notna().sum()
    cov   = df.notna().mean()
    cls = pd.Series("core", index=df.columns)
    cls[cov < 0.25] = "sparse"
    cls[(stale > 0.95) & (cov >= 0.25)] = "pegged"
    return cls

def names():
    import json
    return json.load(open(REFERENCE / "id_to_name.json", encoding="utf-8"))

# ---------------------------------------------------------------- artefacts
# Some items sit at a sentinel price - very often exactly 1 RUB - for weeks at
# a stretch. A walnut forestock did not trade at one rouble for 30 days; this is
# the feed reporting a floor rather than a market. Because the episodes are
# SUSTAINED, the rolling median cannot reject them: inside a 30-day window they
# are the majority, so the "robust" estimator returns the artefact.
#
# They are therefore dropped before the TREND is fitted, but kept in the
# residual, so the item still reads as violently volatile through the noise
# layer. Volatility is what this really is; a price level it is not.
ARTIFACT_REL = 0.05      # under this fraction of the item's own season median
ARTIFACT_ABS = 500.0     # ...AND under this many roubles

def artifact_mask(df):
    """True where an observation is a floor-price artefact rather than a trade."""
    V = np.asarray(df, dtype=float)
    fin = np.isfinite(V)
    med = np.nanmedian(np.where(fin, V, np.nan), axis=0)
    return fin & (V < ARTIFACT_REL * med) & (V < ARTIFACT_ABS)

# ---------------------------------------------------------------- mod-side ops
def level_curve(day_curve, day_knots, start_day, end_day, scaling_max=None):
    """Resample a day-indexed curve onto levels 1..LVL_MAX.

    Below the flea unlock and above scaling_max the fraction clamps, so the
    trend is flat at both ends and only the price walk moves there.
    """
    lv = LEVELS.astype(float)
    cap = SCALING_MAX if scaling_max is None else scaling_max
    frac = np.clip((lv - FLEA_UNLOCK) / (cap - FLEA_UNLOCK), 0, 1)
    return np.interp(start_day + frac * (end_day - start_day), day_knots, day_curve)
