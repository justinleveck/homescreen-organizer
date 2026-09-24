"""How much each app is used, from Screen Time as recorded in state/usage.json.

Time on screen this week counts most. Being the first app opened after picking up the
phone says it is a habit, so it counts next. Notifications say little about use, so they
count least. An app with none of these scores 0.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from layout import STATE, apps_in, identity

USAGE = STATE / "usage.json"
SCORES = STATE / "usage-scores.json"

POINTS_PER_MINUTE_THIS_WEEK = 10
POINTS_FOR_FIRST_AFTER_PICKUP = 150
POINTS_FOR_MOST_NOTIFICATIONS = 40
RANKS_THAT_EARN_POINTS = 40


@dataclass
class Usage:
    week_seconds: int = 0
    pickup_rank: int | None = None
    notification_rank: int | None = None

    @property
    def score(self):
        return round(
            self.week_seconds / 60 * POINTS_PER_MINUTE_THIS_WEEK
            + rank_points(self.pickup_rank, POINTS_FOR_FIRST_AFTER_PICKUP)
            + rank_points(self.notification_rank, POINTS_FOR_MOST_NOTIFICATIONS)
        )


def rank_points(rank, points_for_first):
    if rank is None:
        return 0
    return points_for_first * max(0, RANKS_THAT_EARN_POINTS - rank + 1) / RANKS_THAT_EARN_POINTS


def normalised(name):
    """Screen Time and SpringBoard spell the same name with different invisible characters."""
    visible = re.sub(r"[​-‏‪-‮⁠﻿]", "", name)
    return " ".join(visible.split()).casefold()


def usage_by_name(path=USAGE):
    week = json.loads(Path(path).read_text()).get("week", {}) if Path(path).exists() else {}
    usage = {}

    def usage_of(name):
        return usage.setdefault(normalised(name), Usage())

    for name, seconds in week.get("seconds", {}).items():
        usage_of(name).week_seconds = seconds
    for rank, name in enumerate(week.get("first_used_after_pickup", []), start=1):
        usage_of(name).pickup_rank = rank
    for rank, name in enumerate(week.get("notifications", []), start=1):
        usage_of(name).notification_rank = rank
    return usage


class UsageScores:
    """Usage matched to the apps on the phone, by display name."""

    def __init__(self, layout, path=USAGE):
        self.by_name = usage_by_name(path)
        self.names_on_phone = {normalised(app.get("displayName", "")) for app in apps_in(layout)}

    def usage_of(self, app):
        return self.by_name.get(normalised(app.get("displayName", "")), Usage())

    def score_of(self, app):
        return self.usage_of(app).score

    def unmatched_names(self):
        return sorted(name for name in self.by_name if name not in self.names_on_phone)

    def save_for_editor(self, layout, path=SCORES):
        scores = {
            identity(app): {"name": app.get("displayName"), "score": usage.score, **usage.__dict__}
            for app in apps_in(layout)
            if (usage := self.usage_of(app)).score
        }
        Path(path).write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n")
