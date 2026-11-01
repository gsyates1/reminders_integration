# Reminders – custom Home Assistant integration

Replaces the `sensor.reminders` and `sensor.dynamic_reminders` trigger-template sensors.

## Install

1. **Remove the old template sensors.** Delete both trigger blocks from your YAML and reload template entities (or restart).
   Then go to **Settings → Devices & services → Entities**, find `sensor.reminders` and
   `sensor.dynamic_reminders` (now shown as "no longer provided"), and delete them. If you skip
   this, the new sensors are created as `sensor.reminders_2` / `sensor.dynamic_reminders_2`.
2. Copy the `custom_components/reminders` folder into your HA config folder so you have
   `config/custom_components/reminders/manifest.json`.
3. Restart Home Assistant.
4. **Settings → Devices & services → Add integration → Reminders → Submit.**

Both sensors start at 0. Data is kept in `config/.storage/reminders.data` (atomic writes) and
survives restarts. Removing the integration leaves that file in place, so re-adding it brings the
reminders back.

## Sensors

| Entity | State | `reminders` attribute |
|---|---|---|
| `sensor.reminders` | number of reminders | `{id: "text"}` |
| `sensor.dynamic_reminders` | number of dynamic reminders | `{id: {reminder, next_trigger_time, repeat_frequency, nag}}` |

The `reminders` attribute is excluded from the recorder (history/database).

## Actions

Every action validates its input. On any problem (unknown ID, missing or invalid field, misspelled
field name) it raises an error to the caller and changes nothing.

| Action | Fields | Returns |
|---|---|---|
| `reminders.add` | `reminder` | `{id}` |
| `reminders.acknowledge` | `id` | |
| `reminders.acknowledge_all` | | |
| `reminders.clear_all` | | |
| `reminders.add_dynamic` | `reminder`, `next_trigger_time`, `repeat_frequency`, `nag` (all required) | `{id}` |
| `reminders.update_dynamic` | `id` + any of `reminder`, `next_trigger_time`, `repeat_frequency`, `nag` | |
| `reminders.delete_dynamic` | `id` | |
| `reminders.clear_all_dynamic` | | |

- `next_trigger_time`: date **and** time required. Seconds, fraction and offset are optional;
  `T` or a space between date and time. No offset = HA local time. Stored with the offset, e.g.
  `2026-10-31 11:33:10.095534-04:00` or `2026-12-01 09:00:00-05:00`.
- `repeat_frequency`: whole days, 0 or more (0 = don't repeat).
- `nag`: true/false.

### Examples

```yaml
# Add and keep the new ID
- action: reminders.add
  data:
    reminder: "Take out the trash"
  response_variable: added
- action: notify.notify
  data:
    message: "Reminder {{ added.id }} created"

# Add a dynamic reminder 30 days from now
- action: reminders.add_dynamic
  data:
    reminder: "Change the furnace filter"
    next_trigger_time: "{{ now() + timedelta(days=30) }}"
    repeat_frequency: 30
    nag: false
  response_variable: dyn

# Move it to its next date (only the changed field)
- action: reminders.update_dynamic
  data:
    id: "{{ dyn.id }}"
    next_trigger_time: "{{ now() + timedelta(days=30) }}"

- action: reminders.acknowledge
  data:
    id: "{{ added.id }}"
```

Reading the data in templates works as before:

```jinja
{{ state_attr('sensor.dynamic_reminders', 'reminders') }}
{% for id, r in state_attr('sensor.dynamic_reminders', 'reminders').items() %}
  {{ id }}: {{ r.reminder }} at {{ as_datetime(r.next_trigger_time) }}
{% endfor %}
```

## Events

| Event | Fired by | Event data |
|---|---|---|
| `reminder_acknowledged` | `reminders.acknowledge` | `id`, `reminder` (the text of the acknowledged reminder) |
| `all_reminders_acknowledged` | `reminders.acknowledge_all` | `reminders`: `{id: "text"}` of everything that was cleared (`{}` if the list was already empty) |

Events are fired only after the change is saved, so a rejected call (e.g. unknown ID) fires
nothing. `reminders.clear_all` does not fire an event.

```yaml
triggers:
  - trigger: event
    event_type: reminder_acknowledged
actions:
  - action: notify.notify
    data:
      message: "Done: {{ trigger.event.data.reminder }}"
```

## Logging

**Settings → Devices & services → Reminders → ⋮ → Enable debug logging.** While on, every
action call is logged with its data, including rejected calls and why. Turning it off offers the
captured log as a download.
