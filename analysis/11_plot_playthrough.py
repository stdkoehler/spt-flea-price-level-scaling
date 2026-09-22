"""Two characters, same curve, different markets.

The trend is a function of LEVEL; the price walk is a function of WALL-CLOCK HOUR.
So a trace needs a levelling schedule - here both characters start on the same
date and take PLAYTHROUGH_DAYS to go from the flea unlock to 79. Only the world
seed differs, which isolates the per-playthrough effect.
"""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, warnings
import flealib as F, fleanoise as N
warnings.filterwarnings("ignore")

PLAYTHROUGH_DAYS = 120.0
SIGMA_CAP = 0.5
START = pd.Timestamp("2026-01-01T00:00:00Z")
START_H = START.value / 1e9 / 3600

CHARS = [("Character A", N.world_seed("5c0530ee86f774697952d952", 1763200000), "#c0392b"),
         ("Character B", N.world_seed("5d1b392c86f77425243e98fe", 1763200001), "#1f6f8b")]

C  = pd.read_pickle(F.OUT / "level_curves.pkl")
sd = pd.read_pickle(F.OUT / "resid_sd.pkl")
names = F.names()

ITEMS = ["5d1b392c86f77425243e98fe",   # Light bulb
         "5447a9cd4bdc2dbd208b4567",   # Colt M4A1
         "5672cb724bdc2dc2088b456b",   # Geiger-Muller counter
         "5c0530ee86f774697952d952"]   # LEDX

days = np.linspace(0, PLAYTHROUGH_DAYS, 4000)
level = F.FLEA_UNLOCK + days / PLAYTHROUGH_DAYS * (F.LVL_MAX - F.FLEA_UNLOCK)
hours = START_H + days * 24

fig, axes = plt.subplots(2, 2, figsize=(15, 9))
fig.suptitle("Synthetic noisy price walk showing different randomness for different characters",
             fontsize=13, weight="bold")

for ax, iid in zip(axes.ravel(), ITEMS):
    trend = np.interp(level, C.index, C[iid])
    s = min(float(sd[iid]), SIGMA_CAP)
    ax.plot(days, trend, lw=3, c="black", zorder=5, label="filtered curve (level)")
    for lbl, world, col in CHARS:
        ax.plot(days, trend * N.multiplier(iid, hours, s, world),
                lw=1.0, c=col, alpha=.8, label=f"{lbl}")
    nm = names.get(iid, iid)
    nm = nm if len(nm) < 34 else nm[:32] + "..."
    ax.set_title(f"{nm}   (sigma = {s:.2f})", fontsize=10.5)
    ax.set_xlabel("days into playthrough"); ax.set_xlim(0, PLAYTHROUGH_DAYS)
    ax.grid(alpha=.25); ax.tick_params(labelsize=8)
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k" if v >= 1000 else f"{v:.0f}")
    top = ax.secondary_xaxis("top", functions=(
        lambda d: F.FLEA_UNLOCK + d / PLAYTHROUGH_DAYS * (F.LVL_MAX - F.FLEA_UNLOCK),
        lambda l: (l - F.FLEA_UNLOCK) / (F.LVL_MAX - F.FLEA_UNLOCK) * PLAYTHROUGH_DAYS))
    top.set_xlabel("player level", fontsize=8.5); top.tick_params(labelsize=8, colors="#555")
axes[0, 0].legend(fontsize=8.5, loc="upper left")
plt.tight_layout(rect=[0, 0, 1, .955])
plt.savefig(F.DOCS_IMG / "playthrough.png", dpi=130)

print(f"world seeds: A={CHARS[0][1]}  B={CHARS[1][1]}")
print(f"\n{'item':34} {'sigma':>6} {'A/B corr':>9} {'A end':>10} {'B end':>10} {'curve end':>10}")
for iid in ITEMS:
    trend = np.interp(level, C.index, C[iid]); s = min(float(sd[iid]), SIGMA_CAP)
    a = trend * N.multiplier(iid, hours, s, CHARS[0][1])
    b = trend * N.multiplier(iid, hours, s, CHARS[1][1])
    r = np.corrcoef(np.log(a/trend), np.log(b/trend))[0, 1]
    print(f"{names.get(iid,iid)[:34]:34} {s:6.2f} {r:+9.3f} {a[-1]:10,.0f} {b[-1]:10,.0f} {trend[-1]:10,.0f}")
print(f"\nwrote {F.DOCS_IMG/'playthrough.png'}")
