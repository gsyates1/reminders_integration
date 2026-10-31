"""Constants for the Reminders integration."""

DOMAIN = "reminders"

STORAGE_KEY = f"{DOMAIN}.data"
STORAGE_VERSION = 1

# Keys in the stored data (and which sensor shows them)
KEY_REMINDERS = "reminders"
KEY_DYNAMIC = "dynamic_reminders"

# Sensor attribute that holds the collection
ATTR_REMINDERS = "reminders"

# Action field names
ATTR_ID = "id"
ATTR_REMINDER = "reminder"
ATTR_NEXT_TRIGGER_TIME = "next_trigger_time"
ATTR_REPEAT_FREQUENCY = "repeat_frequency"
ATTR_NAG = "nag"

# Action names
SERVICE_ADD = "add"
SERVICE_ACKNOWLEDGE = "acknowledge"
SERVICE_ACKNOWLEDGE_ALL = "acknowledge_all"
SERVICE_CLEAR_ALL = "clear_all"
SERVICE_ADD_DYNAMIC = "add_dynamic"
SERVICE_UPDATE_DYNAMIC = "update_dynamic"
SERVICE_DELETE_DYNAMIC = "delete_dynamic"
SERVICE_CLEAR_ALL_DYNAMIC = "clear_all_dynamic"
