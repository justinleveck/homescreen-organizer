---
name: homescreen
description: Organize an iPhone Home Screen from this Mac over USB — read the current layout, draft folders from the user's own apps, optionally rank by Screen Time, edit in the local web editor, and apply back to the phone. Use when the user asks to organize their home screen, clean up their iPhone apps, check their notes (from the homescreen editor), or apply the layout to the phone.
---

# homescreen

This tool reads an iPhone's Home Screen over USB, helps arrange it in a local web
editor, and — only when told to — writes the result back to the phone. Follow this
skill top to bottom the first time; later runs can jump to whichever step the user asks
for ("check my notes", "apply it").

## Hard rules

- **Never apply to the phone without the user explicitly saying to apply, in this
  conversation**, after you've told them roughly what will change (see **Apply**
  below). This means `bin/homescreen-apply`, and the editor's `POST /apply` /
  `POST /restore`, which you'd normally trigger by clicking the button yourself in a
  browser you control — don't script around the confirmation.
- **Never delete an app, and never treat "Delete this app" as an action** — it's a note
  left for a human to read (see **App Library Only** in the README for the real
  mechanism to keep an app off the Home Screen).
- Reading the phone (`bin/homescreen-read`) is always safe and needs no confirmation.
- Every apply backs up the phone's prior layout to `state/backups/` first; if something
  looks wrong afterwards, `bin/homescreen-apply --restore state/backups/<file>.json`
  undoes it.

## 1. Setup

If `.venv/` doesn't exist yet, run `bin/homescreen-setup`. It checks macOS and Python
3.11+, creates the venv, installs `pymobiledevice3` into it, creates `state/`, and
checks for a paired iPhone. If it reports no iPhone, tell the user to connect it by
cable, unlock it, and tap Trust if asked — then move on.

## 2. Read the phone

Run `bin/homescreen-read`. It writes `state/current.json` (the layout), `state/icons/`
(every icon image), and a timestamped backup. If it fails, the most common cause is the
phone being locked or not yet trusting this Mac — ask the user to unlock it and tap
Trust, then retry.

## 3. Screen Time (optional)

Ask the user whether they want apps ranked by real use before drafting folders. In a
sentence or two: it fills page 1 with the apps they actually use most this week (by
time, then by being the first thing opened after picking up the phone, then by
notifications), instead of you guessing. It needs a Mac signed into the same Apple ID as
the iPhone, **Share Across Devices** turned on in the iPhone's Screen Time settings, and
a small local helper with **Full Disk Access** — granted to that helper binary only, not
to Terminal or Claude, because that's the permission macOS requires to read the Screen
Time database at all.

If they want it, walk through these steps one at a time, checking in before moving to
the next:

1. **Turn on sync.** Ask them to open Settings > Screen Time > Share Across Devices on
   the iPhone, and turn it on if it isn't already. If it was already on, or they just
   turned it on, note that first-time sync can take a few hours — it's fine to continue
   and come back to step 3 later if it isn't ready yet.
2. **Install the helper.** Run `bin/homescreen-usage-install`. It builds the helper,
   registers it with launchd, prints the exact path it installed to, and opens System
   Settings to the Full Disk Access pane.
3. **Grant Full Disk Access.** Tell the user exactly what to click, using the path the
   previous command printed: click the **+** button, press **Cmd-Shift-G**, paste that
   path, click **Open**, then switch the toggle on next to it. Ask them to confirm they
   did this before continuing.
4. **Copy and read this week's usage.** Run `bin/homescreen-usage`. Interpret what it
   prints:
   - A list of apps with hours and minutes: it worked. Usage is now in
     `state/usage.json`, and the badges will show once the editor is open.
   - `"could not read Screen Time: no access"` (or a `copy-failed` message mentioning
     access): Full Disk Access isn't granted yet, or wasn't detected. Send them back to
     step 3 — re-open the pane (`System Settings > Privacy & Security > Full Disk
     Access`) and check the toggle is really on next to the right path.
   - `"No iPhone Screen Time found"`: Share Across Devices is off, or hasn't synced
     yet. Confirm it's on (step 1) and that the Mac's own **System Settings > Screen
     Time** shows the iPhone in its device picker — if not, it just needs more time;
     suggest trying again in a few hours.
   - A note that records "reach" some time a few hours in the past: that's normal sync
     lag, not a failure — the numbers are still usable.

If they'd rather skip it (or it isn't working yet and they don't want to wait), move on
without it — everything else works the same, just without the usage badges and without
page 1 being auto-filled by real use.

Two more signals are optional and typed in by hand, only worth mentioning as a
footnote: `state/usage.json`'s `week.first_used_after_pickup` and `week.notifications`,
copied in rank order from the iPhone's own Settings > Screen Time > See All App &
Website Activity > Week.

If usage was already working and the user just wants a refresh, re-run
`bin/homescreen-usage` and then `bin/homescreen-propose` (or just tell them the editor's
Screen Time toggle now reflects it, if they're not regenerating the proposal).

## 4. Draft folders with the user

Don't apply `templates/scheme.starter.json` blindly — it's generic. Instead, look at the
app names in `state/current.json` and draft `state/scheme.json` together with the user:

- Group their actual apps into folders that make sense for them (the starter's category
  names — Social, Media, Finance, and so on — are a reasonable starting vocabulary, but
  rename, merge, split, or invent folders to fit what they actually have installed).
- Ask a couple of preference questions rather than guessing: which apps, if any, they
  want pinned loose on page 1 regardless of usage; whether they want a work/personal
  split (as separate folders, or separate pages); anything they want kept in App Library
  Only from the start.
- Write the result to `state/scheme.json` (same shape as `templates/scheme.starter.json`:
  `dock`, and `pages` of `loose` + `folders`).

## 5. Propose

Run `bin/homescreen-propose`. It builds `state/proposed.json` from `state/scheme.json`
(and `state/usage.json` if present). If it reports apps with "no place in
state/scheme.json", add them to a folder or loose list and re-run.

## 6. Open the editor

Run `bin/homescreen-serve` and give the user the URL it prints
(`http://localhost:8765/web/` by default). They can drag things around, make folders,
search, and use the Tray and App Library Only as described in the README.

## 7. Check my notes

When asked to check notes (or periodically while the user is using the editor), run
`bin/homescreen-notes`. For each open note:

- Read what it's about (an app, a folder, or the whole layout) and its text.
- Make the corresponding change in `state/proposed.json` directly (never on the phone).
- Mark it done: set its `status` to `"done"` and add a one-line `reply` saying what you
  did. Notes live in `state/notes.json` as a plain JSON array — edit that file directly,
  or ask the user to delete the note from the editor once you've made the change and
  told them what you did.

## 8. Apply

Only do this when the user explicitly says to apply — not because Check has no
problems, not because they said "looks good." Before running it:

- Warn that widgets and Smart Stacks may not survive the apply (iOS doesn't preserve
  them through this mechanism), and that Apple may partially or fully ignore the write
  on newer iOS — the tool will report which happened.
- Confirm the iPhone is connected by cable and unlocked.

Then run `bin/homescreen-apply` (it will prompt for `yes`; use `--yes` only if the user
has already confirmed in this conversation and you're running it non-interactively) or
tell them to click **Apply to iPhone** in the editor, which shows its own confirmation
first.

After it finishes, read its output:

- "iOS accepted the layout": done, and `state/current.json` now matches.
- "iOS ignored the layout": nothing changed on the phone. Say so, and suggest using the
  editor's **Proposed** view as a manual checklist to rearrange by hand.
- If it lists App Library Only apps iOS put back on the Home Screen: explain that
  `setIconState` can't hide an app, so this is expected, not a failure, and give the
  checklist it printed (long-press each → Remove App → Remove from Home Screen).
- Point out `--restore <backup>` (or **Restore Previous** in the editor) if the user
  wants to undo.
