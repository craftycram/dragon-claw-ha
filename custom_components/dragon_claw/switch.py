"""Power switch: on = Wake-on-LAN, off = power off, state = agent reachable."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DragonClawConfigEntry, DragonClawEntity, api


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DragonClawConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([DragonClawPowerSwitch(entry.runtime_data, "power")])


class DragonClawPowerSwitch(DragonClawEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "power"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.wake()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.perform(api.PowerAction.POWER_OFF)
