# Killfeed icon templates

`chaos_lib/analyzers.py` matches each icon in a killfeed row against these
images to flag a kill (see `_ICON_FLAGS` there):

| File stem  | Flag            | Icon                                   |
|------------|-----------------|----------------------------------------|
| `blind`    | `attackerBlind` | crossed-out eye, before the killer     |
| `noscope`  | `noScope`       | crossed-out scope                      |
| `smoke`    | `throughSmoke`  | smoke cloud                            |
| `wallbang` | `wallbang`      | door with a bullet through it          |
| `headshot` | `isHeadshot`    | head with a bullet                     |

Only the white/grey pixels count, so the background and any red border left
in a crop are ignored. To add another example of an icon (e.g. from a
different HUD scale), crop it tightly from a screenshot and save it as
`<stem>_<n>.png`, like `headshot_2.png`.
