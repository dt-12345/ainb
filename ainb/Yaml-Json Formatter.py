import yaml
import json

# Load the YAML file
with open("Node.Product.900.Lobby.yaml", "r") as file:
    YamlDat = yaml.safe_load(file)

with open("NodeDefinition.json", "r",encoding="utf8") as file:
    jsondat = json.load(file)


for item in YamlDat["root"]:

    if( item not in jsondat ):
        amdone = False
        while( not(amdone)):
            

print(jsondat["UniqueFlowSequenceSpl"])