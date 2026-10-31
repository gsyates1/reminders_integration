"""Actions for the Reminders integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ID,
    ATTR_NAG,
    ATTR_NEXT_TRIGGER_TIME,
    ATTR_REMINDER,
    ATTR_REPEAT_FREQUENCY,
    DOMAIN,
    SERVICE_ACKNOWLEDGE,
    SERVICE_ACKNOWLEDGE_ALL,
    SERVICE_ADD,
    SERVICE_ADD_DYNAMIC,
    SERVICE_CLEAR_ALL,
    SERVICE_CLEAR_ALL_DYNAMIC,
    SERVICE_DELETE_DYNAMIC,
    SERVICE_UPDATE_DYNAMIC,
)
from .manager import ReminderManager
from .validation import non_empty_text, trigger_time, whole_days

_LOGGER = logging.getLogger(__name__)

# Unknown fields are rejected, so a misspelled field name fails loudly.
SCHEMA_NONE = vol.Schema({})
SCHEMA_ID = vol.Schema({vol.Required(ATTR_ID): cv.string})
SCHEMA_ADD = vol.Schema({vol.Required(ATTR_REMINDER): non_empty_text})
SCHEMA_ADD_DYNAMIC = vol.Schema(
    {
        vol.Required(ATTR_REMINDER): non_empty_text,
        vol.Required(ATTR_NEXT_TRIGGER_TIME): trigger_time,
        vol.Required(ATTR_REPEAT_FREQUENCY): whole_days,
        vol.Required(ATTR_NAG): cv.boolean,
    }
)
_UPDATE_FIELDS = (ATTR_REMINDER, ATTR_NEXT_TRIGGER_TIME, ATTR_REPEAT_FREQUENCY, ATTR_NAG)
SCHEMA_UPDATE_DYNAMIC = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_ID): cv.string,
            vol.Optional(ATTR_REMINDER): non_empty_text,
            vol.Optional(ATTR_NEXT_TRIGGER_TIME): trigger_time,
            vol.Optional(ATTR_REPEAT_FREQUENCY): whole_days,
            vol.Optional(ATTR_NAG): cv.boolean,
        }
    ),
    cv.has_at_least_one_key(*_UPDATE_FIELDS),
)

type _Action = Callable[[ReminderManager, dict[str, Any]], Awaitable[dict[str, Any] | None]]


def _get_manager(hass: HomeAssistant) -> ReminderManager:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError("The Reminders integration is not set up or not loaded")


def _validate(name: str, schema: Callable[[Any], Any], raw: dict[str, Any]) -> dict[str, Any]:
    try:
        return schema(raw)
    except vol.Invalid as err:
        message = humanize_error(raw, err)
        _LOGGER.debug("Action %s.%s rejected: %s", DOMAIN, name, message)
        raise ServiceValidationError(f"{DOMAIN}.{name}: {message}") from err


# ---- action bodies --------------------------------------------------------


async def _add(mgr: ReminderManager, data: dict[str, Any]) -> dict[str, Any]:
    return {"id": await mgr.async_add(data[ATTR_REMINDER])}


async def _acknowledge(mgr: ReminderManager, data: dict[str, Any]) -> None:
    await mgr.async_acknowledge(data[ATTR_ID])


async def _clear(mgr: ReminderManager, data: dict[str, Any]) -> None:
    await mgr.async_clear()


async def _add_dynamic(mgr: ReminderManager, data: dict[str, Any]) -> dict[str, Any]:
    new_id = await mgr.async_add_dynamic(
        data[ATTR_REMINDER],
        data[ATTR_NEXT_TRIGGER_TIME],
        data[ATTR_REPEAT_FREQUENCY],
        data[ATTR_NAG],
    )
    return {"id": new_id}


async def _update_dynamic(mgr: ReminderManager, data: dict[str, Any]) -> None:
    changes = {key: data[key] for key in _UPDATE_FIELDS if key in data}
    await mgr.async_update_dynamic(data[ATTR_ID], changes)


async def _delete_dynamic(mgr: ReminderManager, data: dict[str, Any]) -> None:
    await mgr.async_delete_dynamic(data[ATTR_ID])


async def _clear_dynamic(mgr: ReminderManager, data: dict[str, Any]) -> None:
    await mgr.async_clear_dynamic()


_ACTIONS: list[tuple[str, Callable[[Any], Any], _Action, SupportsResponse]] = [
    (SERVICE_ADD, SCHEMA_ADD, _add, SupportsResponse.OPTIONAL),
    (SERVICE_ACKNOWLEDGE, SCHEMA_ID, _acknowledge, SupportsResponse.NONE),
    (SERVICE_ACKNOWLEDGE_ALL, SCHEMA_NONE, _clear, SupportsResponse.NONE),
    (SERVICE_CLEAR_ALL, SCHEMA_NONE, _clear, SupportsResponse.NONE),
    (SERVICE_ADD_DYNAMIC, SCHEMA_ADD_DYNAMIC, _add_dynamic, SupportsResponse.OPTIONAL),
    (SERVICE_UPDATE_DYNAMIC, SCHEMA_UPDATE_DYNAMIC, _update_dynamic, SupportsResponse.NONE),
    (SERVICE_DELETE_DYNAMIC, SCHEMA_ID, _delete_dynamic, SupportsResponse.NONE),
    (SERVICE_CLEAR_ALL_DYNAMIC, SCHEMA_NONE, _clear_dynamic, SupportsResponse.NONE),
]


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all Reminders actions.

    Each call is logged at debug level (with its data) before anything else
    happens, so rejected calls show up in the debug log too. Input is then
    validated; any problem raises ServiceValidationError back to the caller
    and nothing is changed.
    """

    def make_handler(
        name: str, schema: Callable[[Any], Any], action: _Action
    ) -> Callable[[ServiceCall], Awaitable[ServiceResponse]]:
        async def handler(call: ServiceCall) -> ServiceResponse:
            raw = dict(call.data)
            _LOGGER.debug("Action %s.%s called with %s", DOMAIN, name, raw)
            manager = _get_manager(hass)
            data = _validate(name, schema, raw)
            result = await action(manager, data)
            if result is None:
                _LOGGER.debug("Action %s.%s done", DOMAIN, name)
            else:
                _LOGGER.debug("Action %s.%s done: %s", DOMAIN, name, result)
            return result

        return handler

    for name, schema, action, response in _ACTIONS:
        hass.services.async_register(
            DOMAIN,
            name,
            make_handler(name, schema, action),
            schema=None,  # validated inside the handler, after logging
            supports_response=response,
        )
