"""One USB session with the iPhone's SpringBoard, through pymobiledevice3."""

from contextlib import asynccontextmanager

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.springboard import SpringBoardServicesService


@asynccontextmanager
async def springboard():
    lockdown = await create_using_usbmux(autopair=False)
    try:
        async with SpringBoardServicesService(lockdown=lockdown) as service:
            yield service
    finally:
        await lockdown.close()
