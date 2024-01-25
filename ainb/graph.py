"""
Requires Graphviz installation and the graphviz Python package (pip install graphviz)
"""

import graphviz
import json
import yaml
import uuid
import converter
import os
import sys

# Input can be .ainb, .json, or .yml/.yaml
# Recurse controls whether or not to include embedded AINB files in the graph
# The other arguments are passed automatically when recursively iterating
def graph(filepath, recurse=False, parent_id=None, dot=None, index=None):
    if parent_id == None:
        print("Converting... (may take a moment for larger files)")

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

    if dot == None:
        dot = graphviz.Digraph(data["Info"]["Filename"], node_attr={'shape' : 'diamond'})
        dot.format = 'svg'

    precondition_nodes = []

    for node in data["Nodes"]:
        if "Flags" in node and "Is Precondition Node" in node["Flags"]:
            precondition_nodes.append(node["Node Index"])

    id_list = {}
    edge_list = []

    def iter_node(node_index, origin_id=None, lbl=None, already_seen=[], precon=False):
        dot.attr('node', shape='box')
        if node_index not in already_seen and node_index < len(data["Nodes"]):
            id = str(uuid.uuid4())
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
            if recurse:
                if "Flags" in data["Nodes"][node_index]:
                    if "Is External AINB" in data["Nodes"][node_index]["Flags"]:
                        extensions = [".json", ".ainb", ".yml", ".yaml"]
                        for extension in extensions:
                            try:
                                filepath = data["Nodes"][node_index]["Name"] + extension
                                graph(filepath, True, id, dot)
                                break
                            except FileNotFoundError:
                                if extension == ".yaml":
                                    print("Unable to find " + data["Nodes"][node_index]["Name"])
                                pass
            if "Precondition Nodes" in data["Nodes"][node_index]:
                for node in data["Nodes"][node_index]["Precondition Nodes"]:
                    iter_node(precondition_nodes[node], id, "Precondition", already_seen, precon=True)
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
                if "Resident Update Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["Resident Update Link"]:
                        iter_node(node["Node Index"], id, "Resident Update", already_seen)
                if "Output/bool Input/float Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["Output/bool Input/float Input Link"]:
                        iter_node(node["Node Index"], id, node["Parameter"], already_seen, precon=True)
                if "int Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
                    for node in data["Nodes"][node_index]["Linked Nodes"]["int Input Link"]:
                        iter_node(node["Node Index"], id, node["Parameter"], already_seen, precon=True)
                if "String Input Link" in data["Nodes"][node_index]["Linked Nodes"]:
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
            id = str(uuid.uuid4())
            dot.node(id, "Invalid Node\n")
            if origin_id != None: # Not sure this is even possible, but just in case
                if precon:
                    if ((id, origin_id, lbl)) not in edge_list:
                        dot.edge(id, origin_id, label=lbl)
                else:
                    if ((origin_id, id, lbl)) not in edge_list:
                        dot.edge(origin_id, id, label=lbl)
            return id

    if index == None:
        if "Nodes" in data:
            if data["Info"]["File Category"] != "Logic" and "Commands" in data:
                for command in data["Commands"]:
                    dot.attr('node', shape='diamond')
                    cmd_id = str(uuid.uuid4())
                    dot.node(cmd_id, json.dumps(command, indent=4)[1:-2] + "\n\n", color='blue')
                    if recurse and parent_id != None:
                        dot.edge(parent_id, cmd_id)
                    iter_node(command["Left Node Index"], cmd_id)
                    if command["Right Node Index"] >= 0:
                        iter_node(command["Right Node Index"], cmd_id)
            else:
                for node in data["Nodes"]:
                    node_id = iter_node(node["Node Index"])
                    if recurse and node["Node Index"] == 0 and parent_id != None:
                        dot.edge(parent_id, node_id)
        else:
            print("File has no nodes to graph: " + filepath)
    else:
        if "Nodes" in data:
            if index >= 0 and index < len(data["Nodes"]):
                iter_node(index)

    if parent_id == None:
        print("Rendering... (may take a while for recursive graphs)")
        dot.render(data["Info"]["Filename"], view=True)
        print("Finished")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if len(sys.argv) == 4:
            if sys.argv[3].lower() == "true":
                sys.argv[3] = True
            else:
                sys.argv[3] = False
            if os.path.isdir(sys.argv[2]):
                files = [i for i in os.listdir(sys.argv[2]) if os.path.splitext(i)[1] in [".ainb", ".json", ".yml", ".yaml"]]
                for file in files:
                    globals()[sys.argv[1]](os.path.join(sys.argv[2], file), sys.argv[3])
            else:
                globals()[sys.argv[1]](sys.argv[2], sys.argv[3])
        else:
            if os.path.isdir(sys.argv[2]):
                files = [i for i in os.listdir(sys.argv[2]) if os.path.splitext(i)[1] in [".ainb", ".json", ".yml", ".yaml"]]
                for file in files:
                    globals()[sys.argv[1]](os.path.join(sys.argv[2], file))
            else:
                globals()[sys.argv[1]](sys.argv[2])
    else:
        filepath = input("Enter filepath: ")
        recurse = input("Include graphs of embedded AINB files in graph (will increase rendering time) Y/N: ")
        if os.path.isdir(filepath):
            files = [i for i in os.listdir(filepath) if os.path.splitext(i)[1] in [".ainb", ".json", ".yml", ".yaml"]]
            for file in files:
                if recurse.lower() not in ["y", "yes"]:
                    graph(os.path.join(filepath, file))
                else:
                    graph(os.path.join(filepath, file), recurse=True)
        else:
            if recurse.lower() not in ["y", "yes"]:
                graph(filepath)
            else:
                graph(filepath, recurse=True)