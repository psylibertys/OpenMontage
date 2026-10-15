# TreeElf shared music catalog

The source audio root is configured by `TREEELF_MUSIC_LIBRARY_DIR` in the
project `.env` (currently `/Users/treeelf/Desktop/crewai/music/music-sucai/纯音乐`).
Only metadata and usage history live in OpenMontage.

Build or refresh the catalog:

```bash
.venv/bin/python scripts/build_treeelf_music_catalog.py
```

`catalog-v1.json` is generated. Put human ratings, tags, rights information, or
`enabled: false` in `manual-overrides-v1.json`; rebuilds do not overwrite it.
Both TreeElf series append selections to `usage-ledger-v1.json` under a file
lock. A project reuses its reserved or committed track unless its episode
explicitly sets `reselect_music: true`. Reservations become `committed` only
after final-render audio QC and verified delivery; normalization or final-mix
failures become `failed` and no longer penalize later projects. Abandoned
reservations expire after the configured 168-hour recovery window.

Before selection, the library fingerprint is checked. New, removed, or changed
files trigger an incremental rebuild; unchanged SHA entries reuse their
duration and loudness analysis. A different unrelated library root receives a
transient scan and cannot overwrite this catalog.

`纯音乐` and `instrumental` are qualification labels, not semantic matches.
Selection reports them in `ignored_generic_keywords`. The final render must
contain an audio stream through the video tail and pass integrated-LUFS and
true-peak thresholds before delivery.
