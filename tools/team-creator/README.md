# Create a team for the Windows game

Team Creator builds a new team entry with its own city, nickname, team code, uniforms, crowd, and roster. Existing teams keep their own files.

## Build a team

1. Install Python 3 with Tkinter. Install Pillow for uniform previews. Extract the USA Xbox disc to `original/disc/`. [Disc layout](../../original/README.md)
2. Run `Team Creator.cmd` from the repo root or run `python tools/team-creator/creator.py`.
3. Choose the team identity and a base NFL team for its uniform cut, helmet, and crowd. Preview your home and away colors.
4. Generate a roster at your preferred strength or import a compatible EA DB team. Tested inputs include Madden 21 PC/console rosters and NCAA Football 14 PS3 USR-DATA. The import picks 53 players by position in depth order.
5. Build the team and restart the game. In **Quick Game → Team Select**, look after the historic teams.

## Output and credits

The tool creates `mods/teams/<Team>/` with `team.json`, a disc-derived `team.rost`, `roster.csv`, and recolored uniform, helmet, and crowd assets under `files/`.

The texture and archive codecs come from 2K Football Mod Tools / 2K5 Mod Studio. [Vendored codec license](vendor/LICENSE-2k-football-mod-tools.txt) · [Mod folders](../../mods/README.md)
