using System.Text.Json;
using System.Text.Json.Serialization;

namespace FleaPriceLevelScaling;

/// <summary>
/// Player-facing settings. Mirrors config.jsonc; see the root README for the
/// human-readable descriptions.
/// </summary>
public class Config
{
    public bool Enabled { get; set; } = true;

    /// <summary>How hard prices react to level. Applied to the RATIO.</summary>
    public double IntensityExponent { get; set; } = 1.0;

    /// <summary>
    /// Level that endDay maps to. Above it the trend is held flat and only the
    /// price walk moves - see docs/TECHNICAL.md section 5.
    /// </summary>
    public int ScalingMaxLevel { get; set; } = 60;

    /// <summary>Size of rare price shocks (fleanoise JUMP_M). 1.0 = no shocks.</summary>
    public double PriceShockSize { get; set; } = 4.0;

    public NoiseConfig Noise { get; set; } = new();
    public DebugConfig Debug { get; set; } = new();

    public class NoiseConfig
    {
        public bool Enabled { get; set; } = true;
        public double AmplitudeScale { get; set; } = 1.0;
    }

    public class DebugConfig
    {
        public double StartDay { get; set; } = 10.0;
        public double EndDay { get; set; } = 249.0;
        public bool PerPlaythrough { get; set; } = true;
        public ulong? WorldSeedOverride { get; set; }
        public bool LogWorldSeed { get; set; } = true;
        public PriceBoundsConfig PriceBounds { get; set; } = new();
        public double SigmaCap { get; set; } = 0.5;
        public double JumpProbability { get; set; } = 0.04;
        public int FleaUnlockLevel { get; set; } = 15;
        public List<string> ItemBlacklist { get; set; } = new();
    }

    public class PriceBoundsConfig
    {
        public double Min { get; set; } = 0.2;
        public double Max { get; set; } = 5.0;
    }

    /// <summary>
    /// Parsed by hand rather than through ModHelper, because config.jsonc carries
    /// comments and trailing commas that a strict reader rejects.
    /// </summary>
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
        NumberHandling = JsonNumberHandling.AllowReadingFromString
    };

    public static Config Load(string path)
    {
        return JsonSerializer.Deserialize<Config>(File.ReadAllText(path), Options) ?? new Config();
    }

    /// <summary>Clamp to meaningful range.</summary>
    public List<string> Sanitise()
    {
        var notes = new List<string>();

        void Clamp(string name, ref double value, double lo, double hi)
        {
            if (value >= lo && value <= hi) return;
            var original = value;
            value = Math.Clamp(value, lo, hi);
            notes.Add($"{name} was {original}, clamped to {value}");
        }

        var v = IntensityExponent; Clamp(nameof(IntensityExponent), ref v, 0.0, 10.0); IntensityExponent = v;
        v = PriceShockSize; Clamp(nameof(PriceShockSize), ref v, 1.0, 20.0); PriceShockSize = v;
        v = Noise.AmplitudeScale; Clamp("noise.amplitudeScale", ref v, 0.0, 10.0); Noise.AmplitudeScale = v;
        v = Debug.SigmaCap; Clamp("debug.sigmaCap", ref v, 0.0, 5.0); Debug.SigmaCap = v;
        v = Debug.JumpProbability; Clamp("debug.jumpProbability", ref v, 0.0, 1.0); Debug.JumpProbability = v;
        v = Debug.PriceBounds.Min; Clamp("debug.priceBounds.min", ref v, 0.001, 1.0); Debug.PriceBounds.Min = v;
        v = Debug.PriceBounds.Max; Clamp("debug.priceBounds.max", ref v, 1.0, 1000.0); Debug.PriceBounds.Max = v;

        if (Debug.FleaUnlockLevel is < 1 or > 78)
        {
            notes.Add($"debug.fleaUnlockLevel was {Debug.FleaUnlockLevel}, reset to 15");
            Debug.FleaUnlockLevel = 15;
        }

        // Checked after fleaUnlockLevel so the comparison uses the corrected value.
        if (ScalingMaxLevel <= Debug.FleaUnlockLevel || ScalingMaxLevel > 79)
        {
            var original = ScalingMaxLevel;
            ScalingMaxLevel = Math.Clamp(ScalingMaxLevel, Debug.FleaUnlockLevel + 1, 79);
            notes.Add($"scalingMaxLevel was {original}, clamped to {ScalingMaxLevel} " +
                      $"(must be above fleaUnlockLevel {Debug.FleaUnlockLevel} and at most 79)");
        }

        if (Debug.EndDay <= Debug.StartDay)
        {
            notes.Add($"debug.endDay ({Debug.EndDay}) must exceed startDay ({Debug.StartDay}); reset to defaults");
            Debug.StartDay = 10.0;
            Debug.EndDay = 249.0;
        }

        return notes;
    }
}
