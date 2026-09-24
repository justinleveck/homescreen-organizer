"""Read the phone's Home Screen into state/current.json, with every icon as a PNG."""

import asyncio

from layout import CURRENT, ICONS, apps_in, identity, is_web_clip, save, save_backup
from phone import springboard


async def read_home_screen():
    async with springboard() as service:
        layout = await service.get_icon_state()
        saved, missing = await save_icons(service, list(apps_in(layout)))

    save(layout, CURRENT)
    backup = save_backup(layout, "read")
    report(layout, saved, missing, backup)


async def save_icons(service, apps):
    ICONS.mkdir(parents=True, exist_ok=True)
    saved, missing = 0, []
    for app in apps:
        png = await icon_png(service, app)
        if png:
            (ICONS / f"{identity(app)}.png").write_bytes(png)
            saved += 1
        else:
            missing.append(app)
    return saved, missing


async def icon_png(service, app):
    try:
        return await service.get_icon_pngdata(identity(app))
    except Exception:
        if is_web_clip(app):
            return None
        raise


def report(layout, saved, missing, backup):
    app_count = len(list(apps_in(layout)))
    print(f"Read {app_count} icons across {len(layout) - 1} pages and the dock.")
    print(f"Saved {saved} icon images to {ICONS}.")
    for app in missing:
        kind = "web clip" if is_web_clip(app) else "app"
        print(f"  no image for {kind} {app.get('displayName')} ({identity(app)}); the editor shows a placeholder")
    print(f"Layout in {CURRENT}; backup in {backup}.")


asyncio.run(read_home_screen())
