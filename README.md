# ainb

Collection of simple Python scripts to work with AINB files from recent Nintendo EPD games (only v4.7 is supported at the moment, v4.4 AINB from *Splatoon 3* or *Nintendo Switch Sports* are not fully compatible)

Commands to convert between AINB and JSON/YAML are found in converter.py

Reserialization is not byte-perfect and unused strings are removed, potentially leading to some string offsets being different from the original file - however, the game should still run without issue so editing the JSON/YAML then converting is OK

Still in testing so there may be bugs (let me know if there are any issues)