**Flea market prices change as you level up**

Static flea prices didn't seem fun to us. It was way too easy to get money early on.
There's the great [Live Flea Prices](https://sp-mod.com/mod/1131/live-flea-prices) mod.
But that is mirroring the current wipe and not your actual SPT progression.
We decided to built on the basis of this mod and use the provided data to simulate
flea market movement over a wipe.

To do that, we map seasonal flea prices to player level: at level 15 you see flea prices as
in the beginning of a wipe, at level 79 you see flea prices as in the end of a
wipe.

[image: docs/img/season_overview.png]

The prices we used to model this come from **948 real snapshots** of the live
flea market, taken every six hours across the entire 1.0 season (15
November 2025 to 2 August 2026).

For a typical item, the arc looks like this:

| Your level | 15 | 20 | 21 | 40 | 60 | 79 |
|---|---|---|---|---|---|---|
| Price | 100% | 67% | **65%** | 74% | 87% | 87% |

Expensive when everything is sparse at the beginning, bottoming out around
level 21, then inflation up to level 60.

At default config the whole season is mapped between level 15 and level **60**. 
The real season only lasted 250 days, and in that time live players got to roughly
level 50-70. We decided against assuming the end of the season was a level 79 state.
Instead we cap the price trend movement from level 60 onward. They just keep drifting 
day to day. You can move that line with `scalingMaxLevel` (see the Configuration tab).

The graph above only shows the average. Individual items may behave differently:

| Item | Level 15 | Level 60 | |
|---|---|---|---|
| **Respirator** | ₽8,800 | ₽49,200 | x5.6 - strong inflation |
| **Geiger counter** | ₽27,400 | ₽89,400 | x3.3 - medium inflation |
| **Gunpowder "Kite"** | ₽18,700 | ₽18,700 | x1.0 - doesn't seem to move in live data |
| **Colt M4A1** | ₽111,000 | ₽47,900 | x0.43 - deflation for common items |
| **Gas station key** | ₽755,000 | ₽20,300 | x0.03 - extreme deflation |

Prices also **drift from day to day**, independent of leveling, mirroring the
spikes and drops we see in real supply and demand. The seed is calculated from
your profile ID and registration date, so every playthrough sees different
market movement.

[image: docs/img/playthrough.png]

*Two characters' playthroughs showing different market movement around the
same underlying trend (black).*

## Credits

Price data comes from
[DrakiaXYZ/SPT-LiveFleaPriceDB](https://github.com/DrakiaXYZ/SPT-LiveFleaPriceDB),
the same source the excellent [Live Flea Prices](https://sp-mod.com/mod/1131/live-flea-prices)
mod uses. This mod takes a different angle on it: prices adapt to your
character level to simulate a season, rather than tracking the live market
in real time.
