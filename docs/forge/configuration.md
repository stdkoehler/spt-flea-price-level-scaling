Edit `config.jsonc`:

| Setting | Default | Range | What it does |
|---|---|---|---|
| `enabled` | `true` | - | Turn the mod off without uninstalling it. |
| `intensityExponent` | `1.0` | `0` - `10` | How hard prices react to your level. `0` = no scaling. `1` = as real economy. `2` = increased swing. |
| `scalingMaxLevel` | `60` | `16` - `79` | The level where the season runs out. Above it, prices stop trending and only drift. |
| `priceShockSize` | `4.0` | `1` - `20` | How violent occasional price spikes are. `1` = no shocks, just gentle drift. |
| `noise.enabled` | `true` | - | Whether prices drift day to day at all. |
| `noise.amplitudeScale` | `1.0` | `0` - `10` | How big that daily drift is. `0` = off, `2` = more chaotic. |

Out-of-range values are clamped automatically on load (with a note in the
server log).

Debug settings (day/level mapping, price bounds, drift tuning) are documented
inline in `config.jsonc` and in the full README on GitHub.

[image: docs/img/config_effects.png]

## Known quirks

- **Some prices look odd sometimes.** These are price shocks seen in real flea
  data. Set `priceShockSize` to `1` if you don't like that, or disable noise
  entirely with `noise.enabled = false`.
- **Prices move even when you're not playing.** The drift follows real time.
- **Early-wipe prices on some items (rare keys, quest items) are enormous.**
  Change `startDay` in the debug settings to a later day (e.g. `79`) if you
  don't like that.
