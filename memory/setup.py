import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base.util import Util

# Set up the directory path
#home_dir = os.path.expanduser("~")
memory_dir = Util().data_path()
#os.makedirs(memory_dir, exist_ok=True)


def setup_config():
    config_path = os.path.join(memory_dir, "config.json")
    if not os.path.exists(config_path):
        user_id = str(uuid.uuid4())
        config = {"user_id": user_id}
        with open(config_path, "w") as config_file:
            json.dump(config, config_file, indent=4)


def get_user_id():
    config_path = os.path.join(memory_dir, "config.json")
    if not os.path.exists(config_path):
        return "anonymous_user"

    try:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
            user_id = config.get("user_id")
            return user_id
    except Exception:
        return "anonymous_user"
