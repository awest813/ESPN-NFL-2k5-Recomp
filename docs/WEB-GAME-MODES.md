# Retail browser game-mode audit

Audit started 2026-11-08 using the USA retail disc, Chrome 156 on Windows,
hardware WebGPU and the default 30 FPS cap. The local development build uses
an O1 link; production uses O3. Results describe the exercised paths, not
completion of every season, team, tutorial or historical objective.

## Coverage

| Mode / path | Verified behavior | Limits / remaining work |
| --- | --- | --- |
| Franchise | Create 49ers franchise; reject empty team selection; Coach Desk; simulate first week and entire preseason; save Franchise1; close/reopen browser; load and restore Week5, 1–3 record, BAL17–23 last game; quit | Full regular season, offseason, fantasy draft and every Front Office action not exhaustively tested |
| Tournament | Four CPU teams; both semifinals and final simulate; bracket advances; save Tournament1; restart game; restore all three scores including DEN34–CIN14 final; quit | Other bracket sizes, fantasy draft and human-played tournament game not yet verified |
| Practice / Basic Training | Field/player rendering; movement and tackle; expected failed drill and retry; tutorial list; pause/quit | All tutorials have not been completed |
| Practice / Full Scrimmage | Settings; offensive and defensive playcall; snap/run; 4-yard result and reset; pause/quit | Other practice types not exhaustively tested |
| Situation | Custom BAL2–GB0, away possession, second quarter, 5:00, second-and-10 at BAL30 applied to game; next play advanced to third-and-10 at 4:56; pause/quit | Representative CPU-versus-CPU situation; not every setting combination |
| First Person Football | Exactly-one-controller validation; A/D assignment; coin toss and kickoff; helmet camera; tackle and down progression to second-and-10 at ATL31, 4:36; pause/quit | Full game and every player position not exhaustively tested |
| ESPN 25th Anniversary | Challenge catalog and Ice Bowl objective; controller assignment; historical uniforms/frozen field; correct DAL17–GB14, Q4 4:50 atGB32; drive scored touchdown to GB20 and reached PAT at4:37; pause/quit | Full challenge completion and other24 challenges not verified |
| Quick Game | Previous 529-second gameplay run progressed with zero scheduler watchdog stalls | Full game completion and multiplayer gameplay not yet verified |
| The Crib | Room and User Card/milestone counters render; keyboard right-stick rotates camera; pause/quit; VIP creation and existing VIP overwrite succeed; restart loads replaced VIP1 | Unlocked mini-games not tested |
| Attract demo | Starts from idle title; Start returns to title | Not yet treated as a full playable game test |
| Xbox Live | Enter; confirm unsaved-data warning; retail reports no Gamertags and offers Dashboard; decline returns to menu | Browser online matchmaking/account creation is unavailable; Dashboard account setup not tested |

## Corrections made

- Added configurable right-stick keyboard directions (I/K/J/L), including
  defaults for older controls.ini files which omit the new keys. F1 bindings
  lists the new directions. Launcher lists both sticks and all extra buttons.
- The normal input path now applies configured keyboard/mouse input once.
  Legacy defaults previously ran again, defeating remapped keys and mouse-off.
  The legacy input option retains complete default button/stick mappings.
- Retail Basic Training reached a never-taken generated branch at 0x001AE8D5.
  Original Xbox predecessors are DEC EAX and TEST EAX,EAX; both require the
  zero branch when EAX is zero. The persistent generator patch now preserves
  both successors. An already-corrected join at 0x002F7CA4 now bypasses its
  obsolete diagnostic fallback on the nonzero path. Ice Bowl also reached
  0x000A2822, a TEST/CMP join that always took its transition; the patch now
  resolves each predecessor using its original condition.
- NFL2K5_MODE_TRACE=1 enables FSM transitions and bounded per-thread reporting
  of FLAGS, UNRESOLVED and TODO sites. It is disabled by default. Known TODO
  cache/port instructions are distinct from missing gameplay calls.
- Existing VIP overwrite exposed a POSIX/WasmFS file-layer bug: Xbox save
  deletion opens children relative to a directory handle, but those paths
  were resolved from the working directory. Relative create/delete/query now
  honor the directory handle and FATX case lookup. FileDisposition uses rmdir
  for directories and propagates removal failures. Retail overwrite now
  succeeds, and restarting the game loads the replaced VIP successfully.

## Evidence and reproduction

Ignored local evidence is under build-web-tests/mode-audit/: retail/report.json,
retail-reload/report.json and final/report.json, with runtime.ndjson logs and
screenshots. These contain no packaged game disc data. The extracted XBE used
for instruction inspection stays in the ignored build directory.

Use a dedicated browser profile with a disc already imported at the same
origin. Do not run two browsers against the same profile:

```powershell
$env:NODE_PATH = 'path/to/node_modules/with/playwright'
node tools/audit-web-modes.cjs --url http://127.0.0.1:8081/ --profile build-web-mode-audit --out build-web-tests/mode-audit/run --executable 'C:/Program Files/Google/Chrome/Application/chrome.exe'
```

Send newline-delimited JSON commands on stdin, or a JSON array via --script.
Actions include play, begin (id/title), key (key/ms/gap), press (buttons), wait
(ms), shot (tag), status, end (result/detail), reload and close. key uses real
keyboard events; A/D assigns a team whereas arrow keys change menus/uniforms.
press uses the game's opt-in file queue and holds each button for 200 ms; it
can cross a dialog or repeat a selection. Verify screenshots after transitions.
Allow title/VIP-load transitions to finish; idle title starts the attract demo.
Optional --capture-memory enables read-only guest-memory peek for diagnosis.

## Regression checks

- Full local web build passes.
- Browser audio/video/controller tests pass, including I/K/J/L directions,
  exact neutral release, second controller and disconnect/reconnect.
- Launcher tests pass including static-host isolation and disc imports.
- Browser save tests pass including durable data, backup/restore validation,
  rollback/recovery, concurrent-tab exclusion and Xbox save replacement
  through the real Nt APIs on OPFS, including rejected nonempty deletion.
- Fresh application of the published patch to the pinned runtime reproduces
  all 48 modified/added runtime files exactly (normalizing line endings).
- test_gameplay_flag_joins.py passes DEC/TEST and transition TEST/CMP paths, wraparound and
  all 256 x87 status bytes, and verifies regeneration/idempotence.

No 30 FPS minimum guarantee follows from this mode audit.
