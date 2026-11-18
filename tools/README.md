# Map-building scripts

These rebuild `assets/terrain/`. You only need them to change the area, the
home address or the look of the terrain. They were first run as one-off
scripts, so check the file paths at the top of each before running.

| Script | What it does |
| --- | --- |
| `find_overture_roads.py` | Finds which parts of the Overture Maps road data cover the Wasatch. |
| `download_overture_roads.py` | Downloads those road segments to `roads_raw.parquet`. |
| `route_roads.py` | Works out the fastest roads from home to each resort, and draws the grey street grid. |
| `build_terrain_texture.py` | Downloads elevation tiles, paints snow, trees, rock and shading, and writes the terrain files. |
| `route_pieces.json` | Rough outlines used to split each route into the pieces that get their own traffic color. |

After rebuilding, run `python -m wasatch_display.prerender` to redraw the
pictures the light mode uses.

Extra libraries for these scripts: `pip install pyarrow requests shapely`.
