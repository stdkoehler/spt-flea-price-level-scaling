"""Build the artefact the mod ships: a DAY-indexed price curve per item.

Day-indexed rather than level-indexed so the level->day mapping stays a runtime
config (startDay / endDay) instead of being frozen here. Knots sit every 3 days;
against a daily reference that costs a median 0.04% / p95 4.0% reconstruction
error, and the file is smaller than the level-indexed version was.

Only 'core' items get a curve - pegged and sparse items have no reliable live
price history and must keep SPT's defaults.
"""
import json, numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load()
t = F.day_of_season(df.index).to_numpy()
cls = F.classify(df); core = cls[cls == "core"].index

# Floor-price artefacts are excluded from the TREND only (see flealib). They run
# for weeks at a time, so the rolling median cannot reject them on its own.
V = df[core].to_numpy(float)
art_mask = F.artifact_mask(df[core])
A = np.log(np.where(art_mask, np.nan, np.where(V > 0, V, np.nan)))
print(f"artefacts excluded from the trend: {int(art_mask.sum()):,} observations "
      f"on {int((art_mask.sum(axis=0) > 0).sum())} items "
      f"({100*art_mask.sum()/np.isfinite(V).sum():.2f}% of all prices)")

knots = F.DAY_KNOTS
out = np.empty((len(knots), len(core)))
for i, (q, w) in enumerate(zip(knots, F.window_for(knots))):
    m = np.abs(t - q) <= w / 2
    if m.sum() < 5: m = np.argsort(np.abs(t - q))[:9]
    out[i] = np.nanmedian(A[m], axis=0)

# masking can empty a knot entirely; bridge those across rather than drop the item
P = pd.DataFrame(np.exp(out), index=knots, columns=core)
bridged = int(P.isna().sum().sum())
P = P.interpolate(axis=0, limit_direction="both").dropna(axis=1)
print(f"knots bridged after masking: {bridged}")
P.to_pickle(F.OUT / "day_curves.pkl")

# level-indexed view under the DEFAULT mapping, for plots and reporting
days = F.level_to_day(F.LEVELS)
C = pd.DataFrame({c: np.interp(days, P.index, P[c]) for c in P.columns}, index=F.LEVELS)
C.to_pickle(F.OUT / "level_curves.pkl")
mult = C.div(C.loc[F.FLEA_UNLOCK], axis=1)
mult.to_pickle(F.OUT / "level_mult.pkl")

end = mult.loc[F.LVL_MAX]
print(f"curves: {P.shape[1]} items x {len(knots)} day-knots "
      f"(day {knots[0]:.0f}..{knots[-1]:.0f})")
print(f"excluded: pegged {int((cls=='pegged').sum())}, sparse {int((cls=='sparse').sum())}")
print(f"\n=== default mapping: day {F.MAP_DAY_LO:.0f} -> {F.MAP_DAY_HI:.0f} across "
      f"levels {F.FLEA_UNLOCK}-{F.SCALING_MAX}, held flat above {F.SCALING_MAX} ===")
for lv in [15, 20, 30, 40, 50, 60, 70, 79]:
    print(f"  level {lv:2d} (day {days[lv-1]:5.0f}): {mult.loc[lv].median():.3f}")
print(f"\ninflate {100*(end>1).mean():.1f}%  cheaper {100*(end<1).mean():.1f}%")

F.MOD_DATA.mkdir(parents=True, exist_ok=True)
# Meta carries ONLY what the mod reads or verifies. Everything else - who built
# it, when, from which source, with which filter - is recoverable from the mod
# version plus the git tag, so repeating it here would just be a second copy that
# can drift. The noise block is cross-checked by PriceTable.Load.
art = {"meta": {
        "snapshots": int(len(df)),
        "maxLevel": F.LVL_MAX},
       "dayKnots": [round(float(k), 1) for k in knots],
       "price": {c: [int(round(v)) for v in P[c]] for c in P.columns}}
p = F.MOD_DATA / "price_curves.json"
json.dump(art, open(p, "w"), separators=(",", ":"))
print(f"\nwrote {p}  ({p.stat().st_size/1e6:.2f} MB)")

# ---------------------------------------------------------------- test vectors
# Mirrors PriceTable.Load in C# exactly, so tests/NoiseVectorTest can prove the
# port agrees. Regenerated here so the vectors can never go stale silently.
def _vector_curve(curve, start, end, intensity, scaling_max,
                  unlock=F.FLEA_UNLOCK, max_level=F.LVL_MAX):
    lo = min(max(start, knots[0]), knots[-1])
    hi = min(max(end, knots[0]), knots[-1])
    anchor = float(np.interp(lo, knots, curve))
    out = []
    for lv in range(1, max_level + 1):
        frac = min(max((lv - unlock) / (scaling_max - unlock), 0.0), 1.0)
        val = float(np.interp(lo + frac * (hi - lo), knots, curve))
        ratio = val / anchor if anchor > 0 else 1.0
        out.append(anchor * ratio ** intensity)
    return out

_VEC_ITEMS = ["5d1b392c86f77425243e98fe", "5447a9cd4bdc2dbd208b4567",
              "5c0530ee86f774697952d952", "57347c93245977448d35f6e3",
              "5672cb724bdc2dc2088b456b"]
_VEC_CFGS = [
    dict(name="default",        startDay=10.0, endDay=249.0,  intensityExponent=1.0, scalingMaxLevel=F.SCALING_MAX),
    dict(name="raw",            startDay=10.0, endDay=249.0,  intensityExponent=1.0, scalingMaxLevel=F.SCALING_MAX),
    dict(name="intense",        startDay=10.0, endDay=249.0,  intensityExponent=2.0, scalingMaxLevel=F.SCALING_MAX),
    dict(name="inflation-only", startDay=79.0, endDay=249.0,  intensityExponent=1.0, scalingMaxLevel=F.SCALING_MAX),
    dict(name="clamped-days",   startDay=-50.0, endDay=9999.0, intensityExponent=0.5, scalingMaxLevel=F.SCALING_MAX),
    dict(name="uncapped-79",    startDay=10.0, endDay=249.0,  intensityExponent=1.0, scalingMaxLevel=79),
    dict(name="cap-40",         startDay=10.0, endDay=249.0,  intensityExponent=1.0, scalingMaxLevel=40),
]
_VEC_LEVELS = [1, 14, 15, 16, 20, 40, 60, 79]

vectors = {"_comment": "Golden vectors for PriceTable.Load. Levels are 1-based. "
                       "Regenerated by analysis/07_build_trend_curves.py.", "cases": []}
for _cfg in _VEC_CFGS:
    _case = dict(_cfg); _case["items"] = {}
    for _it in _VEC_ITEMS:
        if _it not in art["price"]: continue
        # IMPORTANT: build from the ROUNDED integers that actually ship, not from
        # the float curve - the mod interpolates the integers, and the ~4e-7
        # difference is enough to fail a 1e-12 comparison.
        _c = _vector_curve(np.array(art["price"][_it], float),
                           _cfg["startDay"], _cfg["endDay"],
                           _cfg["intensityExponent"], _cfg["scalingMaxLevel"])
        _case["items"][_it] = {str(lv): _c[lv - 1] for lv in _VEC_LEVELS}
    vectors["cases"].append(_case)
_vp = F.MOD_DATA / "pricetable_test_vectors.json"
json.dump(vectors, open(_vp, "w"), indent=1)
print(f"wrote {_vp}  ({len(_VEC_CFGS)} cases x {len(_VEC_ITEMS)} items x {len(_VEC_LEVELS)} levels)")
