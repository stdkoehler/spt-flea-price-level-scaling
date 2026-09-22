"""Diagnostic plots: the global curve, per-item spread, and raw-vs-fitted panels."""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load(); t = F.day_of_season(df.index).to_numpy()
C = pd.read_pickle(F.OUT / "level_curves.pkl"); mult = pd.read_pickle(F.OUT / "level_mult.pkl")
names = F.names(); LV = C.index.to_numpy(); fit_days = F.level_to_day(LV)
end = mult.loc[F.LVL_MAX]

# ---------------------------------------------------------- 1. global curve
fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
fig.suptitle("Inflation-only curve  (levels 15-79 -> season days 79-249)", weight="bold")
a = ax[0]
a.fill_between(LV[14:], mult.quantile(.25, axis=1)[14:], mult.quantile(.75, axis=1)[14:],
               alpha=.25, label="IQR across items")
a.plot(LV[14:], mult.median(axis=1)[14:], lw=2.6, c="crimson", label="median item (k=1)")
for k, ls in [(1.5, "--"), (2.0, ":")]:
    a.plot(LV[14:], mult.median(axis=1)[14:]**k, lw=1.6, ls=ls, c="darkred", label=f"k={k}")
a.axhline(1, ls=":", c="grey"); a.set_xlim(15, 79); a.grid(alpha=.3); a.legend(fontsize=9)
a.set_xlabel("player level"); a.set_ylabel("price x (level 15 = 1.0)"); a.set_title("Global index")
a = ax[1]
a.hist(np.log10(end.clip(.3, 6)), bins=70, color="steelblue", alpha=.85)
a.axvline(0, c="k", lw=1.2); a.axvline(np.log10(end.median()), c="crimson", lw=2,
                                       label=f"median {end.median():.2f}x")
a.set_xticks(np.log10([.5, 1, 1.5, 2, 3, 5])); a.set_xticklabels(["0.5x","1x","1.5x","2x","3x","5x"])
a.set_xlabel("level-79 multiplier"); a.set_ylabel("items"); a.legend(); a.grid(alpha=.3)
a.set_title(f"Per-item spread ({100*(end>1).mean():.0f}% inflate)")
plt.tight_layout(); plt.savefig(F.OUT / "final_curve.png", dpi=130)

# ---------------------------------------------------------- 2. raw vs fitted
stats = pd.read_pickle(F.OUT / "item_stats.pkl")
named = [c for c in C.columns if c in names]
q = pd.DataFrame({"name": [names[c] for c in named], "end": end[named],
                  "vol": stats.vol[named], "price": C.loc[15, named]}).dropna()
liquid = q[(q.vol < q.vol.quantile(.45)) & (q.price > 3000)]
REQ = ["5c0530ee86f774697952d952", "5d1b392c86f77425243e98fe", "5447a9cd4bdc2dbd208b4567",
       "57347c93245977448d35f6e3", "5672cb724bdc2dc2088b456b"]
rep = liquid.assign(d=(liquid.end - end.median()).abs()).nsmallest(40, "d").nlargest(5, "price").index.tolist()
cheap = liquid.nsmallest(5, "end").index.tolist()

groups = [("Requested", REQ, "#c0392b"),
          (f"Representative  (near median x{end.median():.2f})", rep, "#1f6f8b"),
          ("Gets cheaper", cheap, "#2e7d32")]
fig, axes = plt.subplots(3, 5, figsize=(21, 11.5))
fig.suptitle("Exemplary Items with Filtered Trend vs. Sampling",
             fontsize=14, weight="bold")
for r, (title, ids, col) in enumerate(groups):
    for ci, iid in enumerate(ids):
        a = axes[r, ci]
        s = df[iid].dropna(); dd = F.day_of_season(s.index).to_numpy(); vv = s.to_numpy()
        pre = dd < F.MAP_DAY_LO
        a.plot(dd[pre], vv[pre], ".", ms=2.2, color="#bbbbbb", alpha=.55)
        a.plot(dd[~pre], vv[~pre], ".", ms=2.6, color=col, alpha=.32, label="raw snapshots")
        a.plot(fit_days[14:], C[iid].to_numpy()[14:], lw=2.8, color="black", label="fitted curve")
        a.axvspan(0, F.MAP_DAY_LO, color="#f2f2f2", zorder=0)
        lo, hi = np.nanpercentile(vv, [1, 99]); pad = (hi - lo) * .12
        a.set_ylim(max(0, lo - pad), hi + pad); a.set_xlim(0, 262)
        nm = names.get(iid, iid); nm = nm if len(nm) < 34 else nm[:32] + "..."
        a.set_title(f"{nm}\nx{end[iid]:.2f} at lvl 79", fontsize=9.5)
        a.grid(alpha=.25); a.tick_params(labelsize=8)
        a.yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k" if v >= 1000 else f"{v:.0f}")
        if r == 2: a.set_xlabel("season day", fontsize=9)
        if ci == 0: a.set_ylabel(title, fontsize=10, weight="bold", color=col)
        top = a.secondary_xaxis("top", functions=(F.day_to_level, F.level_to_day))
        top.set_xticks([15, 30, 50, 70]); top.tick_params(labelsize=7.5, colors="#555")
        if r == 0 and ci == 0: a.legend(fontsize=7.5, loc="upper left", markerscale=3)
plt.tight_layout(rect=[0, 0, 1, .965]); plt.savefig(F.DOCS_IMG / "item_fits.png", dpi=125)
print(f"wrote {F.OUT/'final_curve.png'} and {F.DOCS_IMG/'item_fits.png'}")
