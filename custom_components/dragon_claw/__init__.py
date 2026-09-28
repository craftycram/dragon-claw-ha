"""Dragon Claw integration: power control for PCs running the Dragon Claw agent."""

from __future__ import annotations

import logging
from datetime import timedelta

import grpc

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import api

DOMAIN = "dragon_claw"
PLATFORMS = [Platform.BUTTON, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)

type DragonClawConfigEntry = ConfigEntry[DragonClawCoordinator]


class DragonClawCoordinator(DataUpdateCoordinator[set[api.PowerAction] | None]):
    """Polls supported actions; data is None while the PC is offline."""

    config_entry: DragonClawConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DragonClawConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=30),
        )

    @property
    def host(self) -> str:
        return self.config_entry.data[CONF_HOST]

    @property
    def port(self) -> int:
        return self.config_entry.data[CONF_PORT]

    async def _async_update_data(self) -> set[api.PowerAction] | None:
        # Offline is a normal state (it's what "switch off" means), not an update failure.
        try:
            return await api.get_supported_power_actions(self.host, self.port)
        except grpc.aio.AioRpcError:
            return None

    async def perform(self, action: api.PowerAction) -> None:
        try:
            await api.perform_power_action(self.host, self.port, action)
        except grpc.aio.AioRpcError as err:
            raise HomeAssistantError(f"{action.name} failed: {err.details()}") from err
        await self.async_request_refresh()

    async def wake(self) -> None:
        mac = self.config_entry.data.get(CONF_MAC)
        if not mac:
            raise HomeAssistantError("No MAC address configured for Wake-on-LAN")
        await self.hass.async_add_executor_job(api.send_magic_packet, mac)


class DragonClawEntity(CoordinatorEntity[DragonClawCoordinator]):
    """Base entity bound to the PC device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DragonClawCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        mac = entry.data.get(CONF_MAC)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=entry.title,
            manufacturer="Dragon Claw",
        )


async def async_setup_entry(hass: HomeAssistant, entry: DragonClawConfigEntry) -> bool:
    coordinator = DragonClawCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: DragonClawConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DragonClawConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
