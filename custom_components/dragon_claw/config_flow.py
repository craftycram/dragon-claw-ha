"""Config flow: mDNS discovery or manual host entry."""

from __future__ import annotations

from typing import Any

import grpc
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DOMAIN, api


def _clean_mac(mac: str | None) -> str | None:
    """Normalize a user-entered MAC; raises vol.Invalid on garbage."""
    if not mac:
        return None
    mac = format_mac(mac.strip())
    if len(mac) != 17:
        raise vol.Invalid("invalid_mac")
    return mac


class DragonClawConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _discovered: dict[str, Any]

    async def _mac_schema(self, host: str) -> vol.Schema:
        mac = await self.hass.async_add_executor_job(api.mac_from_arp, host)
        return vol.Schema({vol.Optional(CONF_MAC, description={"suggested_value": mac}): str})

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        # The agent only listens on IPv4 (0.0.0.0).
        host = next((str(ip) for ip in discovery_info.ip_addresses if ip.version == 4), None)
        if host is None:
            return self.async_abort(reason="no_ipv4")
        name = discovery_info.name.removesuffix("." + discovery_info.type)
        await self.async_set_unique_id(name.lower())
        # PC got a new DHCP lease -> just follow it.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: discovery_info.port}
        )
        self._discovered = {
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_PORT: discovery_info.port or api.DEFAULT_PORT,
        }
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = _clean_mac(user_input.get(CONF_MAC))
            except vol.Invalid:
                errors[CONF_MAC] = "invalid_mac"
            else:
                d = self._discovered
                return self.async_create_entry(
                    title=d[CONF_NAME],
                    data={CONF_HOST: d[CONF_HOST], CONF_PORT: d[CONF_PORT], CONF_MAC: mac},
                )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=await self._mac_schema(self._discovered[CONF_HOST]),
            description_placeholders={
                "name": self._discovered[CONF_NAME],
                "host": self._discovered[CONF_HOST],
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            try:
                mac = _clean_mac(user_input.get(CONF_MAC))
                await api.get_supported_power_actions(host, port)
            except vol.Invalid:
                errors[CONF_MAC] = "invalid_mac"
            except grpc.aio.AioRpcError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host.lower())
                self._abort_if_unique_id_configured()
                if mac is None:
                    mac = await self.hass.async_add_executor_job(api.mac_from_arp, host)
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or host,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_MAC: mac},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PORT, default=api.DEFAULT_PORT): int,
                        vol.Optional(CONF_NAME): str,
                        vol.Optional(CONF_MAC): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the Wake-on-LAN MAC later."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = _clean_mac(user_input.get(CONF_MAC))
            except vol.Invalid:
                errors[CONF_MAC] = "invalid_mac"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_MAC: mac}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Optional(CONF_MAC): str}), entry.data
            ),
            errors=errors,
        )
