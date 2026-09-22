using System.Reflection;
using SPTarkov.Common.Models.Logging;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Extensions;
using SPTarkov.Server.Core.Generators.Ragfair;
using SPTarkov.Server.Core.Helpers.Profile;
using SPTarkov.Server.Core.Helpers.Server;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Models.Spt.Config;
using SPTarkov.Server.Core.Models.Spt.Tables;
using SPTarkov.Server.Core.Services.Profile;
using SPTarkov.Server.Core.Services.Ragfair;
using SPTarkov.Server.Core.Utils;
using SPTarkov.Server.Core.Utils.Cloners;

namespace FleaPriceLevelScaling;

/// <summary>
/// Scales flea prices by player level, replaying a real Tarkov season.
///
/// Level sets the trend; wall-clock hour sets a stateless price walk on top. Nothing
/// is written to the profile - the profile is only ever read, for the level and
/// for the per-playthrough market seed.
/// </summary>
[Injectable(TypePriority = OnLoadOrder.RagfairCallbacks - 2)]
public class FleaPriceLevelScalingMod(
    ISptLogger<FleaPriceLevelScalingMod> logger,
    TemplateTable templateTable,
    RagfairOfferService ragfairOfferService,
    RagfairOfferGenerator ragfairOfferGenerator,
    RagfairOfferHolder ragfairOfferHolder,
    RagfairConfig ragfairConfig,
    ProfileHelper profileHelper,
    ProfileActivityService profileActivityService,
    ModHelper modHelper,
    ICloner cloner) : IOnLoad, IOnUpdate
{
    private const string Tag = "[FleaPriceLevelScaling]";

    /// <summary>How often to re-check level and hour. The price walk moves on a 2-day
    /// timescale, so anything under a few minutes is wasted work.</summary>
    private const long UpdateIntervalSeconds = 120;

    private Config _config = new();
    private PriceTable? _table;
    private HashSet<MongoId> _blacklist = new();
    private Dictionary<MongoId, double> _originalPrices = new();
    private bool _active;

    private int _lastLevel = -1;
    private long _lastHour = -1;
    private ulong _lastWorld;

    private string ModFolder => modHelper.GetAbsolutePathToModFolder(Assembly.GetExecutingAssembly());

    public Task OnLoadAsync(CancellationToken cancellationToken)
    {
        try
        {
            _config = Config.Load(Path.Join(ModFolder, "config.jsonc"));
        }
        catch (Exception ex)
        {
            logger.Error($"{Tag} Could not read config.jsonc. Mod disabled.", ex);
            return Task.CompletedTask;
        }

        foreach (var note in _config.Sanitise()) logger.Warning($"{Tag} config: {note}");

        if (!_config.Enabled)
        {
            logger.Info($"{Tag} Disabled via config.");
            return Task.CompletedTask;
        }

        try
        {
            _table = PriceTable.Load(Path.Join(ModFolder, "data", "price_curves.json"), _config);
        }
        catch (Exception ex)
        {
            logger.Error($"{Tag} Could not read data/price_curves.json. Mod disabled.", ex);
            return Task.CompletedTask;
        }

        _blacklist = _config.Debug.ItemBlacklist
            .Where(id => !string.IsNullOrWhiteSpace(id))
            .Select(id => new MongoId(id))
            .ToHashSet();

        FleaNoise.JumpMultiplier = _config.PriceShockSize;
        FleaNoise.JumpProbability = _config.Debug.JumpProbability;

        // Take SPT's own flea pricing out of the loop, and keep a pristine copy of
        // the original table so price bounds stay anchored to it rather than to
        // whatever we wrote last pass.
        ragfairConfig.Dynamic.GenerateBaseFleaPrices.UseHandbookPrice = false;
        _originalPrices = cloner.Clone(templateTable.Prices)!;
        _active = true;

        logger.Success($"{Tag} Loaded {_table.LevelPrice.Count} item curves " +
                       $"from {_table.Info.Snapshots} real flea snapshots " +
                       $"(season day {_config.Debug.StartDay:0} -> {_config.Debug.EndDay:0} " +
                       $"across levels {_config.Debug.FleaUnlockLevel}-{_table.MaxLevel}).");

        Apply(regenerateRagfair: false);
        return Task.CompletedTask;
    }

    public Task<bool> OnUpdateAsync(long secondsSinceLastRun, CancellationToken cancellationToken)
    {
        if (!_active || secondsSinceLastRun < UpdateIntervalSeconds) return Task.FromResult(false);

        try
        {
            Apply(regenerateRagfair: true);
        }
        catch (Exception ex)
        {
            // Never let this escape into the server's update loop. Disable instead:
            // stale prices are a nuisance, a crashing update loop is not.
            logger.Error($"{Tag} Price update failed; disabling further updates. " +
                         "Prices stay as last applied until the server restarts.", ex);
            _active = false;
        }

        return Task.FromResult(true);
    }

    /// <summary>
    /// Recompute prices for the current level and hour. Cheap and idempotent: it
    /// returns immediately unless the level, the hour or the active profile changed.
    /// </summary>
    private void Apply(bool regenerateRagfair)
    {
        if (_table is null) return;

        var pmc = ResolveActiveProfile();
        var level = Math.Clamp(pmc?.Info?.Level ?? _config.Debug.FleaUnlockLevel, 1, _table.MaxLevel);
        var world = ResolveWorldSeed(pmc);
        var hour = (long)FleaNoise.CurrentHour();

        if (level == _lastLevel && hour == _lastHour && world == _lastWorld) return;

        var firstRun = _lastLevel < 0;
        if (firstRun && _config.Debug.LogWorldSeed)
            logger.Info($"{Tag} Market seed {world} (include this in bug reports). " +
                        $"Player level {level}.");
        else if (level != _lastLevel && !firstRun)
            logger.Info($"{Tag} Player level {_lastLevel} -> {level}, reprising flea.");

        _lastLevel = level;
        _lastHour = hour;
        _lastWorld = world;

        var prices = templateTable.Prices;
        var items = templateTable.Items;
        var noiseOn = _config.Noise.Enabled && _config.Noise.AmplitudeScale > 0;
        var minMult = _config.Debug.PriceBounds.Min;
        var maxMult = _config.Debug.PriceBounds.Max;
        var updated = 0;
        var skipped = 0;

        foreach (var (idText, _) in _table.LevelPrice)
        {
            if (!MongoId.IsValidMongoId(idText)) { skipped++; continue; }
            var id = new MongoId(idText);
            if (_blacklist.Contains(id)) continue;
            if (items is not null && !items.ContainsKey(id)) continue;

            var price = _table.PriceAt(idText, level);

            if (noiseOn && _table.Sigma.TryGetValue(idText, out var sigma))
            {
                var amplitude = Math.Min(sigma * _config.Noise.AmplitudeScale, _config.Debug.SigmaCap);
                price *= Math.Exp(amplitude * FleaNoise.Z(FleaNoise.SeedOf(idText, world), hour));
            }

            // Bound against SPT's ORIGINAL price
            if (_originalPrices.TryGetValue(id, out var basePrice) && basePrice > 0)
                price = Math.Clamp(price, basePrice * minMult, basePrice * maxMult);

            if (price < 1) price = 1;
            prices[id] = Math.Round(price);
            updated++;
        }

        if (skipped > 0)
            logger.Warning($"{Tag} Skipped {skipped} malformed item ids in the price table.");

        if (!regenerateRagfair)
        {
            logger.Info($"{Tag} Applied {updated} prices for level {level}.");
            return;
        }

        RegenerateRagfair();
    }

    /// <summary>Expire and rebuild the dynamic flea so offers use the new prices.</summary>
    private void RegenerateRagfair()
    {
        try
        {
            var stale = ragfairOfferHolder.GetStaleOfferIds();
            foreach (var offer in ragfairOfferHolder.GetOffers())
            {
                if (offer.IsTraderOffer() || offer.IsPlayerOffer() || stale.Contains(offer.Id)) continue;
                ragfairOfferHolder.FlagOfferAsExpired(offer.Id);
            }

            ragfairOfferService.RemoveExpiredOffers();
            ragfairOfferGenerator.GenerateDynamicOffers();
        }
        catch (Exception ex)
        {
            logger.Error($"{Tag} Failed to regenerate flea offers; prices are updated " +
                         "but existing offers may be stale until the next refresh.", ex);
        }
    }

    /// <summary>
    /// The price table is global but the level is per-profile, so pick the profile
    /// that is actually playing. Falls back to the only profile if there is exactly
    /// one, which is the normal single-player case before the client connects.
    /// </summary>
    private PmcData? ResolveActiveProfile()
    {
        try
        {
            foreach (var sessionId in profileActivityService.GetActiveProfileIdsWithinMinutes(30))
            {
                var pmc = profileHelper.GetPmcProfile(new MongoId(sessionId));
                if (pmc?.Info?.Level is not null) return pmc;
            }

            var profiles = profileHelper.GetProfiles();
            if (profiles.Count == 1)
            {
                var pmc = profileHelper.GetPmcProfile(profiles.Keys.First());
                if (pmc?.Info?.Level is not null) return pmc;
            }
        }
        catch (Exception ex)
        {
            logger.Warning($"{Tag} Could not resolve the active profile ({ex.Message}); " +
                           "using flea-unlock prices until one is available.");
        }

        return null;
    }

    /// <summary>
    /// Per-playthrough market seed, derived read-only from the profile.
    /// RegistrationDate changes when a new character is made, so a wipe gets a
    /// fresh market even on the same account.
    /// </summary>
    private ulong ResolveWorldSeed(PmcData? pmc)
    {
        if (_config.Debug.WorldSeedOverride is { } forced) return forced;
        if (!_config.Debug.PerPlaythrough) return 0UL;

        var id = pmc?.Id.ToString();
        var registered = pmc?.Info?.RegistrationDate ?? 0;
        if (string.IsNullOrEmpty(id) || id.Length < 24) return 0UL;

        try { return FleaNoise.WorldSeed(id, registered); }
        catch { return 0UL; }
    }
}
