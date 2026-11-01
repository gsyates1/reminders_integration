"""Storage and in-memory state for the Reminders integration.

All data lives in .storage/reminders.data. Every change is made on a copy,
written to disk, and only then made current, so a failed action never
leaves the lists half-changed. Writes are atomic: the file is replaced in
one step and can't be left half-written.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import copy
import logging
import secrets
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_NAG,
    ATTR_NEXT_TRIGGER_TIME,
    ATTR_REMINDER,
    ATTR_REPEAT_FREQUENCY,
    KEY_DYNAMIC,
    KEY_REMINDERS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

type RemindersConfigEntry = ConfigEntry[ReminderManager]


class ReminderManager:
    """Holds both reminder collections and saves every change."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
        )
        self._data: dict[str, dict[str, Any]] = {KEY_REMINDERS: {}, KEY_DYNAMIC: {}}
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []

    # ---- loading -------------------------------------------------------

    async def async_load(self) -> None:
        """Load stored data, creating empty collections on first run.

        Raises HomeAssistantError if the file exists but can't be used; the
        file is then left alone rather than replaced with empty lists.
        """
        stored = await self._store.async_load()
        if stored is None:
            _LOGGER.debug("No stored reminders found; starting with empty lists")
            await self._store.async_save(self._data)
            return

        if not isinstance(stored, dict):
            raise HomeAssistantError("stored reminder data is not a dictionary")
        for key in (KEY_REMINDERS, KEY_DYNAMIC):
            value = stored.get(key, {})
            if not isinstance(value, dict):
                raise HomeAssistantError(f"stored '{key}' is not a dictionary")
            self._data[key] = value
        _LOGGER.debug(
            "Loaded %d reminders and %d dynamic reminders",
            len(self._data[KEY_REMINDERS]),
            len(self._data[KEY_DYNAMIC]),
        )

    # ---- reading / listeners -------------------------------------------

    def get(self, key: str) -> dict[str, Any]:
        """Return a collection (do not modify the result)."""
        return self._data[key]

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Call update_callback after every change. Returns a remover."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    # ---- helpers -------------------------------------------------------

    def _new_id(self) -> str:
        """Return a random 8-character ID not used in either collection."""
        while True:
            new_id = secrets.token_hex(4)
            if new_id not in self._data[KEY_REMINDERS] and new_id not in self._data[KEY_DYNAMIC]:
                return new_id

    def _require(self, key: str, item_id: str) -> None:
        if item_id not in self._data[key]:
            kind = "dynamic reminder" if key == KEY_DYNAMIC else "reminder"
            raise ServiceValidationError(f"No {kind} with id '{item_id}'")

    async def _async_commit(self, new_data: dict[str, dict[str, Any]]) -> None:
        """Save new_data, make it current and notify the sensors."""
        await self._store.async_save(new_data)
        self._data = new_data
        for listener in list(self._listeners):
            listener()

    # ---- reminders -----------------------------------------------------

    async def async_add(self, text: str) -> str:
        async with self._lock:
            new_id = self._new_id()
            new = copy.deepcopy(self._data)
            new[KEY_REMINDERS][new_id] = text
            await self._async_commit(new)
            return new_id

    async def async_acknowledge(self, item_id: str) -> str:
        """Remove a reminder and return its text."""
        async with self._lock:
            self._require(KEY_REMINDERS, item_id)
            new = copy.deepcopy(self._data)
            text = new[KEY_REMINDERS].pop(item_id)
            await self._async_commit(new)
            return text

    async def async_clear(self) -> dict[str, str]:
        """Remove all reminders and return what was removed ({id: text})."""
        async with self._lock:
            removed = self._data[KEY_REMINDERS]
            new = copy.deepcopy(self._data)
            new[KEY_REMINDERS] = {}
            await self._async_commit(new)
            return removed

    # ---- dynamic reminders ---------------------------------------------

    async def async_add_dynamic(
        self, text: str, next_trigger_time: str, repeat_frequency: int, nag: bool
    ) -> str:
        async with self._lock:
            new_id = self._new_id()
            new = copy.deepcopy(self._data)
            new[KEY_DYNAMIC][new_id] = {
                ATTR_REMINDER: text,
                ATTR_NEXT_TRIGGER_TIME: next_trigger_time,
                ATTR_REPEAT_FREQUENCY: repeat_frequency,
                ATTR_NAG: nag,
            }
            await self._async_commit(new)
            return new_id

    async def async_update_dynamic(self, item_id: str, changes: dict[str, Any]) -> None:
        async with self._lock:
            self._require(KEY_DYNAMIC, item_id)
            new = copy.deepcopy(self._data)
            new[KEY_DYNAMIC][item_id].update(changes)
            await self._async_commit(new)

    async def async_delete_dynamic(self, item_id: str) -> None:
        async with self._lock:
            self._require(KEY_DYNAMIC, item_id)
            new = copy.deepcopy(self._data)
            del new[KEY_DYNAMIC][item_id]
            await self._async_commit(new)

    async def async_clear_dynamic(self) -> None:
        async with self._lock:
            new = copy.deepcopy(self._data)
            new[KEY_DYNAMIC] = {}
            await self._async_commit(new)
