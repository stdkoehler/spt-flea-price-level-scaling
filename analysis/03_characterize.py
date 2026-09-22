"""Coverage, noise structure and item classification.

Findings: listing gaps are NOT the main problem (84% of items appear in every
snapshot). The noise is heavy-tailed jumps - median 6h move is ~3%, but the
log-return sd is 0.34 and only 7% of big moves are clean round-trips.
"""
import numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load(); n = len(df)
L = np.log(df.where(df > 0)); r = L.diff()
cov = df.notna().mean()
stale = (df.diff() == 0).sum() / df.notna().sum()

print("=== COVERAGE ===")
for th in [1.0, .95, .75, .5, .25]:
    print(f"  items present in >= {th:4.0%} of snapshots: {(cov >= th).sum():5d}")

print("\n=== NOISE ===")
print(f"  median |6h move|          : {r.abs().median().median():.3f} log "
      f"(~{100*(np.exp(r.abs().median().median())-1):.1f}%)")
print(f"  median per-item return sd : {r.std().median():.3f}")
sp = (r.abs() > 0.5).sum()
rt = ((r > .4) & (r.shift(-1) < -.4)).sum() + ((r < -.4) & (r.shift(-1) > .4)).sum()
print(f"  moves >65% in 6h          : {int(sp.sum()):,}  of which round-trips: {100*rt.sum()/sp.sum():.0f}%")
print("  -> spikes mostly PERSIST, so simple outlier clipping will not fix them")

cls = F.classify(df)
print("\n=== ITEM CLASSES ===")
print(cls.value_counts().to_string())
print("  core   = live-traded, usable")
print("  pegged = no tarkov.dev data, frozen at the SPT base price -> must NOT be scaled")
print("  sparse = listed too rarely to fit a curve")

pd.DataFrame({"coverage": cov, "stale": stale, "vol": r.std(),
              "median_price": df.median(), "cls": cls}).to_pickle(F.OUT / "item_stats.pkl")
print(f"\nwrote {F.OUT/'item_stats.pkl'}")
