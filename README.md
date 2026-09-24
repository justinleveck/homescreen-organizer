# homescreen

View and reorganise an iPhone Home Screen from a Mac, over USB.

The phone's layout is read into `state/current.json` with every icon image. A browser
editor shows it like the phone does, and lets you drag a proposed layout together in
`state/proposed.json`. Applying the proposal to the phone is a separate, deliberate step.
Screen Time can optionally rank your apps by real use, so the most-used ones land on
page 1 automatically.

## Requirements

- A Mac running macOS, and an iPhone plugged in over USB, unlocked, and already
  trusting this Mac.
- Python 3.11 or later.
- Optional: [Claude Code](https://claude.com/product/claude-code), to walk you through
  the whole process — reading the phone, drafting folders from your own apps, and
  applying the result — instead of running each command by hand.
- Optional, for Screen Time ranking: Screen Time synced across your devices, and Swift
  (`swiftc`, part of Xcode Command Line Tools) to build a small local helper. See
  **Screen Time** below.

No npm, no frameworks, no build step. The editor is one HTML file.

## Quick start

```bash
git clone <this repo> homescreen
cd homescreen
bin/homescreen-setup
```

Then either open the folder in Claude Code and say **"organize my home screen"** — it
reads the phone, helps you draft folders from your own apps, and walks you through the
rest — or run the commands yourself:

```bash
bin/homescreen-read      # phone -> state/current.json, state/icons/, state/backups/
bin/homescreen-propose   # state/scheme.json (+ state/usage.json) -> state/proposed.json
bin/homescreen-serve     # editor at http://localhost:8765/web/ (pass a port to change it)
bin/homescreen-notes     # print the open notes left in the editor
bin/homescreen-apply     # state/proposed.json -> phone, after a backup and a prompt
bin/homescreen-apply --restore state/backups/<file>.json
```

`bin/homescreen-propose` needs `state/scheme.json` — a folder plan naming where each app
goes. The first run copies `templates/scheme.starter.json`, a generic starting point, to
`state/scheme.json` if you don't have one yet. It's worth replacing with folders built
from your own apps (Claude will do this with you); edit it by hand any time and re-run
propose.

The editor can also trigger `homescreen-apply` itself — see **Apply to iPhone** below.

## How the editor works

`bin/homescreen-serve`, then open the address it prints. The page needs the server:
browsers refuse to load the JSON files from `file://`, and the server is also what Save
writes through.

- **Current** shows the phone as last read. Read only.
- **Proposed** is editable. Drop on the edge of an icon to place beside it, on the middle
  of an icon to make a folder (or add to one), on empty space to add at the end of a page.
  Double-click a folder to open it and rename it. Drag an app outside the open folder to
  take it out. You can add and remove empty pages.
- **Selecting:** click selects an icon or folder. ⌘/Ctrl-click adds or removes one, and
  Shift-click selects a run within one page or folder. Escape clears the selection.
  Dragging a selected icon moves the whole selection.
- **Search** matches app and folder names. Picking a folder scrolls to it and opens it.
  Picking an app that's in a folder opens that folder with the app highlighted.
- **Tray**, at the top of the side panel, holds apps while you decide where they go. Drag
  one app or a selection in, or right-click and choose **Set Aside**. Drag apps back out
  onto a page, into a folder, or onto an icon to make a folder. **Return All** puts each
  app back where it came from. The Tray saves with the layout to `state/tray.json`. Apps
  in the Tray count as placed, but `homescreen-apply` refuses until the Tray is empty.
  Apps missing from a loaded proposal land in the Tray.
- **File Tray Contents**, next to Return All, files every Tray app into the folder where
  it belongs, without asking an agent: `lib/file_tray.py` matches each app to the
  `state/scheme.json` folder that lists it (names matched with `usage.normalised`), then
  picks whichever layout folder already holds the most of that scheme folder's other
  apps — a vote, since you rename and rearrange folders by hand — falling back to a
  layout folder with the same name. It inserts each app by usage score, before the first
  app that scores lower, and re-pages the folder in nines. An app on the **App Library
  Only** list files there instead, no matter what the scheme says — that list always
  wins. Apps the scheme calls loose, or doesn't mention, have no folder to vote for and
  go loose just ahead of the first folders with room (page 1, the hand-picked page of
  loose apps, only when no page of folders has room). The editor applies the result to
  Proposed and marks it unsaved; a notice reports where each app went. New apps the phone
  has that the proposal doesn't place go through the same filing on load, automatically,
  before landing in the Tray as a last resort — Undo reverses that filing as one step.
- **App Library Only**, below the Tray, holds apps you keep off the Home Screen on
  purpose. Right-click → **Keep in App Library Only** (or drag an app into its card) puts
  it there; drag it back out, or right-click → **Put Back on Home Screen**, to return it
  (to the Tray is fine). It saves with the layout to `state/app-library-only.json` as a
  list of `{displayIdentifier, displayName}`. These apps count as placed everywhere that
  matters: not missing, not a Tray stray on load, no Check problem — because `setIconState`
  cannot hide an app, so the phone may still report one that's on this list, and that's
  the goal, not an error. `lib/propose.py` never places a listed app, `lib/file_tray.py`
  routes one straight here instead of voting it into a folder.
- **Screen Time** (top bar) shows or hides usage. When it's on, an app used this week
  carries a small badge with its week's screen time (`2h 41m`), or its pickup rank
  (`#19 pickup`) when it has almost no time. Hovering shows the full numbers and the
  score, and **Most used this week** in the side panel lists the top 15. The choice is
  remembered in this browser.
- **Check** lists everything that would stop the proposal being applied: every app on
  the phone must be placed exactly once, the dock fits 4 apps and no folders, and a page
  fits 24. Folders re-page themselves in nines. It also warns, without blocking Apply,
  when a page has a loose app sitting after a folder ("Page 3: FaceTime, Magnifier, TV
  sit after the folders.") — a drag can still put an app anywhere.
- **Save** writes `state/proposed.json`, `state/tray.json` and `state/app-library-only.json`
  through the server. Drafts save even when Check shows problems, so work in progress is
  never lost. The server accepts PUT or POST to those paths and `/state/notes.json`, and
  refuses to write anything else.
- **Undo**, top bar, or ⌘Z / Ctrl-Z (the browser's own undo runs instead while focus is in
  a text field), undoes the last move, drag, folder create or rename, Set Aside, Return
  All, a Keep in App Library Only or Put Back on Home Screen, File Tray Contents, or the
  automatic filing of new apps on load. Its tooltip names the action ("Undo Set Aside")
  and it's disabled with nothing to undo. Up to 50 steps, kept as deep copies of the
  layout, Tray, App Library Only and origins; Reload clears the history. Notes aren't
  part of it.

Whenever the tool places a loose app on a page itself — filing a new arrival, Put Back on
Home Screen, Return All when the remembered page is gone — it inserts the app after the
page's other loose apps and before its first folder, using the next page with room if
this one is full (`placeLoose` in the editor, `place_loose` in `lib/layout.py`). It never
reorders a folder past where you dragged it yourself.

### Apply to iPhone

Once the layout is saved, Check has no problems and the Tray is empty, **Apply to
iPhone** (top bar) is enabled. Clicking it opens an in-page confirmation — no `confirm()`
dialogs, they don't work reliably here — summarising how many apps change place, folders
added/removed/renamed, and pages before → after, computed in the browser from
`state.current` vs `state.proposed`. It warns that widgets and Smart Stacks may not
survive, and to connect the iPhone by cable and unlock it.

Confirming calls `POST /apply`, which runs `bin/homescreen-apply --yes` as a subprocess
(so the server itself stays plain Python) with a timeout of about 90 seconds, and refuses
if an apply or restore is already running. The result panel shows its output, monospace,
then reloads state — `homescreen-apply` rewrites `state/current.json` on success.

**Restore Previous** appears next to Apply whenever `state/backups/` holds a backup whose
name contains `before-apply` (`GET /backups.json` reports the newest one). Its
confirmation names the backup's time, and confirming calls `POST /restore`, which runs
`bin/homescreen-apply --restore <that backup> --yes` through the same runner.

`HOMESCREEN_APPLY_COMMAND` overrides the command `serve.py` runs for both endpoints,
defaulting to the real `bin/homescreen-apply`. Point it at a stand-in that never touches
a phone to test the editor's apply and restore flows.

### Notes for Claude

The box at the top of **Notes for Claude**, in the side panel, takes a note about
whatever is selected, or about the whole layout when nothing is (its `apps` list is then
empty). Right-click an icon or a selection, in either mode, for the same: **Leave a note…**
opens a text box (Enter saves, Shift-Enter starts a new line). There are also one-click
notes: **Move to page 1**, **Put in a folder with these** (for two or more), and
**Delete this app** — keeping an app off the Home Screen is a real action now, not a
note; see **App Library Only** above. Notes save straight away
to `state/notes.json` as `{id, createdAt, apps: [{displayIdentifier, displayName}], text,
status, reply}`. An icon with an open note shows a small yellow dot, and hovering shows
the note. **Notes for Claude**, in the side panel, lists open notes with Delete. Done
notes are collapsed below, each with Claude's reply.

Claude reads the open notes with `bin/homescreen-notes` and acts on them in
`state/proposed.json`, never on the phone. For each note it then sets `status` to
`"done"` with a one-line `reply` saying what it did.

`state/proposal.md` explains the current draft: what went where and why.

## Screen Time (optional)

Ranking is optional, and everything above works fine without it — Check and Apply never
require it. When it's on, `bin/homescreen-propose` scores every app (minutes this week
count most, then pickup rank, then notification rank) and puts the top 24 that aren't in
the dock on page 1, loose, most used first. The editor's Screen Time toggle then shows
badges and a "Most used this week" list.

It needs a small local helper with **Full Disk Access**, because that's the permission
macOS requires to read the Screen Time database — granted to the helper binary itself,
not to Terminal or Claude:

```bash
bin/homescreen-usage-install   # builds the helper, installs it, opens the Full Disk Access pane
bin/homescreen-usage           # copies this week's Screen Time into state/usage.json
```

Requirements: the Mac and iPhone signed into the same Apple ID, with **Settings > Screen
Time > Share Across Devices** turned on on the iPhone (it can take a few hours to sync
the first time).

Claude Code can walk you through all of this — see the **Screen Time** section of
`.claude/skills/homescreen/SKILL.md` — including what to click in the Full Disk Access
pane and what to do if the sync hasn't shown up yet.

Two more signals are optional and filled in by hand, if you want them, in
`state/usage.json`'s `week.first_used_after_pickup` and `week.notifications` — copied in
rank order from the iPhone's own Settings > Screen Time > See All App & Website Activity
> Week.

## Safety model and limits

- **Reading is harmless.** `homescreen-read` only calls SpringBoard's getters
  (`get_icon_state`, `get_icon_pngdata`) in one USB session. Every read also saves a
  timestamped copy of the layout to `state/backups/`.
- **Nothing writes to the phone except `homescreen-apply`** — run directly, or by the
  editor's Apply to iPhone and Restore Previous, which only ever shell out to it — and it:
  1. refuses while the editor's Tray still holds apps;
  2. reads the phone's live layout and refuses unless the layout to apply places every app
     on the phone right now exactly once (apps installed or removed since the proposal was
     made are caught here) — an app on the App Library Only list is exempt either way, since
     the layout never lists it on purpose;
  3. asks you to type `yes` (skip with `--yes`);
  4. backs up the live layout to `state/backups/<time>-before-apply.json`;
  5. sends the layout with `SpringBoardServicesService.set_icon_state(newstate)`, built
     from the icon records the phone just reported rather than the saved JSON (JSON loses
     the plist dates SpringBoard sent);
  6. reads the layout back, saves it to `state/current.json`, and judges the result with
     App Library Only apps set aside — `setIconState` cannot hide an app, so iOS may put a
     listed one back on the Home Screen (typically the last page) even though the layout
     sent never named it; that alone doesn't count as a failed apply. It prints whether the
     phone otherwise matches, is unchanged, or changed only partly, the `--restore` command
     to undo, and, if iOS did that, a checklist of which apps to remove by hand.
  - `--restore <backup>` goes through the same steps with a backup file instead of the
    proposal.
- **It may do nothing on current iOS.** Apple has tightened what `setIconState` may
  change, and SpringBoard may ignore it without an error. SpringBoard has also
  historically sent no reply to it, so the send has a 10-second deadline. The read-back
  afterwards is what tells you what happened: if it reports "iOS ignored the layout",
  nothing changed on the phone. In that case the editor is still useful as a manual
  checklist — open **Proposed** next to the phone and rearrange by hand, page by page and
  folder by folder; search highlights where an app belongs.
- **It never deletes an app.** "Delete this app" in the editor is a note for a human to
  read, not an action the tool takes — the only way an app leaves the Home Screen is App
  Library Only, and `setIconState` can't even guarantee that (see above).
- Other things `setIconState` may not preserve: widgets and Smart Stacks (the layout this
  reads does not include them), App Library settings, and hidden pages.

## Keeping your data private

`state/` — your phone's layout, icons, usage, notes, and backups — is entirely
gitignored (only `state/.gitkeep` is tracked), so none of it is committed here by
default.

To version your own layout and folder scheme anyway, without putting them in this repo,
point `state/` at a private repo of your own instead of a plain folder:

```bash
rm -rf state   # after checking there's nothing in it you still need
ln -s /path/to/your-private-homescreen-state state
```

Everything else in this repo — the scripts, the editor, the starter scheme — stays
public and shareable.

## Layout

```
bin/          entry points (bash wrappers around lib/)
lib/          layout.py (rules, validation, diff), phone.py (USB session),
              usage.py (scores), read.py, propose.py, apply.py, serve.py, notes.py,
              file_tray.py (File Tray Contents)
web/          index.html, the editor (one file, no build step)
helper/       screentime-copy.swift, the Full-Disk-Access helper for Screen Time
templates/    scheme.starter.json, a generic folder plan to start from
.claude/      skills/homescreen/SKILL.md, so Claude Code can drive the whole process
state/        current.json, proposed.json, proposed.generated.json, tray.json,
              notes.json, proposal.md, usage.json, scheme.json, usage-scores.json,
              app-library-only.json — all local only, gitignored; icons/, backups/
              and screentime/ likewise
```
