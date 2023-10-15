# ainb

Collection of simple Python scripts to work with AINB files from recent Nintendo EPD games (only v4.7 is supported at the moment, v4.4 AINB from *Splatoon 3* or *Nintendo Switch Sports* are not fully compatible)

Commands to convert between AINB and JSON/YAML are found in converter.py

Basic graph creation command is in graph.py (outputs as .svg, requires Graphviz installation)

To use, clone the respository and use the commands in commands.py/graph.py - make sure to have Python 3 installed (not sure what the minimum version is, this was tested on 3.11.6)
For node graph generation, make sure to install Graphviz and the graphviz Python package

Reserialization is not byte-perfect and unused strings are removed, potentially leading to some string offsets being different from the original file - however, the game should still run without issue so editing the JSON/YAML then converting is OK

Still in testing so there may be bugs (let me know if there are any issues)