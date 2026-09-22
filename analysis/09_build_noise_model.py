"""Validate the stateless price walk against the measured residual, then write the
per-item amplitude and the noise parameters into the shipped artefact.

The price walk is indexed by WALL-CLOCK hour, not by level - otherwise prices would
freeze between level-ups. Level sets the trend, the hour sets the wobble.
"""
import json, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, warnings
import flealib as F, fleanoise as N
warnings.filterwarnings("ignore")

sd = pd.read_pickle(F.OUT / "resid_sd.pkl")
TARGET = {6: .872, 12: .739, 21: .566, 33: .415, 49: .304, 72: .206, 108: .110, 156: .032}
lags = list(TARGET)
hours = np.arange(0, 8000, 1.0)
Z = [N.z(s, hours) for s in range(1, 30)]

def acf(x, L):
    x = x - x.mean()
    return np.array([np.sum(x[:-l] * x[l:]) / np.sum(x * x) for l in L])
syn_acf = np.mean([acf(v, lags) for v in Z], axis=0)
z_all = np.concatenate(Z); z_all = z_all / z_all.std()

print("=== ACF: synthetic vs measured ===")
print(f"{'lag':>6} {'synthetic':>10} {'measured':>10}")
for l, s_, t_ in zip(lags, syn_acf, TARGET.values()):
    print(f"{l:>5}h {s_:10.3f} {t_:10.3f}")
print("\n=== TAILS ===")
print(f"  synthetic: kurt {pd.Series(z_all).kurtosis():5.1f}  |z|>3 {100*(np.abs(z_all)>3).mean():.2f}%  "
      f"|z|>5 {100*(np.abs(z_all)>5).mean():.3f}%")
print(f"  measured : kurt  25.8  |z|>3 1.46%  |z|>5 0.286%")
print("  (kurtosis is deliberately NOT matched - the extreme tail of the real data is")
print("   partly tarkov.dev glitches, and reproducing it would show absurd prices)")

print("\n=== AMPLITUDE per item ===")
print(f"  sigma: p10 {sd.quantile(.1):.2f}  median {sd.median():.2f}  p90 {sd.quantile(.9):.2f}  max {sd.max():.2f}")
for cap in [0.4, 0.5, 0.6, 0.8]:
    print(f"    cap {cap}: affects {100*(sd>cap).mean():5.1f}% of items; "
          f"a +2sd move becomes x{np.exp(2*cap):.1f} instead of up to x{np.exp(2*sd.max()):.0f}")

# ---------------------------------------------------------------- plot
C = pd.read_pickle(F.OUT / "level_curves.pkl")
df = F.load(); names = F.names()
fig = plt.figure(figsize=(15, 8.5))
gs = fig.add_gridspec(2, 3)
fig.suptitle("Comparison of synthetic noisy price walk vs. real data", fontsize=13, weight="bold")

a = fig.add_subplot(gs[0, 0])
a.plot(lags, list(TARGET.values()), "o-", c="k", label="measured")
a.plot(lags, syn_acf, "s--", c="crimson", label="synthetic")
a.axhline(0, lw=.8, c="grey"); a.set_xlabel("lag (hours)"); a.set_ylabel("autocorrelation")
a.set_title("Decorrelation (tau ~ 47h)"); a.legend(); a.grid(alpha=.3)

a = fig.add_subplot(gs[0, 1])
L = np.log(df.where(df > 0)); core = df.columns[F.classify(df) == "core"]
t = F.day_of_season(df.index).to_numpy()
S = np.empty((len(t), len(core))); A = L[core].to_numpy()
for i, (q, w) in enumerate(zip(t, F.window_for(t))):
    m = np.abs(t - q) <= w / 2
    if m.sum() < 5: m = np.argsort(np.abs(t - q))[:9]
    S[i] = np.nanmedian(A[m], axis=0)
real_z = ((A - S) / sd[core].to_numpy()).ravel(); real_z = real_z[np.isfinite(real_z)]
bins = np.linspace(-4, 4, 80)
a.hist(real_z, bins=bins, density=True, alpha=.55, label="measured", color="k")
a.hist(z_all, bins=bins, density=True, histtype="step", lw=2, label="synthetic", color="crimson")
a.set_yscale("log"); a.set_xlabel("standardised residual"); a.set_title("Distribution")
a.legend(); a.grid(alpha=.3)

a = fig.add_subplot(gs[0, 2])
a.hist(sd, bins=60, color="steelblue", alpha=.85)
a.axvline(sd.median(), c="crimson", lw=2, label=f"median {sd.median():.2f}")
a.set_xlabel("per-item sigma (log)"); a.set_ylabel("items"); a.set_title("Price walk amplitude")
a.legend(); a.grid(alpha=.3)

for j, iid in enumerate(["5d1b392c86f77425243e98fe", "5447a9cd4bdc2dbd208b4567", "5672cb724bdc2dc2088b456b"]):
    a = fig.add_subplot(gs[1, j])
    s = df[iid].dropna(); dd = F.day_of_season(s.index).to_numpy()
    keep = dd >= F.MAP_DAY_LO
    a.plot(dd[keep], s.to_numpy()[keep], ".", ms=2.5, alpha=.35, c="k", label="real")
    hh = np.arange(F.MAP_DAY_LO, 250, 0.25) * 24
    lv = F.day_to_level(hh / 24)
    trend = np.interp(lv, C.index, C[iid])
    a.plot(hh / 24, trend * N.multiplier(iid, hh, sd[iid]), lw=.7, c="crimson",
           alpha=.75, label="curve x price walk")
    a.plot(hh / 24, trend, lw=2.2, c="darkred", label="curve")
    lo, hi = np.nanpercentile(s.to_numpy()[keep], [1, 99])
    a.set_ylim(max(0, lo - (hi-lo)*.3), hi + (hi-lo)*.3)
    nm = names.get(iid, iid)[:28]
    a.set_title(f"{nm}  (sigma {sd[iid]:.2f})", fontsize=9.5)
    a.set_xlabel("season day"); a.grid(alpha=.25); a.tick_params(labelsize=8)
    a.yaxis.set_major_formatter(lambda v, p: f"{v/1000:,.0f}k" if v >= 1000 else f"{v:.0f}")
    if j == 0: a.legend(fontsize=7.5, markerscale=3)
plt.tight_layout(rect=[0, 0, 1, .96]); plt.savefig(F.DOCS_IMG / "noise_validation.png", dpi=130)

# ---------------------------------------------------------------- artefact
p = F.MOD_DATA / "price_curves.json"
art = json.load(open(p))
# Only what the mod must agree with the generator on. Anything the config owns
# (jump probability, jump size, sigma cap) is deliberately NOT repeated here -
# two sources of truth is how values drift apart.
# unitSd is written at FULL precision: the loader assigns it straight onto
# FleaNoise.UnitSd, so rounding it here silently shifts every price.
art["meta"]["noise"] = {"octaves": [{"knotHours": k, "weight": w} for k, w in N.OCTAVES],
                        "jumpKnotHours": N.JUMP_KNOT_H,
                        "unitSd": N.UNIT_SD}
art["noiseSigma"] = {c: round(float(sd[c]), 4) for c in art["price"] if c in sd.index}
json.dump(art, open(p, "w"), separators=(",", ":"))
print(f"\nwrote {p}  ({p.stat().st_size/1e6:.2f} MB)  +noiseSigma for {len(art['noiseSigma'])} items")
print(f"wrote {F.DOCS_IMG/'noise_validation.png'}")

# ---------------------------------------------------------------- test vectors
# The C# port is verified against these. Regenerated here so that changing the
# generator cannot leave stale vectors behind (see the root README).
_VEC_ITEMS = ["5d1b392c86f77425243e98fe", "5447a9cd4bdc2dbd208b4567",
              "5c0530ee86f774697952d952", "57347c93245977448d35f6e3",
              "5672cb724bdc2dc2088b456b"]
_VEC_HOURS = [0.0, 1.0, 1337.0, 48.0, 47.999, 100000.0, 481337.0, 8760.0]
_VEC_WORLDS = [0, 1, 1763200000, 1763200001, 2**63]

vectors = {
    "_comment": "Golden vectors for porting analysis/fleanoise.py to C#. A port is "
                "correct when every value matches to 1e-12. Regenerated by "
                "analysis/09_build_noise_model.py.",
    "unitSd": N.UNIT_SD,
    "octaves": [{"knotHours": k, "weight": w} for k, w in N.OCTAVES],
    "jump": {"knotHours": N.JUMP_KNOT_H, "q": N.JUMP_Q, "m": N.JUMP_M},
    "splitmix64": {str(x): str(N.splitmix64(x)) for x in [0, 1, 42, 2**63, 2**64 - 1]},
    "worldSeed": [{"profileId": "5c0530ee86f774697952d952", "registrationDate": r,
                   "seed": str(N.world_seed("5c0530ee86f774697952d952", r))}
                  for r in [0, 1763200000, 1763200001]],
    "seedOf": [{"item": i, "world": str(w), "seed": str(N.seed_of(i, w))}
               for i in _VEC_ITEMS[:3] for w in _VEC_WORLDS[:3]],
    "z": [{"item": i, "world": str(w), "hour": h,
           "z": float(N.z(N.seed_of(i, w), np.array([h]))[0])}
          for i in _VEC_ITEMS for w in _VEC_WORLDS for h in _VEC_HOURS],
}
_vp = F.MOD_DATA / "noise_test_vectors.json"
json.dump(vectors, open(_vp, "w"), indent=1)
print(f"wrote {_vp}  ({len(vectors['z'])} z-vectors across {len(_VEC_WORLDS)} worlds)")
