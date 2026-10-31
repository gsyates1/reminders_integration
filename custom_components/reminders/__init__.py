"""The Reminders integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import ReminderManager, RemindersConfigEntry
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions (once, independent of the config entry)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RemindersConfigEntry) -> bool:
    """Load stored reminders and create the sensors."""
    manager = ReminderManager(hass)
    try:
        await manager.async_load()
    except (HomeAssistantError, ValueError, OSError) as err:
        # Don't start with empty lists: that would overwrite the file on the
        # next change. Fail setup and leave the file for inspection.
        raise ConfigEntryError(
            f"Could not load .storage/reminders.data ({err}); the file was left unchanged"
        ) from err

    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemindersConfigEntry) -> bool:
    """Unload the sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
