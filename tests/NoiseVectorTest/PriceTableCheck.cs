using System.Text.Json;
using FleaPriceLevelScaling;

namespace NoiseVectorTest;

/// <summary>
/// Verifies PriceTable.Load against golden vectors from the Python reference:
/// day-knot interpolation, the intensity exponent, and the level cap.
/// </summary>
public static class PriceTableCheck
{
    public static (int pass, int fail) Run(string tablePath, string vectorPath)
    {
        int pass = 0, fail = 0;
        using var doc = JsonDocument.Parse(File.ReadAllText(vectorPath));

        foreach (var c in doc.RootElement.GetProperty("cases").EnumerateArray())
        {
            var name = c.GetProperty("name").GetString()!;
            var cfg = new Config
            {
                IntensityExponent = c.GetProperty("intensityExponent").GetDouble(),
                ScalingMaxLevel = c.GetProperty("scalingMaxLevel").GetInt32()
            };
            cfg.Debug.StartDay = c.GetProperty("startDay").GetDouble();
            cfg.Debug.EndDay = c.GetProperty("endDay").GetDouble();
            // deliberately NOT sanitised: the vectors exercise raw values,
            // including out-of-range days that Load is expected to clamp.

            var table = PriceTable.Load(tablePath, cfg);
            var caseFail = 0;

            foreach (var item in c.GetProperty("items").EnumerateObject())
            {
                foreach (var lv in item.Value.EnumerateObject())
                {
                    var level = int.Parse(lv.Name);
                    var want = lv.Value.GetDouble();
                    var got = table.PriceAt(item.Name, level);
                    // relative tolerance: these are large rouble values
                    var tol = Math.Max(1e-9, Math.Abs(want) * 1e-9);
                    if (Math.Abs(got - want) <= tol) pass++;
                    else
                    {
                        fail++; caseFail++;
                        if (caseFail <= 3)
                            Console.WriteLine($"  FAIL [{name}] {item.Name[..8]}.. lvl {level}\n" +
                                              $"       got  {got:R}\n       want {want:R}");
                    }
                }
            }

            Console.WriteLine($"  {name,-16} {(caseFail == 0 ? "ok" : $"{caseFail} FAILED")}");
        }

        return (pass, fail);
    }
}
