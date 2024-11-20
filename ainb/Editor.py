from converter import json_to_ainb
from converter import ainb_to_json
import os
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
print(current_dir)
ainb_to_json(Path( str(current_dir) + "\\" +input("  Name of the file to edit? Name, not Path. :: ")))