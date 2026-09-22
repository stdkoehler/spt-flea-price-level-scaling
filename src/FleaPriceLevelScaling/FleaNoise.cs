using System;

namespace FleaPriceLevelScaling;

/// <summary>
/// Stateless market price walk. A pure stateless function of (templateId, hour)
///
/// Correlation does NOT come from remembering previous values. Nearby hours fall
/// inside the same knot interval, so they hash the same two endpoints and merely
/// interpolate at different positions. The "history" is recomputed on demand from
/// the hash function, exactly like Perlin noise in terrain generation.
///
/// Port of analysis/fleanoise.py. Verify against data/noise_test_vectors.json.
/// </summary>
public static class FleaNoise
{
    /// <summary>Public so PriceTable can verify the data file was built with these.</summary>
    public static readonly (double KnotHours, double Weight)[] Octaves =
    {
        (12.0, 0.30), (48.0, 0.40), (240.0, 0.30)
    };

    public const double JumpKnotHours = 48.0;

    /// <summary>Fraction of 48h knots carrying a shock. Config: debug.jumpProbability.</summary>
    public static double JumpProbability = 0.04;

    /// <summary>Shock size. Config: priceShockSize. 1.0 disables shocks entirely.</summary>
    public static double JumpMultiplier = 4.0;

    /// <summary>
    /// Normalisation so z has unit variance. MUST match fleanoise.UNIT_SD exactly -
    /// it is an empirical calibration constant, and rounding it shifts every price.
    /// The loader overwrites this from meta.noise.unitSd so the two cannot drift.
    /// </summary>
    public static double UnitSd = 0.6261140207888283;

    private const double ToUnit = 1.0 / 9007199254740992.0;   // 1 / 2^53

    /// <summary>Public so the golden-vector test can exercise it directly.</summary>
    public static ulong SplitMix64(ulong x)
    {
        unchecked
        {
            x += 0x9E3779B97F4A7C15UL;
            ulong z = x;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }
    }

    /// <summary>Two hashed uniforms at one knot -> (gaussian, uniform).</summary>
    private static (double Gauss, double Uniform) Knot(ulong seed, long k, ulong salt)
    {
        unchecked
        {
            ulong h = SplitMix64(seed * 0x100000001B3UL + (ulong)k * 0x9E3779B1UL + salt);
            double u1 = (h >> 11) * ToUnit;
            if (u1 < 1e-12) u1 = 1e-12;
            double u2 = (SplitMix64(h) >> 11) * ToUnit;
            return (Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2), u2);
        }
    }

    private static double SmoothStep(double f) => f * f * (3.0 - 2.0 * f);

    /// <summary>24-hex-char id -> 64 bits.</summary>
    private static ulong HexId(string id)
    {
        return Convert.ToUInt64(id.Substring(0, 16), 16) ^ Convert.ToUInt64(id.Substring(16), 16);
    }

    /// <summary>
    /// Per-playthrough constant, derived READ-ONLY from the profile.
    ///
    /// Info.RegistrationDate changes whenever a new character is created, so a wipe
    /// gets a fresh market even on the same account; _id separates concurrent
    /// profiles. splitmix64 avalanche means two playthroughs started one second
    /// apart are uncorrelated (measured r = +0.008).
    ///
    /// Pass 0 for a market shared by every profile.
    /// </summary>
    public static ulong WorldSeed(string profileId, int registrationDate)
    {
        unchecked { return SplitMix64(HexId(profileId) ^ (ulong)(long)registrationDate); }
    }

    /// <summary>Stable 64-bit seed from a template id, optionally per playthrough.</summary>
    public static ulong SeedOf(string templateId, ulong world = 0UL)
    {
        unchecked { return SplitMix64(HexId(templateId) ^ SplitMix64(world)); }
    }

    /// <summary>Unit-variance price walk in log space for one item at one hour.</summary>
    public static double Z(ulong seed, double hour)
    {
        double v = 0.0;
        for (int i = 0; i < Octaves.Length; i++)
        {
            var (kh, w) = Octaves[i];
            long k = (long)Math.Floor(hour / kh);
            double s = SmoothStep(hour / kh - k);
            ulong salt = (ulong)(i * 7919);
            double g0 = Knot(seed, k, salt).Gauss;
            double g1 = Knot(seed, k + 1, salt).Gauss;
            v += w * (g0 * (1.0 - s) + g1 * s);
        }

        long jk = (long)Math.Floor(hour / JumpKnotHours);
        double js = SmoothStep(hour / JumpKnotHours - jk);
        double j0 = Knot(seed, jk, 55555UL).Uniform < JumpProbability ? JumpMultiplier : 1.0;
        double j1 = Knot(seed, jk + 1, 55555UL).Uniform < JumpProbability ? JumpMultiplier : 1.0;

        return v * (j0 * (1.0 - js) + j1 * js) / UnitSd;
    }

    /// <summary>Price multiplier with median 1.0 and log-sd <paramref name="sigma"/>.</summary>
    public static double Multiplier(string templateId, double hour, double sigma,
                                    double sigmaCap, ulong world = 0UL)
    {
        return Math.Exp(Math.Min(sigma, sigmaCap) * Z(SeedOf(templateId, world), hour));
    }

    /// <summary>Wall-clock hour index. The price walk advances on its own between raids.</summary>
    public static double CurrentHour() => DateTimeOffset.UtcNow.ToUnixTimeSeconds() / 3600.0;
}
