import os
import json

ADMIN_IDS = [93365812, 809612055]
BASE_DATA_DIR = "Users_Data"
STATUS_DIRS = {
    "approved": os.path.join(BASE_DATA_DIR, "approved"),
    "denied": os.path.join(BASE_DATA_DIR, "denied"),
    "blocked": os.path.join(BASE_DATA_DIR, "blocked"),
    "pending": os.path.join(BASE_DATA_DIR, "pending")
}

for path in STATUS_DIRS.values():
    os.makedirs(path, exist_ok=True)

def get_user_status(user_id):
    """Checks the status of a user."""
    if user_id in ADMIN_IDS:
        return "admin"
    
    for status, path in STATUS_DIRS.items():
        if os.path.exists(os.path.join(path, f"{user_id}.json")):
            return status
    return "new"

def save_user_data(user_data, status):
    """Saves user info and updates their status."""
    user_id = str(user_data['id'])
    filename = f"{user_id}.json"
    
    for path in STATUS_DIRS.values():
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            
    if status in STATUS_DIRS:
        target_path = os.path.join(STATUS_DIRS[status], filename)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=4, ensure_ascii=False)

def get_user_info(user_id):
    """Retrieves user details from the database."""
    for path in STATUS_DIRS.values():
        filepath = os.path.join(path, f"{user_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None

def load_users_by_status(status):
    """Returns a list of all users with a specific status."""
    path = STATUS_DIRS.get(status)
    users = []
    if path and os.path.exists(path):
        for filename in os.listdir(path):
            if filename.endswith(".json"):
                with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                    users.append(json.load(f))
    return users