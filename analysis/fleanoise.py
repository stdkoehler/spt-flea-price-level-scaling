"""Stateless market price walk: the reference implementation the C# mod mirrors.

Fitted in 09_build_noise_model.py against the residual measured in 08_residual_noise.py:
  ACF  tau ~ 47h, matched by three smoothstep octaves (12h / 48h / 240h)
  tails matched by a jump mixture (4% of 48h knots scaled x4)

Deterministic in (itemId, hour). No state, no persistence, seeding by profile.
"""
import numpy as np

OCTAVES = [(12, 0.30), (48, 0.40), (240, 0.30)]   # (knot hours, weight)
JUMP_KNOT_H, JUMP_Q, JUMP_M = 48, 0.04, 4.0
MASK = (1 << 64) - 1

def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & MASK
    z = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)

def _knot_pair(seed, knots, salt):
    """one standard normal + one uniform per knot, from a pure hash"""
    h = [splitmix64((int(seed) * 0x100000001B3 + int(k) * 0x9E3779B1 + salt) & MASK) for k in knots]
    u1 = np.clip(np.array([float(x >> 11) / (1 << 53) for x in h]), 1e-12, 1.0)
    u2 = np.array([float(splitmix64(int(x)) >> 11) / (1 << 53) for x in h])
    return np.sqrt(-2 * np.log(u1)) * np.cos(2 * np.pi * u2), u2

def _interp(hours, knot_h, values_by_knot):
    k = np.floor(hours / knot_h).astype(int)
    f = hours / knot_h - k
    s = f * f * (3 - 2 * f)                       # smoothstep
    a = np.array([values_by_knot[i] for i in k])
    b = np.array([values_by_knot[i + 1] for i in k])
    return a * (1 - s) + b * s

def z(seed, hours):
    """unit-variance price walk in log space"""
    hours = np.atleast_1d(np.asarray(hours, float))
    out = np.zeros_like(hours)
    for i, (kh, w) in enumerate(OCTAVES):
        ks = np.arange(int(np.floor(hours.min() / kh)), int(np.floor(hours.max() / kh)) + 2)
        g, _ = _knot_pair(seed, ks, i * 7919)
        out += w * _interp(hours, kh, dict(zip(ks, g)))
    ks = np.arange(int(np.floor(hours.min() / JUMP_KNOT_H)), int(np.floor(hours.max() / JUMP_KNOT_H)) + 2)
    _, u = _knot_pair(seed, ks, 55555)
    out *= _interp(hours, JUMP_KNOT_H, dict(zip(ks, np.where(u < JUMP_Q, JUMP_M, 1.0))))
    return out / UNIT_SD

def hex_id(mongo_id):
    """24-hex-char id -> 64 bits"""
    return int(mongo_id[:16], 16) ^ int(mongo_id[16:], 16)

def world_seed(profile_id, registration_date):
    """Per-playthrough constant, read-only from the profile.

    RegistrationDate changes on every new character, so a wipe gets a fresh
    market even on the same account; profile_id separates concurrent profiles.
    splitmix64 avalanche means seeds differing by 1 second are uncorrelated.
    """
    return splitmix64(hex_id(profile_id) ^ (int(registration_date) & MASK))

def seed_of(template_id, world=0):
    """stable 64-bit seed from a template id, optionally per playthrough"""
    return splitmix64(hex_id(template_id) ^ splitmix64(int(world) & MASK))

def multiplier(template_id, hours, sigma, world=0):
    """price multiplier: median 1.0, log-sd = sigma"""
    return np.exp(sigma * z(seed_of(template_id, world), hours))

UNIT_SD = 1.0
def _calibrate():
    global UNIT_SD
    h = np.arange(0, 20000, 1.0)
    UNIT_SD = float(np.std(np.concatenate([z(s, h) for s in range(1, 12)])))
_calibrate()
