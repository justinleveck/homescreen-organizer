# homescreen — agent instructions

This repo organises an iPhone Home Screen from a Mac, over USB. When asked to organize,
clean up, or apply a Home Screen layout, use the `.claude/skills/homescreen/SKILL.md`
skill — it walks through setup, reading the phone, drafting folders with the user,
Screen Time, the "check my notes" loop, and applying.

## Hard safety rules

- Never apply a layout to the phone (`bin/homescreen-apply`, `POST /apply`, `POST
  /restore`) without the user explicitly saying to, in this conversation, after you have
  told them what will change.
- Never delete an app, or treat "Delete this app" as anything but a note for the user to
  read — the tool has no way to remove an app from the phone.
- Reading the phone (`bin/homescreen-read`) is always safe to run without asking.
- Backups land in `state/backups/`; point the user at `--restore` if an apply goes wrong.
