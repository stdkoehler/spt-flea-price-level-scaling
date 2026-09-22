"""Tune the smoothing window.

One fixed window is wrong: the early-wipe crash needs a narrow window (a 60D
median is actively harmful there) while the flat late season wants a wide one.
Winner: an adaptive window w(day) = clip(5 + 0.25*day, 5, 60), see flealib.window_for.
Robust LOCAL LINEAR was also tried and is much worse - it extrapolates badly
across the held-out block during the crash.
"""
import numpy as np, pandas as pd, warnings
import flealib as F
warnings.filterwarnings("ignore")

df = F.load(); L = np.log(df.where(df > 0))
Lc = L[df.columns[F.classify(df) == "core"]].dropna(axis=1)
Lc = Lc.iloc[:, np.random.default_rng(0).choice(Lc.shape[1], 500, replace=False)]
t = F.day_of_season(Lc.index).to_numpy(); A = Lc.to_numpy()

BLOCK, BUF = 7.0, 3.0
folds = []
for s in np.arange(t.min(), t.max() - BLOCK, BLOCK * 2):
    te = (t >= s) & (t < s + BLOCK); tr = (t < s - BUF) | (t >= s + BLOCK + BUF)
    if te.sum() > 5 and tr.sum() > 100: folds.append((s, tr, te))
early = np.array([s < 45 for s, _, _ in folds])

def med_filter(wmin, alpha, wmax):
    def f(tt, AA, tq):
        out = np.empty((len(tq), AA.shape[1]))
        for i, q in enumerate(tq):
            w = np.clip(wmin + alpha * q, wmin, wmax)
            m = np.abs(tt - q) <= w / 2
            if m.sum() < 5: m = np.argsort(np.abs(tt - q))[:5]
            out[i] = np.median(AA[m], axis=0)
        return out
    return f

print(f"{'window schedule':34} {'overall':>8} {'early<45':>9} {'late':>8}")
for wmin, a, wmax in [(3, 0, 3), (14, 0, 14), (60, 0, 60), (3, .10, 30), (5, .15, 45),
                      (7, .20, 60), (5, .25, 60), (3, .30, 60), (10, .15, 50)]:
    fn = med_filter(wmin, a, wmax)
    per = np.array([np.median(np.abs(fn(t[tr], A[tr], t[te]) - A[te])) for _, tr, te in folds])
    tag = f"w=clip({wmin}+{a}*day,..,{wmax})"
    star = "  <-- chosen" if (wmin, a, wmax) == (5, .25, 60) else ""
    print(f"{tag:34} {per.mean():8.4f} {per[early].mean():9.4f} {per[~early].mean():8.4f}{star}")
