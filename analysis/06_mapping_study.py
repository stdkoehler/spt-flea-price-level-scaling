"""How should player level map onto season day?

SPT's XP table (globals.json) shows level 15 is only 0.19% of the grind to 79,
so the mapping faithful to playtime is XP-warped, not linear. It loses anyway,
on pacing: XP-warping reaches the same trough and the same level-79 endpoint as
the linear mapping but leaves levels 30-60 flat and crams ~59% of the inflation
run into the last nine levels. The shipped mapping is linear from the flea
unlock across day 10 -> 249 (flealib.MAP_DAY_LO / MAP_DAY_HI), which keeps the
early crash in view and spreads the recovery evenly.

This script reports the alternatives that were considered and rejected.
"""
import json, numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

g = json.load(open(F.REFERENCE / "globals.json", encoding="utf-8"))
need = np.array([e["exp"] for e in g["config"]["exp"]["level"]["exp_table"]], dtype=np.int64)
cum = np.concatenate([[0], np.cumsum(need)])
np.save(F.OUT / "cum_xp.npy", cum)
print("=== SPT XP CURVE ===")
for lv in [15, 30, 50, 70, 79]:
    print(f"  level {lv:2d}: {100*cum[lv-1]/cum[78]:6.2f}% of total XP to 79")

df = F.load(); L = np.log(df.where(df > 0))
core = df.columns[F.classify(df) == "core"]
t = F.day_of_season(df.index).to_numpy(); A = L[core].to_numpy()
LV = F.LEVELS

def index_for(days):
    out = []
    for q, w in zip(days, F.window_for(days)):
        m = np.abs(t - q) <= w / 2
        if m.sum() < 5: m = np.argsort(np.abs(t - q))[:9]
        out.append(np.nanmedian(A[m], axis=0))
    R = np.exp(np.vstack(out) - np.vstack(out)[14])
    return pd.Series(np.nanmedian(R, axis=1), index=LV)

# XP share measured to 79 vs to the cap are very different curves: level 50 is
# 6.9% of the grind to 79 but 51.9% of the grind to 60. The explosive part of
# the XP table is levels 60-79, so capping removes most of what made warping
# pathological - hence both variants below.
f     = np.clip((cum[LV-1] - cum[14]) / (cum[78] - cum[14]), 0, 1)
f_cap = np.clip((cum[LV-1] - cum[14]) / (cum[F.SCALING_MAX-1] - cum[14]), 0, 1)
maps = {
    f"shipped: unlock->L{F.SCALING_MAX}, flat above (day {F.MAP_DAY_LO:.0f}-{F.MAP_DAY_HI:.0f})": F.level_to_day(LV),
    "full season, linear lvl 1-79":        np.clip((LV-1)/78*F.SEASON_DAYS, 8, 249),
    "full season, linear lvl 15-79":       8 + np.clip((LV-15)/64, 0, 1) * 241,
    "full season, XP-warped gamma=0.5":    8 + f**0.5 * 241,
    f"XP-warped gamma=0.5, cap L{F.SCALING_MAX}": F.MAP_DAY_LO + f_cap**0.5 * (F.MAP_DAY_HI - F.MAP_DAY_LO),
}
P = pd.DataFrame({k: index_for(v) for k, v in maps.items()}, index=LV)
# 13_plot_docs.py draws both halves of the story, so the level->day curves are
# saved here rather than re-derived there - one definition, no drift.
pd.DataFrame(maps, index=LV).to_pickle(F.OUT / "mapping_days.pkl")
print("\n=== PRICE INDEX RELATIVE TO LEVEL 15 ===")
print(P.loc[[15, 20, 30, 40, 50, 60, 70, 79]].round(3).to_string())

# Pacing is what actually separates these: the mappings mostly agree on the
# trough and the endpoint and disagree about WHERE along the level range the
# movement arrives. docs/TECHNICAL.md section 5 quotes this table.
print("\n=== PACING (where the movement is delivered) ===")
_W = 9                       # last _W levels before the cap
print(f"{'mapping':42} {'trough':>11} {f'L{F.SCALING_MAX}':>6} "
      f"{f'L{F.SCALING_MAX-_W}-{F.SCALING_MAX}':>8} {'L30-55':>7} {'half by':>8}")
for c in P.columns:
    s = P[c]; sub = s.loc[F.FLEA_UNLOCK:]
    tr = sub.idxmin(); lo, hi = sub.loc[tr], s.loc[F.SCALING_MAX]
    rng = hi - lo
    flat = s.loc[30:55].max() - s.loc[30:55].min()
    if rng < 1e-9:
        print(f"{c:42} {'none':>11} {hi:>6.3f} {'-':>8} {flat:>7.3f} {'-':>8}")
        continue
    last9 = (hi - s.loc[F.SCALING_MAX - _W]) / rng
    half = s.loc[tr:][(s.loc[tr:] - lo) >= 0.5 * rng].index[0]
    trough = "none" if tr == F.FLEA_UNLOCK else f"{lo:.3f} (L{tr})"
    print(f"{c:42} {trough:>11} {hi:>6.3f} {last9:>7.1%} {flat:>7.3f} {half:>8}")

P.to_pickle(F.OUT / "mapping_compare.pkl")
