"""Filtered lookup vs fitted function, under GAPPED BLOCK cross-validation.

The gap matters: adjacent snapshots share ~75% of their 24h averaging window,
so a naive even/odd split rewards "copy your neighbour" and wrongly concludes
that no filtering is best. Holding out contiguous blocks with a buffer removes
that leak. Conclusion: every parametric fit loses to a plain robust lookup.
"""
import numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load(); L = np.log(df.where(df > 0))
core = F.classify(df) == "core"
Lc = L[df.columns[core]].dropna(axis=1)
Lc = Lc.iloc[:, np.random.default_rng(0).choice(Lc.shape[1], 700, replace=False)]
t = F.day_of_season(Lc.index).to_numpy(); A = Lc.to_numpy()

BLOCK, BUF = 7.0, 3.0
folds = []
for s in np.arange(t.min(), t.max() - BLOCK, BLOCK * 3):
    te = (t >= s) & (t < s + BLOCK); tr = (t < s - BUF) | (t >= s + BLOCK + BUF)
    if te.sum() > 5 and tr.sum() > 100: folds.append((tr, te))

def run(fn, name):
    e = np.concatenate([np.abs(fn(t[tr], A[tr], t[te]) - A[te]) for tr, te in folds])
    m = float(np.median(e))
    print(f"  {name:34} {m:.4f}  = {100*(np.exp(m)-1):5.1f}% price error")
    return m

def roll(w):
    def f(tt, AA, tq):
        s = pd.DataFrame(AA, index=pd.to_datetime(tt * 86400, unit="s", utc=True))
        sm = s.rolling(f"{w}D", min_periods=1, center=True).median().to_numpy()
        return np.vstack([np.interp(tq, tt, sm[:, k]) for k in range(sm.shape[1])]).T
    return f
def poly(d):
    def f(tt, AA, tq):
        C = np.polyfit(tt, AA, d)
        return np.vstack([np.polyval(C[:, k], tq) for k in range(AA.shape[1])]).T
    return f

print(f"gapped block CV | {Lc.shape[1]} items, {len(folds)} folds\n=== MAE(log) ===")
res = {"raw nearest (no filter)":
       run(lambda tt, AA, tq: AA[np.searchsorted(tt, tq).clip(0, len(tt)-1)], "raw nearest (no filter)")}
for w in [1, 3, 7, 14, 28, 42, 60]: res[f"rolling median {w}D"] = run(roll(w), f"rolling median {w}D")
for d in [2, 3, 5, 8, 10]:          res[f"poly deg {d}"]        = run(poly(d), f"global polynomial deg {d}")
print("\n=== RANKING ===")
for k, v in sorted(res.items(), key=lambda x: x[1]): print(f"  {v:.4f}  {k}")

import pickle
pickle.dump(res, open(F.OUT / "cv_results.pkl", "wb"))
print(f"\nwrote {F.OUT/'cv_results.pkl'}")
