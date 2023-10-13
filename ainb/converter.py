import json
import yaml
import ainb
import sys

def ainb_to_json(filepath):
    with open(filepath, 'rb') as file:
        data = file.read()
    file = ainb.AINB(data)
    with open(file.filename + ".json", 'w', encoding='utf-8') as outfile:
        json.dump(file.output_dict, outfile, ensure_ascii=False, indent=4)

def json_to_ainb(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        data = json.load(file)
    file = ainb.AINB(data, from_dict=True)
    with open(file.filename + ".ainb", 'wb') as outfile:
        file.ToBytes(file, outfile)

def ainb_to_yaml(filepath):
    with open(filepath, 'rb') as file:
        data = file.read()
    file = ainb.AINB(data)
    with open(file.filename + ".yml", 'w', encoding='utf-8') as outfile:
        yaml.dump(file.output_dict, outfile, sort_keys=False)

def yaml_to_ainb(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
    file = ainb.AINB(data, from_dict=True)
    with open(file.filename + ".ainb", 'wb') as outfile:
        file.ToBytes(file, outfile)
        
if __name__ == '__main__':
    globals()[sys.argv[1]](sys.argv[2])