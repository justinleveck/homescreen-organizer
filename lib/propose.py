"""Build state/proposed.json from usage: page 1 holds the most used apps, loose and in
order of use; everything else lives where state/scheme.json puts it, most used first."""

import argparse

from layout import (
    CURRENT, FOLDER_PAGE_CAPACITY, PAGE_CAPACITY, PROPOSED, STATE, TRAY, app_library_only, apps_in, arrangement,
    identity, load, problems_with, save,
)
from usage import UsageScores, normalised

SCHEME = STATE / "scheme.json"
LAST_GENERATED = STATE / "proposed.generated.json"


class Proposal:
    def __init__(self, phone, scheme, scores, kept_off_home_screen=()):
        self.scheme = scheme
        self.scores = scores
        self.apps_on_phone = list(apps_in(phone))
        self.kept_off_home_screen_names = {normalised(app["displayName"]) for app in kept_off_home_screen}
        self.placed = {identity(app) for app in kept_off_home_screen}
        self.unknown_names = []

    def build(self):
        dock = self.take_all(self.scheme["dock"])
        most_used = self.take_most_used()
        return [dock, most_used, *(self.page_from(page) for page in self.scheme["pages"])]

    def take_most_used(self):
        used = [app for app in self.unplaced_apps() if self.scores.score_of(app) > 0]
        most_used = sorted(used, key=self.scores.score_of, reverse=True)[:PAGE_CAPACITY]
        self.placed.update(identity(app) for app in most_used)
        return most_used

    def page_from(self, scheme_page):
        loose = self.take_all(scheme_page.get("loose", []))
        folders = [self.folder(name, names) for name, names in scheme_page.get("folders", {}).items()]
        return loose + [folder for folder in folders if folder["iconLists"]]

    def folder(self, name, names):
        apps = sorted(self.take_all(names), key=self.scores.score_of, reverse=True)
        folder_pages = [apps[start:start + FOLDER_PAGE_CAPACITY] for start in range(0, len(apps), FOLDER_PAGE_CAPACITY)]
        return {"listType": "folder", "displayName": name, "iconLists": folder_pages}

    def take_all(self, names):
        return [app for name in names for app in self.take(name)]

    def take(self, name):
        named = [app for app in self.apps_on_phone if normalised(app.get("displayName", "")) == normalised(name)]
        if not named and normalised(name) not in self.kept_off_home_screen_names:
            self.unknown_names.append(name)
        apps = [app for app in named if identity(app) not in self.placed]
        self.placed.update(identity(app) for app in apps)
        return apps

    def unplaced_apps(self):
        return [app for app in self.apps_on_phone if identity(app) not in self.placed]


def refuse_to_overwrite_hand_edits():
    if not PROPOSED.exists():
        return
    if LAST_GENERATED.exists() and arrangement(load(PROPOSED)) == arrangement(load(LAST_GENERATED)):
        return
    print(f"Refusing: {PROPOSED} has changes made in the editor since this script last wrote it")
    print(f"(its last output is kept in {LAST_GENERATED}). Proposing again would throw those edits away.")
    print("Commit or copy the edited layout first, then run with --force to replace it.")
    raise SystemExit(1)


def propose(force):
    if not force:
        refuse_to_overwrite_hand_edits()
    phone = load(CURRENT)
    scores = UsageScores(phone)
    kept_off_home_screen = app_library_only()
    proposal = Proposal(phone, load(SCHEME), scores, kept_off_home_screen)
    layout = proposal.build()

    homeless = proposal.unplaced_apps()
    if homeless:
        print("These apps have no place in state/scheme.json; add them to a folder or a loose list:")
        for app in homeless:
            print(f"  {app.get('displayName')}")
        raise SystemExit(1)

    problems = problems_with(layout, phone, kept_off_home_screen)
    if problems:
        print("The proposal does not validate:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)

    save(layout, PROPOSED)
    save(layout, LAST_GENERATED)
    save([], TRAY)
    scores.save_for_editor(phone)
    report(layout, proposal, scores)


def report(layout, proposal, scores):
    print(f"Wrote {PROPOSED}: {len(layout) - 1} pages, every app placed once.")
    print("Page 1, most used first:")
    for position, app in enumerate(layout[1], start=1):
        print(f"  {position:2}. {app.get('displayName')} ({scores.score_of(app)})")
    for name in proposal.unknown_names:
        print(f"Not on the phone, named in state/scheme.json: {name}")
    for name in scores.unmatched_names():
        print(f"Not on the phone, named in state/usage.json: {name}")


def arguments():
    parser = argparse.ArgumentParser(prog="homescreen-propose", description=__doc__)
    parser.add_argument("--force", action="store_true", help="replace state/proposed.json even if it was edited by hand")
    return parser.parse_args()


propose(arguments().force)
