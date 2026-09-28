"""One button per agent power action."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DragonClawConfigEntry, DragonClawCoordinator, DragonClawEntity, api


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DragonClawConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [
        DragonClawActionButton(coordinator, action) for action in api.PowerAction
    ]
    if entry.data.get(CONF_MAC):
        entities.append(DragonClawWakeButton(coordinator, "wake"))
    async_add_entities(entities)


class DragonClawActionButton(DragonClawEntity, ButtonEntity):
    def __init__(self, coordinator: DragonClawCoordinator, action: api.PowerAction) -> None:
        super().__init__(coordinator, action.name.lower())
        self._action = action
        self._attr_translation_key = action.name.lower()
        if action is api.PowerAction.REBOOT:
            self._attr_device_class = ButtonDeviceClass.RESTART

    @property
    def available(self) -> bool:
        # Actions the PC doesn't support (or all, while offline) stay unavailable.
        return bool(self.coordinator.data) and self._action in self.coordinator.data

    async def async_press(self) -> None:
        await self.coordinator.perform(self._action)


class DragonClawWakeButton(DragonClawEntity, ButtonEntity):
    _attr_translation_key = "wake"

    async def async_press(self) -> None:
        await self.coordinator.wake()
