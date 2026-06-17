import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

CLOUD_ACCOUNT = os.getenv("CLOUD_ACCOUNT", "")
CLOUD_PASSWORD = os.getenv("CLOUD_PASSWORD", "")
DEVICE_ID = os.getenv("DEVICE_ID", "")
CLOUD_CLIENT_UUID = os.getenv("CLOUD_CLIENT_UUID", "")
