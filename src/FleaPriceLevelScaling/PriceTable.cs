using System.Text.Json;
using System.Text.Json.Serialization;

namespace FleaPriceLevelScaling;

/// <summary>
/// The day-indexed price curves produced by analysis/07_build_trend_curves.py, resampled
/// onto player levels using the configured startDay / endDay mapping.
/// </summary>
public class PriceTable
{
    public sealed class Meta
    {
        // Only fields this code actually uses are deserialised. Provenance fields
        // (seasonStart, source, filter, defaultStartDay, ...) stay in the JSON for
        // humans but are deliberately not bound, so nobody edits one expecting an effect.
        [JsonPropertyName("maxLevel")]  public int MaxLevel { get; set; } = 79;
        [JsonPropertyName("snapshots")]       public int Snapshots { get; set; }
        [JsonPropertyName("noise")]           public NoiseMeta? Noise { get; set; }
    }

    public sealed class NoiseMeta
    {
        [JsonPropertyName("unitSd")]        public double UnitSd { get; set; }
        [JsonPropertyName("jumpKnotHours")] public double JumpKnotHours { get; set; }
        [JsonPropertyName("octaves")]       public OctaveMeta[]? Octaves { get; set; }
    }

    public sealed class OctaveMeta
    {
        [JsonPropertyName("knotHours")] public double KnotHours { get; set; }
        [JsonPropertyName("weight")]    public double Weight { get; set; }
    }

    private sealed class Raw
    {
        [JsonPropertyName("meta")]       public Meta? Meta { get; set; }
        [JsonPropertyName("dayKnots")]   public double[]? DayKnots { get; set; }
        [JsonPropertyName("price")]      public Dictionary<string, double[]>? Price { get; set; }
        [JsonPropertyName("noiseSigma")] public Dictionary<string, double>? NoiseSigma { get; set; }
    }

    public Meta Info { get; private set; } = new();

    /// <summary>templateId -> price at each level, index 0 = level 1.</summary>
    public Dictionary<string, double[]> LevelPrice { get; } = new();

    /// <summary>templateId -> price walk amplitude in log space.</summary>
    public Dictionary<string, double> Sigma { get; } = new();

    public int MaxLevel => Info.MaxLevel;

    /// <summary>
    /// Load the table and bake it down to per-level prices.
    ///
    /// Order matters. The intensity exponent is applied to the RATIO against the
    /// anchor, so it stretches the arc without moving the base price and without
    /// exponentiating the noise.
    /// </summary>
    public static PriceTable Load(string path, Config config)
    {
        var raw = JsonSerializer.Deserialize<Raw>(File.ReadAllText(path))
                  ?? throw new InvalidDataException("price table did not parse");
        if (raw.DayKnots is null || raw.DayKnots.Length < 2 || raw.Price is null)
            throw new InvalidDataException("price table is missing dayKnots or price data");

        var table = new PriceTable { Info = raw.Meta ?? new Meta() };

        var knots = raw.DayKnots;

        var unlock = config.Debug.FleaUnlockLevel;
        var maxLevel = table.Info.MaxLevel;
        if (maxLevel <= unlock) maxLevel = Math.Max(unlock + 1, 79);
        table.Info.MaxLevel = maxLevel;

        // level -> season day, clamped to the table's own range so a silly
        // startDay in the config cannot extrapolate off the end of the data.
        var dayLo = Math.Clamp(config.Debug.StartDay, knots[0], knots[^1]);
        var dayHi = Math.Clamp(config.Debug.EndDay, knots[0], knots[^1]);

        // endDay maps to scalingMaxLevel, NOT to maxLevel. Above the cap the
        // clamp below pins frac at 1.0, so the trend holds at dayHi while the
        // price walk (a function of wall-clock hour, never of level) keeps moving.
        var cap = Math.Clamp(config.ScalingMaxLevel, unlock + 1, maxLevel);

        var days = new double[maxLevel];
        for (var lv = 1; lv <= maxLevel; lv++)
        {
            var frac = Math.Clamp((lv - (double)unlock) / (cap - unlock), 0.0, 1.0);
            days[lv - 1] = dayLo + frac * (dayHi - dayLo);
        }

        foreach (var (id, curve) in raw.Price)
        {
            if (curve.Length != knots.Length) continue;

            var anchor = Interpolate(knots, curve, dayLo);
            if (anchor <= 0) continue;

            var levels = new double[maxLevel];
            for (var i = 0; i < maxLevel; i++)
            {
                var value = Interpolate(knots, curve, days[i]);
                var ratio = value / anchor;
                if (ratio <= 0) ratio = 1e-6;
                levels[i] = anchor * Math.Pow(ratio, config.IntensityExponent);
            }

            table.LevelPrice[id] = levels;
        }

        if (raw.NoiseSigma is not null)
            foreach (var (id, sigma) in raw.NoiseSigma)
                table.Sigma[id] = sigma;

        // The data file records the noise parameters it was generated with. Verify
        // them rather than trusting them: if the generator and this code disagree,
        // every price is subtly wrong in a way nothing else would surface.
        if (raw.Meta?.Noise is { } noise) VerifyNoiseParameters(noise);

        return table;
    }

    /// <summary>
    /// Cross-check the shipped noise parameters against the compiled generator.
    /// A mismatch means the table was built by a different version of
    /// analysis/fleanoise.py than this code implements, so the price walk would be
    /// wrong everywhere. Fail loudly rather than shipping quietly-wrong prices.
    /// </summary>
    private static void VerifyNoiseParameters(NoiseMeta noise)
    {
        if (noise.UnitSd <= 0)
            throw new InvalidDataException("price table is missing meta.noise.unitSd");

        // Full precision matters: this value divides every price walk sample.
        if (Math.Abs(noise.UnitSd - FleaNoise.UnitSd) > 1e-12)
            throw new InvalidDataException(
                $"meta.noise.unitSd ({noise.UnitSd:R}) does not match the compiled " +
                $"FleaNoise.UnitSd ({FleaNoise.UnitSd:R}). Regenerate the table with " +
                "analysis/09_build_noise_model.py, or update FleaNoise.");

        if (Math.Abs(noise.JumpKnotHours - FleaNoise.JumpKnotHours) > 1e-12)
            throw new InvalidDataException(
                $"meta.noise.jumpKnotHours ({noise.JumpKnotHours}) does not match " +
                $"FleaNoise.JumpKnotHours ({FleaNoise.JumpKnotHours}).");

        var octaves = noise.Octaves ?? [];
        if (octaves.Length != FleaNoise.Octaves.Length)
            throw new InvalidDataException(
                $"price table declares {octaves.Length} noise octaves, FleaNoise implements " +
                $"{FleaNoise.Octaves.Length}.");

        for (var i = 0; i < octaves.Length; i++)
        {
            var (knot, weight) = FleaNoise.Octaves[i];
            if (Math.Abs(octaves[i].KnotHours - knot) > 1e-12 ||
                Math.Abs(octaves[i].Weight - weight) > 1e-12)
                throw new InvalidDataException(
                    $"noise octave {i} is ({octaves[i].KnotHours}h x {octaves[i].Weight}) in the " +
                    $"price table but ({knot}h x {weight}) in FleaNoise.");
        }
    }

    /// <summary>Linear interpolation on a sorted knot grid; clamps outside the range.</summary>
    private static double Interpolate(double[] xs, double[] ys, double x)
    {
        if (x <= xs[0]) return ys[0];
        if (x >= xs[^1]) return ys[^1];

        var lo = 0;
        var hi = xs.Length - 1;
        while (hi - lo > 1)
        {
            var mid = (lo + hi) / 2;
            if (xs[mid] <= x) lo = mid; else hi = mid;
        }

        var span = xs[hi] - xs[lo];
        if (span <= 0) return ys[lo];
        var t = (x - xs[lo]) / span;
        return ys[lo] + t * (ys[hi] - ys[lo]);
    }

    /// <summary>Trend price for an item at a level. Levels below the flea unlock clamp.</summary>
    public double PriceAt(string templateId, int level)
    {
        var curve = LevelPrice[templateId];
        var idx = Math.Clamp(level, 1, curve.Length) - 1;
        return curve[idx];
    }
}
