"""File every Tray app into the folder where it belongs, deterministically.

An app belongs to whichever folder state/scheme.json lists it under. The user renames
and rearranges folders by hand though, so the layout folder to file into is found by
vote: whichever layout folder already holds the most of that scheme folder's other
apps, falling back to a layout folder with the same name. Apps the scheme calls loose,
or does not mention at all, go loose just ahead of the first folders with room, where
the user can rearrange them.

An app on the App Library Only list never gets voted into a scheme folder - that list
wins regardless of what state/scheme.json says - and files straight into App Library
Only instead, the same as any other destination.
"""

import json

from layout import FOLDER_PAGE_CAPACITY, STATE, identity, is_folder, place_loose
from usage import UsageScores, normalised

SCHEME = STATE / "scheme.json"
APP_LIBRARY_ONLY_LABEL = "App Library Only"


def file_tray_contents(layout, tray, app_library_only=()):
    folders = _scheme_folders()
    scores = UsageScores(layout)
    layout_folders = [icon for page in layout for icon in page if is_folder(icon)]
    kept_ids = {identity(app) for app in app_library_only}

    filed = []
    archived = list(app_library_only)
    for app in tray:
        if identity(app) in kept_ids:
            # Already on the list (it seeded kept_ids), so file it there without duplicating it.
            filed.append({"app": app.get("displayName", "?"), "folder": APP_LIBRARY_ONLY_LABEL})
            continue
        destination = _folder_for(app, folders, layout_folders)
        if destination is None:
            page = place_loose(layout[1:], app)
            page_number = next(number for number, each in enumerate(layout) if each is page)
            filed.append({"app": app.get("displayName", "?"), "folder": f"page {page_number}"})
            continue
        _insert_by_usage(destination, app, scores)
        filed.append({"app": app.get("displayName", "?"), "folder": destination["displayName"]})

    return layout, [], archived, filed, []


def _scheme_folders():
    scheme = json.loads(SCHEME.read_text())
    return {
        name: {normalised(member) for member in members}
        for page in scheme["pages"]
        for name, members in page.get("folders", {}).items()
    }


def _folder_for(app, folders, layout_folders):
    scheme_folder = next((name for name, members in folders.items() if normalised(app.get("displayName", "")) in members), None)
    if scheme_folder is None:
        return None
    members = folders[scheme_folder]

    def votes(folder):
        return sum(1 for other in _apps_in_folder(folder) if normalised(other.get("displayName", "")) in members)

    voted = max(layout_folders, key=votes, default=None)
    if voted is not None and votes(voted) > 0:
        return voted
    return next((folder for folder in layout_folders if normalised(folder["displayName"]) == normalised(scheme_folder)), None)


def _apps_in_folder(folder):
    return [app for page in folder["iconLists"] for app in page]


def _insert_by_usage(folder, app, scores):
    apps = _apps_in_folder(folder)
    index = next((position for position, other in enumerate(apps) if scores.score_of(other) < scores.score_of(app)), len(apps))
    apps.insert(index, app)
    folder["iconLists"] = [apps[start:start + FOLDER_PAGE_CAPACITY] for start in range(0, len(apps), FOLDER_PAGE_CAPACITY)]
