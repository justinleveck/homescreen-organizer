"""Put a layout on the phone: state/proposed.json, or a backup with --restore.

Validates against the phone's live layout, backs that up, applies, then reads the
phone again to learn whether SpringBoard took the change.
"""

import argparse
import asyncio
from pathlib import Path

from layout import (
    CURRENT, PROPOSED, app_library_only, apps_in, apps_in_tray, differences, identity, load, problems_with,
    rebuilt_with_live_icons, save, save_backup, without_apps,
)
from phone import springboard

# SpringBoard has historically sent no reply to setIconState, while pymobiledevice3
# waits for one, so the send is given a deadline instead of being awaited forever.
SET_REPLY_DEADLINE_SECONDS = 10
SETTLE_SECONDS = 3


async def put_on_phone(layout_path, reason, confirmed):
    wanted = load(layout_path)
    kept_off_home_screen = app_library_only()

    async with springboard() as service:
        live = await service.get_icon_state()
        refuse_if_invalid(wanted, live, layout_path, kept_off_home_screen)
        if not confirmed and not confirm(layout_path):
            raise SystemExit("Nothing was changed.")
        backup = save_backup(live, f"before-{reason}")
        print(f"Backed up the phone's layout to {backup}")
        await send(service, rebuilt_with_live_icons(wanted, live))

    await asyncio.sleep(SETTLE_SECONDS)
    async with springboard() as service:
        after = await service.get_icon_state()
    save(after, CURRENT)
    report(wanted, after, backup, kept_off_home_screen)


def refuse_while_tray_holds_apps():
    waiting = len(apps_in_tray())
    if waiting:
        apps = "app" if waiting == 1 else "apps"
        raise SystemExit(f"Return or place the {waiting} {apps} in your Tray before applying.")


def refuse_if_invalid(wanted, live, layout_path, kept_off_home_screen):
    problems = problems_with(wanted, live, kept_off_home_screen)
    if problems:
        print(f"Refusing: {layout_path} does not fit the phone as it is now.")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)


def confirm(layout_path):
    answer = input(f"Replace the phone's Home Screen with {layout_path}? Type yes to continue: ")
    return answer.strip().lower() == "yes"


async def send(service, layout):
    try:
        await asyncio.wait_for(service.set_icon_state(layout), SET_REPLY_DEADLINE_SECONDS)
    except TimeoutError:
        print("Sent the layout; SpringBoard did not reply (expected on many iOS versions).")


def report(wanted, after, backup, kept_off_home_screen):
    """Print how the apply went, judging it by the layout minus any App Library Only app
    iOS surfaced - setIconState can't hide those, so their reappearing isn't a failed
    apply, just something to clear by hand."""
    kept_ids = {identity(app) for app in kept_off_home_screen}
    surfaced = [app for app in apps_in(after) if identity(app) in kept_ids]
    comparable_after = without_apps(after, {identity(app) for app in surfaced})

    remaining = differences(wanted, comparable_after)
    if not remaining:
        print("iOS accepted the layout: the phone now matches it exactly.")
    else:
        if not differences(load(backup), comparable_after):
            print("iOS ignored the layout: the phone is unchanged. Use the editor as a manual checklist.")
        else:
            print("iOS changed the layout, but not to exactly what was sent. Where it differs:")
        for line in remaining:
            print(f"  {line}")
        print(f"To undo: bin/homescreen-apply --restore {backup}")

    if surfaced:
        names = ", ".join(app.get("displayName", identity(app)) for app in surfaced)
        noun = "app" if len(surfaced) == 1 else "apps"
        print(
            f"iOS put {len(surfaced)} App Library Only {noun} back on the Home Screen: {names}. "
            "On the iPhone, long-press each → Remove App → Remove from Home Screen."
        )


def arguments():
    parser = argparse.ArgumentParser(prog="homescreen-apply", description=__doc__)
    parser.add_argument("--restore", metavar="BACKUP", type=Path, help="put a saved backup back on the phone")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    return parser.parse_args()


options = arguments()
if options.restore:
    asyncio.run(put_on_phone(options.restore, "restore", options.yes))
else:
    refuse_while_tray_holds_apps()
    asyncio.run(put_on_phone(PROPOSED, "apply", options.yes))
