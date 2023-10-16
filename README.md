# ainb

Collection of simple Python scripts to work with AINB files from recent Nintendo EPD games (only v4.7 is supported at the moment, v4.4 AINB from *Splatoon 3* or *Nintendo Switch Sports* are not fully compatible)

Commands to convert between AINB and JSON/YAML are found in converter.py

Basic graph creation command is in graph.py (warning: graphs may be large)

## Usage
To use, clone the respository and use the commands in commands.py/graph.py - make sure to have Python 3 installed (not sure what the minimum version is, this was tested on 3.11.6)

For node graph generation, make sure to install [Graphviz](https://www.graphviz.org/download/) and the graphviz Python package

Arguments can be passed all as once as shown below or one-by-one via prompts

### Examples

```powershell
python converter.py ainb_to_json <path_to_ainb> # Converts provided AINB file to JSON

python graph.py graph <path_to_ainb> true # Creates recursive node graph of file and nested files 
```

### Dependencies
+ mmh3
+ PyYAML
+ graphviz (node graph generation only)
+ Graphviz (different from the Python package)

## File Format Overview

AINB (**AI** **N**ode **B**inary) is a binary file format used by ModulePack[1] games for various AI and logic purposes. AINB files contain a set of interconnected nodes which are run and updated by the game that control different aspects of the game from enemy AI to conditional spawning. Individual files may also contain "embedded" AINB files that are called by certain nodes. This leads to a complex system of node connections which can be difficult to keep track of mentally.

[1]: ModulePack is the unofficial name for the game engine used in recent Nintendo EPD games such as *Nintendo Switch Sports*, *Splatoon 3*, *The Legend of Zelda: Tears of the Kingdom*, and *Super Mario Bros. Wonder*

## Notes
Reserialization is not byte-perfect and unused strings are removed, potentially leading to some string offsets being different from the original file - however, the game should still run without issue so editing the JSON/YAML then converting is OK

Still in testing so there may be bugs (let me know if there are any issues)

Special thanks to Watertoon for their help reversing the format