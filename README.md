# AINB-Serializer
WIP Python commands to convert between AINB and JSON/YAML

Use the functions in converter.py to convert

Still in testing phase, there may be bugs

Does not guarantee the file will be valid and does not serialize byte-perfectly

Only AINB v4.7 is supported, will not work for AINB files from Splatoon 3 or Nintendo Switch Sports (v4.4)

Notes:
- There are some unused strings in certain AINB files that appear unreferenced by the file - those are removed when converted to JSON/YAML and back leading to certain string offsets differing between the original and converted files (if a necessary purpose is found for these strings, I can add them if needed)
- Other than the unused strings and shifted string offsets, it should be near byte-perfect reserialization of the file
- Our understanding of the format is still not 100% complete so there may need to be updates in the future