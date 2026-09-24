"""Print the open notes left in the editor, for Claude to act on."""

import json

from layout import STATE

NOTES = STATE / "notes.json"


def subject_label(subject):
    name = subject.get("displayName", "?")
    if subject.get("folder"):
        return f"{name} folder"
    return f"{name} ({subject.get('displayIdentifier')})"


def print_open_notes():
    notes = json.loads(NOTES.read_text()) if NOTES.exists() else []
    open_notes = [note for note in notes if note.get("status") == "open"]
    if not open_notes:
        print("No open notes.")
        return
    for note in open_notes:
        print(f"{note['id']}  {note.get('createdAt', '')}")
        subjects = [subject_label(subject) for subject in note.get("apps", [])]
        print(f"  on:   {', '.join(subjects) or 'the whole layout'}")
        for number, line in enumerate(note.get("text", "").splitlines()):
            print(f"  {'note:' if number == 0 else '     '} {line}")
        print()


print_open_notes()
