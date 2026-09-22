"""Figures for docs/TECHNICAL.md."""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, warnings
import flealib as F, fleanoise as N
warnings.filterwarnings("ignore")
IMG = F.DOCS_IMG
df = F.load(); L = np.log(df.where(df > 0)); t = F.day_of_season(df.index).to_numpy()
names = F.names()

# ============================================================ season overview
core = df.columns[F.classify(df) == "core"]
Lc = L[core]
idx = np.exp(Lc.sub(Lc.iloc[np.argmin(np.abs(t - 8))], axis=1)).median(axis=1)
fig, ax = plt.subplots(figsize=(12, 4.6))
ax.plot(t, idx, lw=1.0, c="#c0392b", alpha=.85)
for lo, hi, lbl in [(0, 8, "no data\n(launch)"), (249, 260.5, "no data\n(pre-1.1.0.0)")]:
    ax.axvspan(lo, hi, color="#dddddd", zorder=0)
    ax.text((lo+hi)/2, 1.55, lbl, ha="center", fontsize=8, color="#555")
ax.axvline(10, ls="--", c="#2980b9"); ax.text(13, 1.45, "default startDay = 10", fontsize=8.5, color="#2980b9")
ax.axvline(79, ls=":", c="#27ae60");  ax.text(82, 1.35, "trough / inflation begins", fontsize=8.5, color="#27ae60")
ax.set_xlabel("season day")
ax.set_ylabel("price index (day 8 = 1.0)")
ax.set_title("Median item prices over season (EFT 1.0 from 2025-11-15 to 2026-08-03)", weight="bold")
ax.grid(alpha=.3); ax.set_xlim(0, 261)
plt.tight_layout(); plt.savefig(IMG / "season_overview.png", dpi=130)

# ============================================================ filter mechanism
fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
d = np.linspace(8, 249, 300)
ax[0].plot(d, F.window_for(d), lw=2.5, c="#2980b9")
ax[0].fill_between(d, 0, F.window_for(d), alpha=.15, color="#2980b9")
ax[0].set_xlabel("season day"); ax[0].set_ylabel("median window (days)")
ax[0].set_title("Adaptive window  w = clip(5 + 0.25·day, 5, 60)", fontsize=11)
ax[0].grid(alpha=.3)
ax[0].annotate("narrow: keep early wipe signal", xy=(20, 9), xytext=(148, 13),
               arrowprops=dict(arrowstyle="->", color="#555"), fontsize=8.5, color="#555")
ax[0].annotate("wide: late season smooth", xy=(222, 60), xytext=(52, 50),
               arrowprops=dict(arrowstyle="->", color="#555"), fontsize=8.5, color="#555")

iid = "5672cb724bdc2dc2088b456b"
P = pd.read_pickle(F.OUT / "day_curves.pkl")
s = df[iid].dropna(); dd = F.day_of_season(s.index).to_numpy()
ax[1].plot(dd, s.to_numpy(), ".", ms=3, alpha=.4, c="k", label="raw snapshots")
for w, c, lbl in [(5, "#e67e22", "fixed 5d"), (60, "#27ae60", "fixed 60d")]:
    sm = [np.nanmedian(np.log(s.to_numpy())[np.abs(dd - q) <= w/2]) for q in P.index]
    ax[1].plot(P.index, np.exp(sm), lw=1.4, c=c, alpha=.8, label=lbl)
ax[1].plot(P.index, P[iid], lw=2.8, c="#c0392b", label="adaptive (used)")
ax[1].set_xlabel("season day"); ax[1].set_ylabel("price (RUB)")
ax[1].set_title(f"{names[iid]}", fontsize=11); ax[1].legend(fontsize=8.5); ax[1].grid(alpha=.3)
ax[1].yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k")
plt.tight_layout(); plt.savefig(IMG / "filter_mechanism.png", dpi=130)

# ============================================================ noise mechanism
seed = N.seed_of("5d1b392c86f77425243e98fe", 0)
H0 = 1440.0                      # a window that actually contains a jump
h = np.linspace(H0, H0 + 720, 3000)
fig, ax = plt.subplots(2, 2, figsize=(14, 8))
fig.suptitle("How the stateless price walk is generated", fontsize=13, weight="bold")

a = ax[0, 0]
kh = 48
ks = np.arange(int(H0/kh), int(H0/kh) + 17)
g, _ = N._knot_pair(seed, ks, 7919)
a.plot(h, N._interp(h, kh, dict(zip(ks, g))), lw=2, c="#2980b9")
a.plot(ks * kh, g, "o", ms=7, c="#c0392b", zorder=5)
a.set_ylim(min(g)*1.35, max(g)*1.35)
for x in ks * kh: a.axvline(x, lw=.5, c="#ccc", zorder=0)
a.axvspan(ks[4]*kh, ks[5]*kh, color="#f9e79f", alpha=.6, zorder=0)
a.annotate("every hour in this band reads\nthe SAME two red dots",
           xy=(ks[4]*kh + kh/2, g[4]), xytext=(0.5, 0.07), textcoords="axes fraction",
           ha="center", fontsize=8.5, color="#7d6608",
           arrowprops=dict(arrowstyle="->", color="#b7950b", lw=1.2))
a.set_xlabel("hour"); a.set_title("One octave: hash a gaussian per 48h knot, join with a smoothstep", fontsize=10)
a.grid(alpha=.25); a.set_xlim(H0, H0+720)

a = ax[0, 1]
for (khh, w), c in zip(N.OCTAVES, ["#e67e22", "#2980b9", "#27ae60"]):
    kk = np.arange(int(H0/khh), int((H0+720)/khh) + 2)
    gg, _ = N._knot_pair(seed, kk, N.OCTAVES.index((khh, w)) * 7919)
    a.plot(h, w * N._interp(h, khh, dict(zip(kk, gg))), lw=1.8, c=c, label=f"{khh}h x {w}")
a.set_xlabel("hour"); a.legend(fontsize=8.5); a.grid(alpha=.25); a.set_xlim(H0, H0+720)
a.set_title("Three octaves — fast chop, 2-day swings, slow mood", fontsize=10)

a = ax[1, 0]
def _oct(i, khh, w):
    kk = np.arange(int(H0/khh), int((H0+720)/khh) + 2)
    gg, _ = N._knot_pair(seed, kk, i * 7919)
    return w * N._interp(h, khh, dict(zip(kk, gg)))
base = sum(_oct(i, khh, w) for i, (khh, w) in enumerate(N.OCTAVES))
jk = np.arange(int(H0/N.JUMP_KNOT_H), int((H0+720)/N.JUMP_KNOT_H) + 2)
_, u = N._knot_pair(seed, jk, 55555)
jenv = N._interp(h, N.JUMP_KNOT_H, dict(zip(jk, np.where(u < N.JUMP_Q, N.JUMP_M, 1.0))))
a.plot(h, base, lw=1.6, c="#7f8c8d", label="sum of octaves")
a.plot(h, base * jenv / N.UNIT_SD, lw=2, c="#c0392b", label="x jump envelope = z")
a2 = a.twinx(); a2.plot(h, jenv, lw=1.2, ls="--", c="#8e44ad", alpha=.7)
a2.set_ylabel("jump envelope", color="#8e44ad", fontsize=9); a2.tick_params(labelsize=8, colors="#8e44ad")
a.set_xlabel("hour"); a.legend(fontsize=8.5, loc="upper left"); a.grid(alpha=.25); a.set_xlim(H0, H0+720)
a.set_title("Sum, then the rare jump envelope, then normalise to unit variance", fontsize=10)

a = ax[1, 1]
for sig, c in [(0.05, "#27ae60"), (0.20, "#2980b9"), (0.50, "#c0392b")]:
    a.plot((h - H0) / 24, np.exp(sig * N.z(seed, h)), lw=1.6, c=c, label=f"sigma {sig}")
a.axhline(1, ls=":", c="grey"); a.set_xlabel("days"); a.set_ylabel("price multiplier")
a.legend(fontsize=8.5); a.grid(alpha=.25)
a.set_title("Final multiplier exp(sigma·z) for three amplitudes", fontsize=10)
plt.tight_layout(rect=[0, 0, 1, .955]); plt.savefig(IMG / "noise_mechanism.png", dpi=130)
print("wrote season_overview.png, filter_mechanism.png, noise_mechanism.png")

# ============================================================ mapping comparison
# Left: what each candidate mapping DOES. Right: what the player then feels.
# Both from 06_mapping_study.py so the numbers cannot drift from the doc.
MD = pd.read_pickle(F.OUT / "mapping_days.pkl")
MP = pd.read_pickle(F.OUT / "mapping_compare.pkl")
# keyed positionally so adding a candidate in 06 does not need edits here
STYLE = dict(zip(MD.columns, [
    ("#c0392b", 3.0, "-"), ("#7f8c8d", 1.6, "--"), ("#2980b9", 1.6, ":"),
    ("#8e44ad", 2.0, "-"), ("#e67e22", 2.0, (0, (5, 2, 1, 2))),
]))
lv = MD.index.to_numpy()
keep = lv >= F.FLEA_UNLOCK

fig, ax = plt.subplots(1, 2, figsize=(14, 5.0))

a = ax[0]
for c in MD.columns:
    col, w, ls = STYLE[c]
    a.plot(lv[keep], MD[c].to_numpy()[keep], lw=w, ls=ls, c=col, label=c)
a.set_xlabel("player level"); a.set_ylabel("season day the player sees")
a.set_xlim(F.FLEA_UNLOCK, F.LVL_MAX); a.grid(alpha=.3); a.legend(fontsize=8.5, loc="upper left")
a.set_title("Player Level to Season Runtime mapping", fontsize=11)
# A leader line has nowhere to go on either panel, so label the rule directly.
for a_ in ax:
    a_.axvline(F.SCALING_MAX, ls="-.", lw=1.2, c="#c0392b", alpha=.6, zorder=0)
    a_.text(F.SCALING_MAX - 0.6, 0.02, f"cap {F.SCALING_MAX}", ha="right", va="bottom",
            fontsize=8, color="#c0392b", transform=a_.get_xaxis_transform())

a = ax[1]
for c in MP.columns:
    col, w, ls = STYLE[c]
    s = MP[c].loc[F.FLEA_UNLOCK:]
    a.plot(s.index, s.to_numpy(), lw=w, ls=ls, c=col, label=c)
    tr = s.idxmin()
    if tr != F.FLEA_UNLOCK:
        a.plot([tr], [s.loc[tr]], "o", ms=7, c=col, zorder=5)
a.axhline(1.0, ls=":", c="grey", lw=1)
a.set_xlabel("player level"); a.set_ylabel("price x  (level 15 = 1.0)")
a.set_xlim(F.FLEA_UNLOCK, F.LVL_MAX); a.grid(alpha=.3)
a.set_title("Player level to median price mapping", fontsize=11)
a.legend(fontsize=8, loc="upper left")
a.annotate("XP-warped WITHOUT the cap: flat for thirty levels,\nthen the entire climb in the last nine",
           xy=(46, MP[MP.columns[3]].loc[46]), xytext=(31, 0.93),
           fontsize=8.5, color="#8e44ad", arrowprops=dict(arrowstyle="->", color="#8e44ad"))
plt.tight_layout(); plt.savefig(IMG / "mapping_compare.png", dpi=130)
print("wrote mapping_compare.png")

# ============================================================ method comparison
import pickle
res = pickle.load(open(F.OUT / "cv_results.pkl", "rb"))
s = pd.Series(res).sort_values()
colors = ["#27ae60" if "rolling median" in k else "#c0392b" if "poly" in k else "#7f8c8d"
          for k in s.index]
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.barh(range(len(s)), 100 * (np.exp(s.to_numpy()) - 1), color=colors)
ax.set_yticks(range(len(s))); ax.set_yticklabels(s.index, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("held-out price error (%), gapped block CV")
ax.grid(alpha=.3, axis="x")
for i, v in enumerate(100 * (np.exp(s.to_numpy()) - 1)):
    ax.text(v + .08, i, f"{v:.1f}%", va="center", fontsize=8.5)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#27ae60", label="robust lookup (filter)"),
                   Patch(color="#c0392b", label="fitted polynomial"),
                   Patch(color="#7f8c8d", label="no filtering")], fontsize=9, loc="lower right")
plt.tight_layout(); plt.savefig(IMG / "method_comparison.png", dpi=130)
print("wrote method_comparison.png")
