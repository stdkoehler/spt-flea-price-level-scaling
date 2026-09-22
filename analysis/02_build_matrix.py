"""Fold the raw snapshots into one (snapshot x item) price matrix."""
import json, numpy as np, pandas as pd
import flealib as F

files = sorted(p for p in F.SNAPSHOTS.iterdir() if p.suffix == ".json")
ts, recs = [], []
for f in files:
    n = f.name
    ts.append(pd.Timestamp(f"{n[:10]} {n[11:19].replace('-',':')}", tz="UTC"))
    recs.append(json.load(open(f)))

items = sorted({k for r in recs for k in r})
idx = {k: i for i, k in enumerate(items)}
M = np.full((len(recs), len(items)), np.nan)
for i, r in enumerate(recs):
    for k, v in r.items(): M[i, idx[k]] = v

df = pd.DataFrame(M, index=pd.DatetimeIndex(ts), columns=items).sort_index()
np.savez_compressed(F.OUT / "price_matrix.npz", M=df.to_numpy(),
                    items=np.array(items), ts=df.index.astype("int64").to_numpy())

gap = df.index.to_series().diff().dt.total_seconds() / 3600
print(f"snapshots {df.shape[0]}  items {df.shape[1]}  NaN {df.isna().to_numpy().mean():.1%}")
print(f"span {df.index[0]} -> {df.index[-1]}")
print(f"gap hours: median {gap.median():.1f}  max {gap.max():.0f} ({gap.max()/24:.1f} days)")
