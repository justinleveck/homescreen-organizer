"""The Home Screen layout as SpringBoard describes it, and the rules a proposal must follow.

A layout is a list of pages. Page 0 is the dock. Each page holds icons: apps and web
clips (identified by displayIdentifier) or folders ({"listType": "folder",
"displayName", "iconLists": [[icon, ...], ...]}).
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
CURRENT = STATE / "current.json"
PROPOSED = STATE / "proposed.json"
BACKUPS = STATE / "backups"
ICONS = STATE / "icons"
TRAY = STATE / "tray.json"
APP_LIBRARY_ONLY = STATE / "app-library-only.json"

DOCK_CAPACITY = 4
PAGE_CAPACITY = 24
FOLDER_PAGE_CAPACITY = 9


def is_folder(icon):
    return icon.get("listType") == "folder"


def is_web_clip(icon):
    return not is_folder(icon) and "bundleIdentifier" not in icon


def identity(icon):
    return icon.get("displayIdentifier") or icon["bundleIdentifier"]


def apps_in(layout):
    for page in layout:
        yield from _apps_on(page)


def _apps_on(icons):
    for icon in icons:
        if is_folder(icon):
            for folder_page in icon["iconLists"]:
                yield from _apps_on(folder_page)
        else:
            yield icon


def arrangement(layout):
    """The layout reduced to what the user sees: names of folders and identities of apps."""

    def arrange(icon):
        if is_folder(icon):
            return {"folder": icon.get("displayName", ""), "pages": [[identity(app) for app in page] for page in icon["iconLists"] if page]}
        return identity(icon)

    return [[arrange(icon) for icon in page] for page in layout]


def problems_with(proposed, current, kept_off_home_screen=()):
    """Why the proposed layout cannot be applied to a phone whose layout is current.

    An app on kept_off_home_screen is deliberately absent from proposed (it lives in the
    App Library only), so its absence is not a missing app - even when current still
    reports it, which happens when iOS puts it back after setIconState can't hide it.
    """
    kept_ids = {identity(app) for app in kept_off_home_screen}
    problems = []
    current_ids = [identity(app) for app in apps_in(current)]
    proposed_ids = [identity(app) for app in apps_in(proposed)]
    names = {identity(app): app.get("displayName", identity(app)) for app in apps_in(current)}

    missing = sorted(set(current_ids) - set(proposed_ids) - kept_ids)
    unknown = sorted(set(proposed_ids) - set(current_ids))
    duplicated = sorted({app for app in proposed_ids if proposed_ids.count(app) > 1})
    problems += [f"not placed: {names[app]} ({app})" for app in missing]
    problems += [f"not on the phone: {app}" for app in unknown]
    problems += [f"placed more than once: {names.get(app, app)} ({app})" for app in duplicated]

    if not proposed:
        return problems + ["there is no dock"]
    if len(proposed[0]) > DOCK_CAPACITY:
        problems.append(f"the dock holds {len(proposed[0])} icons; it fits {DOCK_CAPACITY}")
    if any(is_folder(icon) for icon in proposed[0]):
        problems.append("the dock holds a folder; keep the dock to apps")
    for number, page in enumerate(proposed[1:], start=1):
        if len(page) > PAGE_CAPACITY:
            problems.append(f"page {number} holds {len(page)} icons; it fits {PAGE_CAPACITY}")
        if not page:
            problems.append(f"page {number} is empty")
        problems += _folder_problems(page, number)
    return problems


def _folder_problems(page, number):
    problems = []
    for folder in (icon for icon in page if is_folder(icon)):
        name = folder.get("displayName", "")
        if not name.strip():
            problems.append(f"page {number} has a folder with no name")
        if not any(folder["iconLists"]):
            problems.append(f"folder {name!r} on page {number} is empty")
        for folder_page in folder["iconLists"]:
            if len(folder_page) > FOLDER_PAGE_CAPACITY:
                problems.append(f"folder {name!r} has a page of {len(folder_page)}; folder pages fit {FOLDER_PAGE_CAPACITY}")
            if any(is_folder(icon) for icon in folder_page):
                problems.append(f"folder {name!r} holds another folder")
    return problems


def rebuilt_with_live_icons(layout, live):
    """The arrangement of layout, built from the icon records the phone reported just now.

    Saved JSON has lost the plist types SpringBoard sent (dates became strings), so the
    phone's own records are what go back to it.
    """
    live_icons = {identity(app): app for app in apps_in(live)}

    def rebuild(icon):
        if is_folder(icon):
            return {
                "listType": "folder",
                "displayName": icon["displayName"],
                "iconLists": [[live_icons[identity(app)] for app in page] for page in icon["iconLists"] if page],
            }
        return live_icons[identity(icon)]

    return [[rebuild(icon) for icon in page] for page in layout]


def differences(expected, actual):
    expected_pages, actual_pages = arrangement(expected), arrangement(actual)
    names = {identity(app): app.get("displayName", identity(app)) for app in [*apps_in(expected), *apps_in(actual)]}
    lines = []
    if len(expected_pages) != len(actual_pages):
        lines.append(f"page count: expected {len(expected_pages)}, phone has {len(actual_pages)}")
    for number, (want, have) in enumerate(zip(expected_pages, actual_pages)):
        if want != have:
            label = "dock" if number == 0 else f"page {number}"
            lines.append(f"{label}: expected {_describe(want, names)}")
            lines.append(f"{' ' * len(label)}  phone has {_describe(have, names)}")
    return lines


def _describe(page, names):
    return ", ".join(f"[{icon['folder']}]" if isinstance(icon, dict) else names[icon] for icon in page)


def load(path):
    return json.loads(Path(path).read_text())


def save(layout, path):
    Path(path).write_text(json.dumps(layout, indent=2, ensure_ascii=False, default=_plist_value) + "\n")


def _plist_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return None
    raise TypeError(f"cannot store {type(value).__name__} in JSON")


def apps_in_tray():
    return [entry["app"] for entry in load(TRAY)] if TRAY.exists() else []


def app_library_only():
    """Apps kept off the Home Screen on purpose - the goal state, not a stray."""
    return load(APP_LIBRARY_ONLY) if APP_LIBRARY_ONLY.exists() else []


def without_apps(layout, ids):
    return [[icon for icon in page if is_folder(icon) or identity(icon) not in ids] for page in layout]


def place_loose(pages, app, capacity=PAGE_CAPACITY):
    """Insert a loose app just ahead of the first folders that have room beside them,
    after that page's other loose apps. Pages of loose apps only are the hand-picked
    ones (page 1 is the most used), so they are filled only when no page of folders
    has room. Returns the page the app went on."""
    with_room = [page for page in pages if len(page) < capacity]
    page = next((page for page in with_room if any(is_folder(icon) for icon in page)), None) or next(iter(with_room), pages[-1])
    first_folder = next((index for index, icon in enumerate(page) if is_folder(icon)), len(page))
    page.insert(first_folder, app)
    return page


def save_backup(layout, reason):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    path = BACKUPS / f"{datetime.now():%Y-%m-%d-%H%M%S}-{reason}.json"
    save(layout, path)
    return path
