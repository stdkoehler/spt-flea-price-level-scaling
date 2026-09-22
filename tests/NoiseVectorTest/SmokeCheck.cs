using FleaPriceLevelScaling;

namespace NoiseVectorTest;

/// <summary>
/// End-to-end smoke test: parse the real config.jsonc (comments and all), load the
/// real table, and print what a player would actually be charged.
/// </summary>
public static class SmokeCheck
{
    public static int Run(string configPath, string tablePath)
    {
        var problems = 0;

        var cfg = Config.Load(configPath);
        Console.WriteLine($"  config.jsonc parsed: enabled={cfg.Enabled} " +
                          $"intensity={cfg.IntensityExponent} cap={cfg.ScalingMaxLevel} " +
                          $"shock={cfg.PriceShockSize} noise={cfg.Noise.Enabled}/{cfg.Noise.AmplitudeScale}");
        Console.WriteLine($"  debug: startDay={cfg.Debug.StartDay} endDay={cfg.Debug.EndDay} " +
                          $"perPlaythrough={cfg.Debug.PerPlaythrough} sigmaCap={cfg.Debug.SigmaCap} " +
                          $"unlock={cfg.Debug.FleaUnlockLevel}");

        foreach (var note in cfg.Sanitise())
        {
            Console.WriteLine($"  UNEXPECTED sanitise note on shipped defaults: {note}");
            problems++;
        }

        FleaNoise.JumpMultiplier = cfg.PriceShockSize;
        FleaNoise.JumpProbability = cfg.Debug.JumpProbability;

        var table = PriceTable.Load(tablePath, cfg);
        Console.WriteLine($"  table: {table.LevelPrice.Count} curves, {table.Sigma.Count} sigmas, " +
                          $"maxLevel={table.MaxLevel}, unitSd={FleaNoise.UnitSd:R}");

        if (table.LevelPrice.Count < 2000) { Console.WriteLine("  TOO FEW CURVES"); problems++; }

        var world = FleaNoise.WorldSeed("5c0530ee86f774697952d952", 1763200000);
        var hour = 481337.0;
        string[] items = ["5d1b392c86f77425243e98fe", "5447a9cd4bdc2dbd208b4567", "5672cb724bdc2dc2088b456b"];
        string[] names = ["Light bulb", "Colt M4A1", "Geiger counter"];

        // lvl 60 and 79 straddle scalingMaxLevel, so they should be identical:
        // above the cap the trend is held and only the price walk moves.
        Console.WriteLine($"\n  {"item",-16}{"lvl 1",12}{"lvl 15",12}{"lvl 40",12}{"lvl 60",12}{"lvl 79",12}   (trend only)");
        for (var i = 0; i < items.Length; i++)
        {
            var row = $"  {names[i],-16}";
            foreach (var lv in new[] { 1, 15, 40, 60, 79 }) row += $"{table.PriceAt(items[i], lv),12:N0}";
            Console.WriteLine(row);
        }

        foreach (var it in items)
            if (Math.Abs(table.PriceAt(it, cfg.ScalingMaxLevel) - table.PriceAt(it, 79)) > 1e-6)
            {
                Console.WriteLine($"  TREND NOT FLAT ABOVE scalingMaxLevel for {it[..8]}..");
                problems++;
            }

        Console.WriteLine($"\n  {"item",-16}{"lvl 15",12}{"lvl 40",12}{"lvl 79",12}   (with price walk @ hour {hour})");
        for (var i = 0; i < items.Length; i++)
        {
            var row = $"  {names[i],-16}";
            foreach (var lv in new[] { 15, 40, 79 })
            {
                var p = table.PriceAt(items[i], lv);
                if (table.Sigma.TryGetValue(items[i], out var s))
                {
                    var amp = Math.Min(s * cfg.Noise.AmplitudeScale, cfg.Debug.SigmaCap);
                    p *= Math.Exp(amp * FleaNoise.Z(FleaNoise.SeedOf(items[i], world), hour));
                }
                row += $"{Math.Round(p),12:N0}";
            }
            Console.WriteLine(row);
        }

        // levels below the unlock must clamp to the unlock price
        foreach (var it in items)
            if (Math.Abs(table.PriceAt(it, 1) - table.PriceAt(it, cfg.Debug.FleaUnlockLevel)) > 1e-6)
            {
                Console.WriteLine($"  CLAMP BROKEN for {it}"); problems++;
            }

        // every price must be finite and positive at every level
        var bad = 0;
        foreach (var (_, curve) in table.LevelPrice)
            foreach (var v in curve)
                if (double.IsNaN(v) || double.IsInfinity(v) || v <= 0) bad++;
        Console.WriteLine($"\n  non-finite or non-positive price entries: {bad}");
        if (bad > 0) problems++;

        return problems;
    }
}
