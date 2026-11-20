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
- Browser files marked for deletion now close their OPFS access handle before
  removing the entry. Deletion remains pending across duplicated handles and
  can be cancelled; the final close reports any removal failure. The save
  regression checks these cases through the real Nt APIs.

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
(ms), wait-log (pattern/ms), shot (tag), status, end (result/detail), reload and close. key uses real
keyboard events; A/D assigns a team whereas arrow keys change menus/uniforms.
press uses the game's opt-in file queue: each word presses for 100 ms and
releases for at least 250 ms. A polling stall expires the old press before
returning another sample. Verify screenshots after transitions.
wait-log accepts a regular expression and watches fresh events since the last
play, input, begin or reload checkpoint. A timeout records an audit failure.
For title startup, optional button/everyMs retries one button until the expected
transition appears, bounded by ms (at most 60 seconds). For example:

```json
{"action":"wait-log","pattern":"descriptor=00515660","button":"start","everyMs":3000,"ms":60000}
```

This waits for the main menu; after Quick Game A, descriptor 0052728C identifies
team selection and 00585474 identifies coach matchup. Select the controller
side with A/D before changing its team with LT/RT. Initial away teams can vary
between boots; verify both teams and coaches before recording gameplay.
The selector also contains additional teams, including NFC/AFC all-star
teams; do not assume it wraps after 32 entries.
Allow title/VIP-load transitions to finish; idle title starts the attract demo.
Optional --capture-memory enables read-only guest-memory peek for diagnosis.
Reports include browser/adapter metadata and separate fatal failures from known
guest-site diagnostics. Browser exceptions, GPU failures and rejected draws
override requested pass/partial results and make the CLI exit unsuccessfully.
The [stadium/staff audit](WEB-STADIUM-FIDELITY.md) documents close replay views.

## Regression checks

- Full local web build passes.
- Browser audio/video/controller tests pass, including I/K/J/L directions,
  exact neutral release, second controller and disconnect/reconnect.
- Launcher tests pass including static-host isolation and disc imports.
- Browser save tests pass including durable data, backup/restore validation,
  rollback/recovery, concurrent-tab exclusion and Xbox save replacement
  through the real Nt APIs on OPFS, including rejected nonempty deletion.
- Fresh application of the published patch to the pinned runtime reproduces
    all 51 modified/added runtime files exactly (normalizing line endings).
- test_gameplay_flag_joins.py passes DEC/TEST and transition TEST/CMP paths, wraparound and
  all 256 x87 status bytes, and verifies regeneration/idempotence.

No 30 FPS minimum guarantee follows from this mode audit.

## Historical mode with executable DSP — November 20, 2026

The frozen `5de6f40` build is exercised with `RECOMP_APU_DSP=1`, the 30 FPS
cap, hardware WebGPU and APU/IRQ/per-draw/CPU profiling off. Build and Pages
workflows for that commit pass. `irq-level-ice-bowl-retail` retains the exact
artifact hashes, screenshots, runtime log and report.

The Anniversary catalog, Ice Bowl objective and historical uniform/controller
selection render. The field starts at DAL17–GB14, Q4 4:50, first-and-ten at
GB32, with fog, frozen field/sidelines, stadium/crowd, staff and readable
play-call text. Input delays during inspection produce delay-of-game penalties;
later inspections pause the game. A four-yard run advances to second-and-21
at GB21, 4:33, and a dropped right-side pass advances to third-and-21 at 4:18.
Pause, quit submenu and return to the objective screen work. No new FLAGS,
unresolved-call or browser/GPU failures are recorded.

Audio counters remain at three affected blocks / 384 missing frames from the
first field checkpoint through the final menu checkpoint. Those intervals
include inspection pauses and are not an uninterrupted active-play benchmark.
Initial idle navigation also entered attract mode before returning to the
menu; it is excluded from challenge coverage. The challenge is not completed,
and full original-Xbox graphics/audio parity and the other 24 challenges remain
unverified.

This pass also exposes inconsistent menu camera stretch after previous
attract/gameplay transitions. The camera callback's clock/team validation can
accept retained match records while a full-screen menu is visible. The
follow-up implementation and regression are recorded in the stadium/fidelity
ledger; broader mode and scene coverage remains open.

## Heidi Bowl historical-mode regression — November 20, 2026

The RGB565 renderer audit also exercises the second Anniversary scenario,
The Heidi Bowl. Its objective starts NYJ32–OAK29 at Q4 1:05, kickoff at NYJ30;
selection displays Jets 1965–1968 and Raiders 1966–1967 uniforms. Oakland's
stadium/crowd, sideline figures, long shadows and readable field/play-call UI
render. The first attempt returns 18 yards to OAK32 at 1:01 but logs
`[FLAGS] 00221ABB`; that audit is retained as failed. Source inspection finds
an obsolete fallback on the already-resolved nonzero TEST predecessor. The
persistent completion branch and regression are described in the fidelity
ledger; the audit classifier and diagnostic logging are unchanged.

The rebuilt replay returns 19 yards to OAK33 at 1:02 and completes a 22-yard
pass to NYJ45 at 0:48. Pause, quit submenu and return to the objective work.
There are no FLAGS, unresolved-call, browser/GPU/DSP failures in that replay.
Its last sampled audio counter is one block / 128 frames (2.667 ms); inspection
pauses prevent treating the whole run as uninterrupted active play. The
challenge is not completed or won, and original-Xbox output identity and the
30 FPS floor are not established. Reports, artifact hashes, images and logs
remain under `rgb565-historical-retail` and `rgb565-heidi-final-retail` in the
private build-test directory; their browsers and owned servers closed.

## Remaining resolved flag joins — November 20, 2026

A follow-up checks the original disc bytes at `00167701`/`00167817` and
`002FAD00`–`002FAD44`. The first join branches on JNE at `00167707` and
continues at `0016770D` when false; the second branches on JE at `002FAD42`
and continues at `002FAD44` when false. Existing patches already resolve the
TEST predecessor separately from the CMP predecessor, but each CMP false
path still invokes the obsolete flags fallback. Explicit completion branches
now bypass that fallback without suppressing diagnostics at other sites.

The expanded `test_gameplay_flag_joins.py` executes the production join and
TEST-predecessor blocks, with the original fall-through ordering preserved.
It checks 4,352 additional branch outcomes across both predecessors, all
single-bit operand pairs and unsigned edge values. The pre-fix source
reproduces nonzero fallback calls; the corrected Wasm fixture passes with
zero fallback calls and verifies regeneration/idempotence. This establishes
the branch continuations and removes false unknown-flags diagnostics; it
does not establish new retail mode coverage or a gameplay performance gain.

### State-transition TEST/CMP split in overlapping bodies

The same audit finds a functional error at `003D4CFB`. Original bytes at
`003D4CB7` are `85 C0 EB 40` (`TEST EAX,EAX; JMP 003D4CFB`); the other
predecessor loads a signed byte from `[ESI+3]` and compares it with EDI.
The joined JNE skips the state-3 write when its respective predicate is true.
The preceding return-value-5 shortcut goes directly to that write.

The existing standalone `sub_003D4C02` patch uses `CMP_NE` even for the TEST
predecessor. Its saved operands are both EAX, so nonzero results incorrectly
advance the state. The same original instructions are also lifted into
`sub_003D4940`; that overlapping body still uses the unresolved fallback for
both predecessors. Resolving only the standalone entry leaves this second
copy incorrect.

Persistent patches now decide TEST before the join in both bodies and use
CMP only for the comparison predecessor. The production-block fixture
preserves the return-value-5 shortcut and checks all 256 signed byte counts,
matching/neighboring indices and 32-bit return-value edges. Before the fix,
the 6,164 added cases report eight standalone TEST mismatches, eight
overlapping TEST mismatches and 2,808 overlapping CMP mismatches. After the
fix all four predecessor/body combinations have zero mismatches; the full
fixture also passes regeneration/idempotence and zero obsolete fallback
calls. This proves the corrected branch semantics, without attributing a
particular visible mode failure to this state update.

The final optimized Web link and complete launcher/static-host suite pass.
The frozen `frontend-join-retail` candidate renders the Heidi objective,
controller assignment and Oakland kickoff. Its return reaches OAK34 at
Q4 1:02; the offensive play reaches 2nd-and-4 at OAK40, Q4 0:47. Four sampled
audio counters remain at zero underruns/missing frames. No FLAGS,
unresolved-call, browser, GPU or DSP failures appear in that sequence.

The first case nevertheless remains failed: the audit incorrectly waits for
a new objective push after quitting. The game pops three states instead,
and its inspected screenshot correctly shows the objective in neutral
framing. The raw timeout is retained. A separate case re-enters the field,
pauses, quits with the observed pop-event expectation and verifies the
objective again; that case passes with no diagnostic failures. Its final
cumulative audio sample also remains zero. The overall harness exits with
status 1 because the first failed case is deliberately retained, rather than
being rewritten as a clean run.

The private run directory preserves both cases, seven inspected screenshots,
raw logs and nine build/source hashes. The owned browser and server are
closed. These bounded checks include pauses and do not establish an FPS
floor, uninterrupted whole-game audio, exact Xbox output, challenge completion
or execution coverage of every corrected join. The production-block fixture
provides the branch-specific evidence.

## Ice Bowl depth-rendering regression — November 20, 2026

The final D24 candidate renders the historical frozen field and advances
from 1st-and-10 at GB32, Q4 4:50 to 2nd-and-4 at GB38, Q4 4:35. Pause/quit
returns to the objective. Its three sampled audio counters remain zero and
the final audit passes without browser/GPU/runtime failures. The earlier
candidate's generated-line constructor error and failed black-field capture
are preserved separately, with the correction and regression documented in
[the depth audit](WEB-STADIUM-FIDELITY.md#integer-d24-triangle-depth-precision-2026-11-20).
Challenge completion, exact Xbox scene parity and a 30 FPS floor remain
unverified.
