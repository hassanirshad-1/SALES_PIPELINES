import os
import json

def ensure_dir(directory):
    """Safely creates a directory if it doesn't exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def log_error(slug, message, output_dir="output"):
    """Logs an error to the errors.log file."""
    ensure_dir(output_dir)
    log_path = os.path.join(output_dir, "errors.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{slug}] {message}\n")

def read_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
