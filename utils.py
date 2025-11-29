import json
import os
import logging
from datetime import timedelta

logger = logging.getLogger('discord')

DATA_FILE = 'event_data.json'

EVENT_PARAMS = {
    'Ancient Ruins': {
        'duration': timedelta(hours=1),
        'interval': timedelta(hours=39)
    },
    'Altar of Darkness': {
        'duration': timedelta(hours=2),
        'interval': timedelta(hours=84)
    }
}

event_data = {
    'Ancient Ruins': {
        'next_time_iso': None, 'role_id': None, 'channel_id': None, 'reminders_sent': []
    },
    'Altar of Darkness': {
        'next_time_iso': None, 'role_id': None, 'channel_id': None, 'reminders_sent': []
    },
}

def load_data():
    """Loads event data from the JSON file into event_data."""
    global event_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                for event in event_data:
                    if event in loaded_data:
                        event_data[event].update(loaded_data[event])
                logger.info("Event data loaded from file.")
        except json.JSONDecodeError:
            logger.warning("Could not decode event data file. Starting with default settings.")
        except Exception as e:
            logger.error(f"An unexpected error occurred loading data: {e}")

def save_data():
    """Saves event data from event_data to the JSON file."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(event_data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving data to JSON file: {e}")

load_data()
