import json
import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.reminders.const import DOMAIN


async def _setup(hass, hass_storage=None):
    await hass.config.async_set_time_zone("America/Indianapolis")
    entry = MockConfigEntry(domain=DOMAIN, title="Reminders", data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def call(hass, service, data=None, response=False):
    return await hass.services.async_call(
        DOMAIN, service, data or {}, blocking=True, return_response=response
    )


def attr(hass, entity):
    return hass.states.get(entity).attributes["reminders"]


async def test_reminders_flow(hass, hass_storage):
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.reminders").state == "0"
    assert hass.states.get("sensor.dynamic_reminders").state == "0"

    r1 = (await call(hass, "add", {"reminder": "Trash"}, True))["id"]
    r2 = (await call(hass, "add", {"reminder": "Mail"}, True))["id"]
    assert len(r1) == 8 and r1 != r2
    # call without asking for response also works
    await call(hass, "add", {"reminder": "Dishes"})
    assert hass.states.get("sensor.reminders").state == "3"
    assert attr(hass, "sensor.reminders")[r1] == "Trash"

    await call(hass, "acknowledge", {"id": r1})
    assert hass.states.get("sensor.reminders").state == "2"
    assert r1 not in attr(hass, "sensor.reminders")

    with pytest.raises(ServiceValidationError, match="No reminder with id"):
        await call(hass, "acknowledge", {"id": r1})
    assert hass.states.get("sensor.reminders").state == "2"

    await call(hass, "acknowledge_all")
    assert hass.states.get("sensor.reminders").state == "0"
    await call(hass, "add", {"reminder": "x"})
    await call(hass, "clear_all")
    assert attr(hass, "sensor.reminders") == {}

    # bad input rejected
    for bad in ({}, {"reminder": ""}, {"reminder": "x", "unique_id": "a"}):
        with pytest.raises(ServiceValidationError):
            await call(hass, "add", bad)
    assert hass.states.get("sensor.reminders").state == "0"


async def test_dynamic_flow(hass, hass_storage):
    await _setup(hass)
    d = (
        await call(
            hass,
            "add_dynamic",
            {
                "reminder": "Filter",
                "next_trigger_time": "2026-10-31 11:33:10.095534-04:00",
                "repeat_frequency": 30,
                "nag": True,
            },
            True,
        )
    )["id"]
    item = attr(hass, "sensor.dynamic_reminders")[d]
    assert item == {
        "reminder": "Filter",
        "next_trigger_time": "2026-10-31 11:33:10.095534-04:00",
        "repeat_frequency": 30,
        "nag": True,
    }
    assert hass.states.get("sensor.dynamic_reminders").state == "1"

    # partial update; naive time -> local offset; no seconds/micro
    await call(hass, "update_dynamic", {"id": d, "next_trigger_time": "2026-12-01 09:00"})
    item = attr(hass, "sensor.dynamic_reminders")[d]
    assert item["next_trigger_time"] == "2026-12-01 09:00:00-05:00"  # EST in December
    assert item["reminder"] == "Filter" and item["repeat_frequency"] == 30

    await call(hass, "update_dynamic", {"id": d, "repeat_frequency": "0", "nag": "off"})
    item = attr(hass, "sensor.dynamic_reminders")[d]
    assert item["repeat_frequency"] == 0 and item["nag"] is False
    # template result for the time parses back
    assert dt_util.parse_datetime(item["next_trigger_time"]) is not None

    bad_cases = [
        ("update_dynamic", {"id": "nope", "nag": True}),
        ("update_dynamic", {"id": d}),  # nothing to change
        ("update_dynamic", {"id": d, "next_trigger_time": "2026-10-31"}),
        ("update_dynamic", {"id": d, "next_trigger_time": "2026-02-30 10:00"}),
        ("update_dynamic", {"id": d, "next_trigger_time": "tomorrow"}),
        ("update_dynamic", {"id": d, "repeat_frequency": -1}),
        ("update_dynamic", {"id": d, "repeat_frequency": 1.5}),
        ("update_dynamic", {"id": d, "repeat_frequency": True}),
        ("add_dynamic", {"reminder": "x", "next_trigger_time": "2026-10-31 10:00", "repeat_frequency": 1}),
        ("delete_dynamic", {"id": "nope"}),
    ]
    before = attr(hass, "sensor.dynamic_reminders")
    for service, data in bad_cases:
        with pytest.raises(ServiceValidationError):
            await call(hass, service, data)
    assert attr(hass, "sensor.dynamic_reminders") == before

    # other accepted formats
    for t, expected in [
        ("2026-10-31T11:33:10", "2026-10-31 11:33:10-04:00"),
        ("2026-10-31 11:33:10Z", "2026-10-31 11:33:10+00:00"),
        ("2026-10-31 11:33:10.5-04:00", "2026-10-31 11:33:10.500000-04:00"),
    ]:
        await call(hass, "update_dynamic", {"id": d, "next_trigger_time": t})
        assert attr(hass, "sensor.dynamic_reminders")[d]["next_trigger_time"] == expected

    await call(hass, "delete_dynamic", {"id": d})
    assert hass.states.get("sensor.dynamic_reminders").state == "0"
    await call(hass, "add_dynamic", {"reminder": "a", "next_trigger_time": "2026-11-01 08:00", "repeat_frequency": 0, "nag": False})
    await call(hass, "clear_all_dynamic")
    assert attr(hass, "sensor.dynamic_reminders") == {}


async def test_persistence_and_reload(hass, hass_storage):
    entry = await _setup(hass)
    rid = (await call(hass, "add", {"reminder": "Keep me"}, True))["id"]
    await hass.async_block_till_done()
    stored = hass_storage["reminders.data"]["data"]
    assert stored["reminders"] == {rid: "Keep me"}

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert attr(hass, "sensor.reminders") == {rid: "Keep me"}
    assert hass.states.get("sensor.reminders").state == "1"


async def test_loads_existing_storage(hass, hass_storage):
    hass_storage["reminders.data"] = {
        "version": 1,
        "key": "reminders.data",
        "data": {"reminders": {"abc12345": "Old"}, "dynamic_reminders": {}},
    }
    await _setup(hass)
    assert attr(hass, "sensor.reminders") == {"abc12345": "Old"}


async def test_bad_storage_fails_setup_without_overwrite(hass, hass_storage):
    bad = {"version": 1, "key": "reminders.data", "data": {"reminders": "garbage"}}
    hass_storage["reminders.data"] = bad
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert hass_storage["reminders.data"] == bad
    with pytest.raises(ServiceValidationError, match="not set up or not loaded"):
        await call(hass, "add", {"reminder": "x"})


async def test_debug_logging(hass, hass_storage, caplog):
    await _setup(hass)
    caplog.set_level(logging.DEBUG, logger="custom_components.reminders")
    await call(hass, "add", {"reminder": "Logged"})
    with pytest.raises(ServiceValidationError):
        await call(hass, "add", {"reminder": ""})
    text = caplog.text
    assert "reminders.add called with {'reminder': 'Logged'}" in text
    assert "reminders.add rejected" in text


async def test_not_recorded(hass, hass_storage):
    from homeassistant.helpers import entity_registry as er  # noqa: F401
    await _setup(hass)
    from custom_components.reminders.sensor import ReminderCountSensor
    assert "reminders" in ReminderCountSensor._unrecorded_attributes


async def test_config_flow_single_instance(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "abort"


async def test_service_descriptions(hass, hass_storage):
    from homeassistant.helpers.service import async_get_all_descriptions
    await _setup(hass)
    desc = (await async_get_all_descriptions(hass))[DOMAIN]
    assert set(desc) == {"add", "acknowledge", "acknowledge_all", "clear_all", "add_dynamic",
                         "update_dynamic", "delete_dynamic", "clear_all_dynamic"}
    assert "next_trigger_time" in desc["add_dynamic"]["fields"]


async def test_acknowledge_events(hass, hass_storage):
    from pytest_homeassistant_custom_component.common import async_capture_events

    await _setup(hass)
    single = async_capture_events(hass, "reminder_acknowledged")
    every = async_capture_events(hass, "all_reminders_acknowledged")

    r1 = (await call(hass, "add", {"reminder": "Trash"}, True))["id"]
    r2 = (await call(hass, "add", {"reminder": "Mail"}, True))["id"]

    await call(hass, "acknowledge", {"id": r1})
    await hass.async_block_till_done()
    assert len(single) == 1
    assert single[0].data == {"id": r1, "reminder": "Trash"}

    # failed acknowledge fires nothing
    with pytest.raises(ServiceValidationError):
        await call(hass, "acknowledge", {"id": r1})
    await hass.async_block_till_done()
    assert len(single) == 1

    await call(hass, "acknowledge_all")
    await hass.async_block_till_done()
    assert len(every) == 1
    assert every[0].data == {"reminders": {r2: "Mail"}}

    # still fired when the list is already empty
    await call(hass, "acknowledge_all")
    await hass.async_block_till_done()
    assert len(every) == 2
    assert every[1].data == {"reminders": {}}

    # clear_all does not fire the acknowledge event
    await call(hass, "add", {"reminder": "x"})
    await call(hass, "clear_all")
    await hass.async_block_till_done()
    assert len(every) == 2 and len(single) == 1
