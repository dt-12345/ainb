"""
Requires Graphviz installation and the graphviz Python package (pip install graphviz)
"""

import graphviz
import json
import yaml
import random
import converter
import os
import sys

def graph(filepath): # Input can be .ainb, .json, or .yml/.yaml
    print("Converting... (May take a moment for larger files)")

    if ".json" in filepath:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
    elif ".yml" in filepath or ".yaml" in filepath:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
    else:
        converter.ainb_to_json(filepath)
        filepath = os.path.basename(filepath).replace('.ainb', '.json')
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)

    dot = graphviz.Digraph(data["Info"]["Filename"], node_attr={'shape' : 'diamond'})
    dot.format = 'svg'

    id_list = {}
    edge_list = []

    def iter_node(node_index, origin_id=None, lbl=None, already_seen=[], precon=False):
        if node_index not in already_seen and node_index < len(data["Nodes"]):
            id = str(random.random())
            id_list[node_index] = id
            dot.node(id, json.dumps(data["Nodes"][node_index], indent=4)[1:-2].replace('\n', '\l') + "\l\n")
            if origin_id != None:
                if precon:
                    dot.edge(id, origin_id, label=lbl)
                    edge_list.append((id, origin_id, lbl))
                else:
                    dot.edge(origin_id, id, label=lbl)
                    edge_list.append((origin_id, id, lbl))
            already_seen.append(node_index)
            if "Precondition Nodes" in data["Nodes"][node_index]:
                for node in data["Nodes"][node_index]["Precondition Nodes"]:
                    iter_node(node, id, "Precondition", already_seen, precon=True)
            if "Input Parameters" in data["Nodes"][node_index]:
                for type in data["Nodes"][node_index]["Input Parameters"]:
                    for parameter in data["Nodes"][node_index]["Input Parameters"][type]:
                        if "Node Index" in parameter:
                            if parameter["Node Index"] >= 0:
                                iter_node(parameter["Node Index"], id, parameter["Name"], already_seen, precon=True)
                        elif "Sources" in parameter:
                            for param in parameter["Sources"]:
                                if param["Node Index"] >= 0:
                                    iter_node(param["Node Index"], id, parameter["Name"], already_seen, precon=True)
            if "Linked Nodes" in data["Nodes"][node_index]:
                if "Standard Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    if data["Nodes"][node_index]["Node Type"] != "Element_Sequential":
                        for node in data["Nodes"][node_index]["Linked Nodes"]["Standard Link"]:
                            if "Condition" in node:
                                iter_node(node["Node Index"], id, str(node["Condition"]), already_seen)
                            elif "その他" in node:
                                iter_node(node["Node Index"], id, "Default", already_seen)
                            elif "Probability" in node:
                                iter_node(node["Node Index"], id, "Probability: " + str(node["Probability"]), already_seen)
                            elif "Condition Min" in node:
                                iter_node(node["Node Index"], id, "Min: " + str(node["Condition Min"]) + " | Max: " + str(node["Condition Max"]), already_seen)
                            else:
                                iter_node(node["Node Index"], id, node["Connection Name"], already_seen)
                    else:
                        ids = [id]
                        for node in data["Nodes"][node_index]["Linked Nodes"]["Standard Link"]:
                            ids.append(iter_node(node["Node Index"], ids[data["Nodes"][node_index]["Linked Nodes"]["Standard Link"].index(node)], None, already_seen))
                elif "Resident Update Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["Resident Update Link"]:
                        iter_node(node["Node Index"], id, "Resident Update", already_seen)
                elif "Output/bool Input/float Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["Output/bool Input/float Input Link"]:
                        iter_node(node["Node Index"], id, node["Parameter"], already_seen, precon=True)
                elif "int Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["int Input Link"]:
                        iter_node(node["Node Index"], id, node["Parameter"], already_seen, precon=True)
                elif "String Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["String Input Link"]:
                        iter_node(node["Node Index"], id, node["Parameter"], already_seen, precon=True)
            return id
        elif node_index < len(data["Nodes"]):
            if origin_id != None:
                if precon:
                    if ((id_list[node_index], origin_id, lbl)) not in edge_list:
                        dot.edge(id_list[node_index], origin_id, label=lbl)
                else:
                    if ((origin_id, id_list[node_index], lbl)) not in edge_list:
                        dot.edge(origin_id, id_list[node_index], label=lbl)
            return id_list[node_index]
        else:
            id = str(random.random())
            dot.node(id, "Invalid Node\n")
            if origin_id != None: # Not sure this is even possible, but just in case
                if precon:
                    if ((id, origin_id, lbl)) not in edge_list:
                        dot.edge(id, origin_id, label=lbl)
                else:
                    if ((origin_id, id, lbl)) not in edge_list:
                        dot.edge(origin_id, id, label=lbl)
            return id

    if "Nodes" in data:
        if data["Info"]["File Category"] != "Logic":
            for command in data["Commands"]:
                cmd_id = str(random.random())
                dot.node(cmd_id, json.dumps(command, indent=4)[1:-2] + "\n\n")
                dot.attr('node', shape='box')
                iter_node(command["Left Node Index"], cmd_id)
                if command["Right Node Index"] >= 0:
                    iter_node(command["Right Node Index"], cmd_id)
                dot.attr('node', shape='diamond')
        else:
            dot.attr('node', shape='box')
            for node in data["Nodes"]:
                iter_node(node["Node Index"])
    else:
        print("File has no nodes to graph")

    dot.render(data["Info"]["Filename"], view=True)

if __name__ == '__main__':
    globals()[sys.argv[1]](sys.argv[2])