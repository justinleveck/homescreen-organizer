"""The iPhone's time in each app, read from the Screen Time records the Mac keeps in sync.

bin/homescreen-usage has the copy helper copy those records into state/screentime/
first; this reads the copies. Each record says an app came to the front or left it,
at a moment counted in seconds from 2001. An app's time is the span from coming to
the front until it leaves, or until another app comes to the front.

The format follows ActivityWatch's aw-import-screentime; the records sit in Apple's
SEGB container files, which ccl-segb reads.
"""

import argparse
import json
import sqlite3
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ccl_segb

from layout import CURRENT, STATE, apps_in, load
from usage import USAGE

COPIES = STATE / "screentime"
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
IOS_PLATFORM = 2


@dataclass
class FocusChange:
    bundle_id: str
    at: datetime
    to_front: bool


def current_iphone_id(sync_db):
    """Old phones stay listed long after they are gone; the current one synced last."""
    uri = f"file:{sync_db}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute(
            "SELECT device_identifier FROM DevicePeer WHERE platform = ? ORDER BY last_sync_date DESC LIMIT 1",
            (IOS_PLATFORM,),
        ).fetchone()
        return row[0] if row else None


def focus_changes(device_folder):
    records = sorted((path for path in device_folder.iterdir() if path.is_file() and not path.name.startswith(".")),
                     key=lambda path: path.stat().st_mtime)
    for path in records:
        for record in ccl_segb.read_segb_file(str(path)):
            change = decoded(getattr(record, "data", b""))
            if change:
                yield change


def decoded(data):
    """Only three fields matter: 3 in_foreground, 4 the moment, 6 the bundle id."""
    if not data or not any(data):
        return None
    fields = {}
    at = 0
    try:
        while at < len(data):
            key, at = varint(data, at)
            number, wire = key >> 3, key & 7
            if wire == 0:
                fields[number], at = varint(data, at)
            elif wire == 1:
                fields[number] = struct.unpack_from("<d", data, at)[0]
                at += 8
            elif wire == 2:
                length, at = varint(data, at)
                fields[number] = data[at:at + length]
                at += length
            elif wire == 5:
                at += 4
            else:
                return None
    except (IndexError, struct.error):
        return None
    if 6 not in fields or 4 not in fields:
        return None
    return FocusChange(
        bundle_id=fields[6].decode("utf-8", "replace"),
        at=APPLE_EPOCH + timedelta(seconds=fields[4]),
        to_front=bool(fields.get(3, 0)),
    )


def varint(data, at):
    value = shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, at
        shift += 7


def time_in_front(changes, since):
    seconds = defaultdict(float)
    opens = Counter()
    in_front, came_forward = None, None
    for change in sorted(changes, key=lambda change: change.at):
        if change.to_front and change.bundle_id == in_front:
            continue
        leaves = in_front and (change.bundle_id == in_front or change.to_front)
        if leaves and change.at > came_forward:
            start = max(came_forward, since)
            if change.at > start:
                seconds[in_front] += (change.at - start).total_seconds()
        if change.to_front:
            in_front, came_forward = change.bundle_id, change.at
            if change.at >= since:
                opens[change.bundle_id] += 1
        elif change.bundle_id == in_front:
            in_front, came_forward = None, None
    return seconds, opens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    days = parser.parse_args().days
    since = datetime.now(timezone.utc) - timedelta(days=days)

    iphone = current_iphone_id(COPIES / "sync.db")
    folder = COPIES / "App.InFocus" / (iphone or "")
    if not iphone or not folder.is_dir():
        raise SystemExit("No iPhone Screen Time found. Is Share Across Devices on in the iPhone's Screen Time settings?")

    changes = list(focus_changes(folder))
    newest = max(change.at for change in changes)
    seconds, opens = time_in_front(changes, since)

    names = {app["bundleIdentifier"]: app["displayName"] for app in apps_in(load(CURRENT)) if "bundleIdentifier" in app}
    on_phone = {bundle: secs for bundle, secs in seconds.items() if bundle in names}

    usage = json.loads(USAGE.read_text()) if USAGE.exists() else {}
    week = usage.setdefault("week", {})
    week["seconds"] = {names[bundle]: round(secs) for bundle, secs in sorted(on_phone.items(), key=lambda item: -item[1])}
    week["opens"] = {names[bundle]: count for bundle, count in opens.most_common() if bundle in names}
    usage["about"] = (
        f"iPhone Screen Time for the {days} days to {datetime.now():%Y-%m-%d %H:%M}, read by bin/homescreen-usage from the "
        "records the Mac keeps in sync. first_used_after_pickup and notifications still come from the Screen Time view by hand."
    )
    usage["not_on_home_screen_seconds"] = {
        bundle: round(secs) for bundle, secs in sorted(seconds.items(), key=lambda item: -item[1]) if bundle not in names and secs >= 60
    }
    USAGE.write_text(json.dumps(usage, indent=2, ensure_ascii=False) + "\n")

    total = sum(on_phone.values())
    print(f"{len(on_phone)} apps, {total / 3600:.1f} h over {days} days, from {len(changes)} focus changes.")
    # The iPhone syncs these records to the Mac in batches, often hours behind.
    print(f"Records reach {newest.astimezone():%a %H:%M}; anything after that has not synced yet.")
    for name, secs in list(week["seconds"].items())[:10]:
        print(f"  {name:<22} {secs // 3600}h {secs % 3600 // 60:02d}m")


if __name__ == "__main__":
    main()
