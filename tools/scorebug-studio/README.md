# Scorebug Studio

Open [`index.html`](index.html) in a browser to use the offline editor. On Windows, run `.\tools\open-scorebug-studio.ps1` from the repo root to open it with the repository's presentation templates.

## Create or edit a package

1. Choose a starting look and adjust the colors, label, typography, placement, and size.
2. Drag the preview to position the scorebug, then select **Download presentation.json**.
3. To edit an existing package, choose **Load an existing presentation.json**. The imported JSON panel exposes advanced layers, media, and animations. Use **Download imported JSON** to save edits from that panel.

## Install and test on Windows

Run `.\tools\install-scorebug-json.ps1 -Path "C:\path\to\presentation.json"` from the repo root. It copies the manifest and nearby `images`, `music`, and `video` folders into the new package. For a manual install, put the manifest in `mods/presentations/<package name>/presentation.json`.

Restart the game and choose the package from **Coach Match Up → Presentation**. Check it at kickoff, scrimmage, and score changes. Add any permitted media your design calls for.

[Windows mods](../../mods/README.md) · [Authoring reference](../../docs/SCOREBUG-AUTHORING-GUIDE.md)
