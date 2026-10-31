"""Sensors for the Reminders integration."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_REMINDERS, KEY_DYNAMIC, KEY_REMINDERS
from .manager import ReminderManager, RemindersConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemindersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensor.reminders and sensor.dynamic_reminders."""
    manager = entry.runtime_data
    async_add_entities(
        [
            ReminderCountSensor(manager, entry.entry_id, KEY_REMINDERS, "Reminders", "mdi:bell-outline"),
            ReminderCountSensor(
                manager, entry.entry_id, KEY_DYNAMIC, "Dynamic Reminders", "mdi:bell-cog-outline"
            ),
        ]
    )


class ReminderCountSensor(SensorEntity):
    """State = number of items; 'reminders' attribute = the collection."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Keep the (possibly large) collection out of the recorder database.
    _unrecorded_attributes = frozenset({ATTR_REMINDERS})

    def __init__(
        self, manager: ReminderManager, entry_id: str, key: str, name: str, icon: str
    ) -> None:
        """Initialize."""
        self._manager = manager
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        """Update whenever the data changes."""
        self.async_on_remove(self._manager.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> int:
        """Number of items (always matches the collection)."""
        return len(self._manager.get(self._key))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The collection itself."""
        return {ATTR_REMINDERS: copy.deepcopy(self._manager.get(self._key))}
