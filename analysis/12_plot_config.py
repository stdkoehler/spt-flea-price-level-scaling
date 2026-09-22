"""Illustrations of what each player-facing setting does (for the README)."""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, warnings
import flealib as F, fleanoise as N
warnings.filterwarnings("ignore")

P = pd.read_pickle(F.OUT / "day_curves.pkl")
sd = pd.read_pickle(F.OUT / "resid_sd.pkl")
LV = F.LEVELS
IMG = F.DOCS_IMG

lvl = pd.DataFrame({c: F.level_curve(P[c].to_numpy(), P.index.to_numpy(),
                                     F.MAP_DAY_LO, F.MAP_DAY_HI) for c in P.columns},
                   index=LV)
mult = lvl.div(lvl.loc[F.FLEA_UNLOCK], axis=1)
idx = mult.median(axis=1)

fig, ax = plt.subplots(2, 2, figsize=(14, 9))

# ---- (a) intensityExponent
a = ax[0, 0]
for k, c in zip([0.0, 0.5, 1.0, 2.0, 3.0], plt.cm.viridis(np.linspace(0, .9, 5))):
    a.plot(LV[14:], idx.loc[15:] ** k, lw=2.2, color=c, label=f"{k}")
a.axhline(1, ls=":", c="grey"); a.set_xlim(15, 79); a.grid(alpha=.3)
a.legend(title="intensityExponent", fontsize=9); a.set_xlabel("player level")
a.set_ylabel("price x (level 15 = 1.0)")
a.set_title("intensityExponent: scaling factor (1.0 as live data)", fontsize=11)

# ---- (b) scalingMaxLevel
# the level the season runs out at; above it the trend is held and only noise moves
a = ax[0, 1]
for cap, c in zip([40, 50, 60, 79], ["#c0392b", "#e67e22", "#2980b9", "#7f8c8d"]):
    cv = pd.DataFrame({k: F.level_curve(P[k].to_numpy(), P.index.to_numpy(),
                                        F.MAP_DAY_LO, F.MAP_DAY_HI, scaling_max=cap)
                       for k in P.columns}, index=LV)
    m = cv.div(cv.loc[F.FLEA_UNLOCK], axis=1).median(axis=1)
    a.plot(LV[14:], m.loc[15:], lw=2.4 if cap == F.SCALING_MAX else 1.8, color=c,
           label=f"{cap}" + ("  (default)" if cap == F.SCALING_MAX else ""))
    a.plot([cap], [m.loc[cap]], "o", ms=6, color=c, zorder=5)
a.axhline(1, ls=":", c="grey"); a.set_xlim(15, 79); a.grid(alpha=.3)
a.legend(title="scalingMaxLevel", fontsize=9, ncol=2)
a.set_xlabel("player level"); a.set_ylabel("price x (level 15 = 1.0)")
a.set_title("scalingMaxLevel: inflation gradient and cap", fontsize=11)

# ---- (c) noise.amplitudeScale
ITEM = "5447a9cd4bdc2dbd208b4567"          # Colt M4A1, sigma 0.31 - visibly restless
days = np.linspace(0, 90, 2600)
level = F.FLEA_UNLOCK + days / 90 * (F.LVL_MAX - F.FLEA_UNLOCK)
hours = pd.Timestamp("2026-01-01T00:00:00Z").value / 1e9 / 3600 + days * 24
trend = np.interp(level, LV, lvl[ITEM])
world = N.world_seed("5c0530ee86f774697952d952", 1763200000)
a = ax[1, 0]
a.plot(days, trend, lw=3, c="k", zorder=5, label="0.0  (off)")
for s_, c in zip([0.5, 1.0, 2.0], ["#27ae60", "#2980b9", "#c0392b"]):
    sig = min(float(sd[ITEM]) * s_, 0.5 * s_)
    a.plot(days, trend * N.multiplier(ITEM, hours, sig, world), lw=.9, alpha=.8,
           color=c, label=f"{s_}")
a.grid(alpha=.3); a.legend(title="noise.amplitudeScale", fontsize=9, ncol=2)
a.set_xlabel("days into playthrough"); a.set_ylabel("price (RUB)")
a.yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k")
a.set_title("noise.amplitudeScale: day-to-day drift", fontsize=11)

# ---- (d) priceShockSize
# Deliberately NOT the M4A1: at sigma 0.31 its everyday drift is as tall as a
# shock, so nothing reads as exceptional. A calm item (sigma ~0.11) whose window
# happens to hold five shock knots makes the tail behaviour legible instead.
SHOCK_ITEM = "5d1b376e86f774252519444e"      # Bottle of Fierce Hatchling moonshine
a = ax[1, 1]
shock_trend = np.interp(level, LV, lvl[SHOCK_ITEM])
shock_sig = min(float(sd[SHOCK_ITEM]), .5)

# shade the 48h knots carrying a shock, so "which bump is the shock" is not a guess
ks = np.arange(int(hours.min() // N.JUMP_KNOT_H), int(hours.max() // N.JUMP_KNOT_H) + 2)
_, u = N._knot_pair(N.seed_of(SHOCK_ITEM, world), ks, 55555)
for d_ in (ks * N.JUMP_KNOT_H - hours.min())[u < N.JUMP_Q] / 24.0:
    a.axvspan(d_ - 2, d_ + 2, color="#c0392b", alpha=.07, lw=0, zorder=0)

orig = N.JUMP_M
# largest first so the tamer settings stay visible on top
for jm, c in zip([6.0, 4.0, 2.5, 1.0], ["#c0392b", "#2980b9", "#27ae60", "#7f8c8d"]):
    N.JUMP_M = jm
    a.plot(days, shock_trend * N.multiplier(SHOCK_ITEM, hours, shock_sig, world),
           lw=1.0, alpha=.9, color=c, label=f"{jm}")
N.JUMP_M = orig
a.plot(days, shock_trend, lw=2.4, c="k", zorder=5)
h, l = a.get_legend_handles_labels()
a.grid(alpha=.3); a.set_xlim(0, 90)
a.legend(h[::-1], l[::-1], title="priceShockSize", fontsize=9, ncol=2)
a.set_xlabel("days into playthrough"); a.set_ylabel("price (RUB)")
a.yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k")
a.set_title("priceShockSize: how violent the shocks are (shaded)", fontsize=11)

plt.tight_layout(); plt.savefig(IMG / "config_effects.png", dpi=130)
print(f"wrote {IMG/'config_effects.png'}")
