import database
import json

def load_additional_folders():
    """Loads the list of additional network folders from the database."""
    return database.get_additional_folders()

def save_additional_folders(folders):
    """Saves the list of additional network folders to the database."""
    database.save_additional_folders(folders)

def load_note_options():
    """Loads note options from the database."""
    return database.get_note_options()

def add_note_option(option):
    """Adds a new note option to the database."""
    database.add_note_option(option)

def load_all_notes():
    """Loads all consumer notes from the database."""
    return database.get_all_notes()

def save_note(cid, note, remarks):
    """Saves a single consumer note to the database."""
    database.save_note(cid, note, remarks)

def delete_note(cid):
    """Deletes a consumer note from the database."""
    database.delete_note(cid)

def get_meter_number(consumer_id):
    """Retrieves a meter number for a given consumer ID from the database."""
    return database.get_meter_number(consumer_id)
    
def get_consumer_by_meter(meter_no):
    """Retrieves a consumer id for a given meter number from the database."""
    return database.get_consumer_by_meter(meter_no)
    
def update_meter_mapping(mapping_dict):
    """Updates the meter mapping in the database."""
    database.update_meter_mapping(mapping_dict)

def save_search_history(key, val):
    try:
        d = database.get_info_value("search_history", {"consumer_ids": [], "meter_numbers": []})
        if val in d[key]: d[key].remove(val)
        d[key].append(val)
        if len(d[key]) > 10: d[key] = d[key][-10:]
        database.set_info_value("search_history", d)
    except:
        pass

def load_search_history(key):
    try:
        d = database.get_info_value("search_history", {"consumer_ids": [], "meter_numbers": []})
        return d.get(key, [])
    except:
        return []

def console_log(message):
    """Prints a message to the console with a timestamp."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
