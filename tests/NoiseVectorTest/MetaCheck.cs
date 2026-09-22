using System.Text.Json;
using System.Text.Json.Nodes;
using FleaPriceLevelScaling;

namespace NoiseVectorTest;

/// <summary>
/// Guards the data/code contract for the noise parameters.
///
/// This exists because of a real bug: the generator wrote unitSd rounded to six
/// decimals, PriceTable.Load assigned it straight onto FleaNoise.UnitSd, and the
/// z-vector assertions ran BEFORE Load - so they checked the compiled constant and
/// never saw the clobbered one. Production used the rounded value; the tests did not.
/// </summary>
public static class MetaCheck
{
    public static (int pass, int fail) Run(string tablePath)
    {
        int pass = 0, fail = 0;

        void Expect(string what, bool ok)
        {
            if (ok) pass++;
            else { fail++; Console.WriteLine($"  FAIL {what}"); }
        }

        // 1. Loading the real table must leave the calibration constant exact.
        var before = FleaNoise.UnitSd;
        PriceTable.Load(tablePath, new Config());
        Expect($"UnitSd unchanged by Load (was {before:R}, now {FleaNoise.UnitSd:R})",
               FleaNoise.UnitSd == before);

        // 2. A table built with different noise parameters must be rejected, not
        //    silently used. One case per field the loader verifies.
        var original = JsonNode.Parse(File.ReadAllText(tablePath))!;
        var tmp = Path.Combine(Path.GetTempPath(), "fps_tampered.json");

        void Tamper(string label, Action<JsonNode> mutate)
        {
            var clone = JsonNode.Parse(original.ToJsonString())!;
            mutate(clone);
            File.WriteAllText(tmp, clone.ToJsonString());
            try
            {
                PriceTable.Load(tmp, new Config());
                fail++;
                Console.WriteLine($"  FAIL tampered {label} was ACCEPTED");
            }
            catch (InvalidDataException)
            {
                pass++;
            }
        }

        Tamper("unitSd (rounded to 6dp - the original bug)",
               n => n["meta"]!["noise"]!["unitSd"] = Math.Round(FleaNoise.UnitSd, 6));
        Tamper("jumpKnotHours",
               n => n["meta"]!["noise"]!["jumpKnotHours"] = 24.0);
        Tamper("octave weight",
               n => n["meta"]!["noise"]!["octaves"]![1]!["weight"] = 0.41);
        Tamper("octave count",
               n => n["meta"]!["noise"]!["octaves"] = new JsonArray(
                       new JsonObject { ["knotHours"] = 12.0, ["weight"] = 1.0 }));

        try { File.Delete(tmp); } catch { /* best effort */ }

        Console.WriteLine($"  UnitSd after all loads: {FleaNoise.UnitSd:R}");
        return (pass, fail);
    }
}
