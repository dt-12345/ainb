from converter import json_to_ainb
from converter import ainb_to_json
import os
from pathlib import Path
import json
##------------------------Converting and Reading Ainb Data------------------------##
# creating current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
print(current_dir)

#save the file name
filename = input("  Name of the file to edit? (ex: 'LogicTest.root.ainb') :: ")

#convert the ainb to a Json
ainb_to_json( Path( str(current_dir) + "\\" + filename), str(current_dir) + filename[0:-4])

#Saving the path to the new Json
JsonPath = current_dir + "\\" + filename[0:-4] + "json"
filename = filename[0:-4]

# Open the JSON file
with open(JsonPath, encoding="utf8") as data:
    # Load the JSON data into a Python dictionary
    data = json.load(data)

##------------------------Pygame------------------------##
