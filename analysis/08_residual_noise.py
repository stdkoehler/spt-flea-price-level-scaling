"""Characterise what the smooth level curve leaves behind.

The mod is stateless, so any price walk must be a deterministic function of
(itemId, hour). To make it look real we need three things from the data:
the amplitude, the decorrelation time, and the tail shape.
"""
import numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load(); L = np.log(df.where(df > 0))
t  = F.day_of_season(df.index).to_numpy()
core = df.columns[F.classify(df) == "core"]
Lc = L[core]

# Smooth with the SAME adaptive filter the curve uses, and with the same
# artefact mask, so the residual is exactly the component the mod cannot
# represent. The mask applies to the TREND only: the artefacts stay in the
# residual, so an item that spends weeks at a sentinel price reads as extremely
# volatile rather than as cheap. Most such items land on sigmaCap, which is the
# honest outcome - we know they move violently, not where they sit.
S = np.empty(Lc.shape)
A = Lc.to_numpy()
Am = np.where(F.artifact_mask(df[core]), np.nan, A)
for i, (q, w) in enumerate(zip(t, F.window_for(t))):
    m = np.abs(t - q) <= w / 2
    if m.sum() < 5: m = np.argsort(np.abs(t - q))[:9]
    S[i] = np.nanmedian(Am[m], axis=0)
R = pd.DataFrame(A - S, index=Lc.index, columns=core)

sd = R.std()
print("=== AMPLITUDE (sd of log residual, per item) ===")
print(sd.describe(percentiles=[.1, .25, .5, .75, .9]).round(3).to_string())
print(f"  median item: sd {sd.median():.3f} log  ~ +/-{100*(np.exp(sd.median())-1):.0f}% typical swing")

stats = pd.read_pickle(F.OUT / "item_stats.pkl")
b = pd.cut(stats.median_price[core], [0, 2e4, 5e4, 2e5, 1e6, 1e12],
           labels=["<20k", "20-50k", "50-200k", "200k-1M", ">1M"])
print("\n=== does amplitude depend on price? ===")
print(pd.DataFrame({"sd": sd, "grp": b}).groupby("grp", observed=True)
        .agg(n=("sd", "size"), median_sd=("sd", "median")).round(3).to_string())

print("\n=== DECORRELATION (autocorrelation of residual vs time lag) ===")
Rv = R.to_numpy()
edges = [(3,9),(9,15),(15,27),(27,39),(39,60),(60,84),(84,132),(132,180),
         (180,264),(264,360),(360,504),(504,720)]
ac = []
for lo, hi in edges:
    num = den = 0.0
    for i in range(len(t)):
        j = np.where((t - t[i]) * 24 >= lo)[0]
        j = j[(t[j] - t[i]) * 24 < hi]
        if len(j) == 0: continue
        a_, b_ = Rv[i], Rv[j].mean(axis=0)
        ok = np.isfinite(a_) & np.isfinite(b_)
        num += np.nansum(a_[ok] * b_[ok]); den += np.nansum(a_[ok] ** 2)
    ac.append(num / den if den else np.nan)
    print(f"  lag {lo:4d}-{hi:4d}h ({(lo+hi)/48:5.1f}d): rho = {ac[-1]:6.3f}")
mid = np.array([(lo + hi) / 2 for lo, hi in edges])
ok = np.array(ac) > 0.02
tau = -np.polyfit(mid[ok], np.log(np.array(ac)[ok]), 1)[0] ** -1
print(f"\n  fitted OU decorrelation time tau ~ {tau:.0f} h  ({tau/24:.1f} days)")

z = (R / sd).to_numpy().ravel(); z = z[np.isfinite(z)]
print("\n=== TAIL SHAPE (standardised residual) ===")
print(f"  kurtosis {pd.Series(z).kurtosis():.1f} (normal = 0)   "
      f"|z|>3: {100*(np.abs(z)>3).mean():.2f}% (normal 0.27%)   "
      f"|z|>5: {100*(np.abs(z)>5).mean():.3f}% (normal 0.00006%)")
for p in [1, 5, 25, 50, 75, 95, 99]:
    print(f"    p{p:<2d} {np.percentile(z, p):+.2f}", end="")
print()
np.save(F.OUT / "resid_sd.npy", sd.to_numpy())
sd.to_pickle(F.OUT / "resid_sd.pkl")
