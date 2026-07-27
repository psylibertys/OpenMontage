# TreeElf shared music catalog

The source audio remains in `/Users/treeelf/Desktop/crewai/music/music-sucai/纯音乐`.
Only metadata and usage history live in OpenMontage.

Build or refresh the catalog:

```bash
.venv/bin/python scripts/build_treeelf_music_catalog.py
```

`catalog-v1.json` is generated. Put human ratings, tags, rights information, or
`enabled: false` in `manual-overrides-v1.json`; rebuilds do not overwrite it.
Both TreeElf series append selections to `usage-ledger-v1.json` under a file
lock so recent tracks receive a ranking penalty across batches.
