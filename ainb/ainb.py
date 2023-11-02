from exb import EXB
from utils import *
from enum import Enum
import json
try:
    import mmh3
except ImportError:
    raise ImportError("DID YOU EVEN TRY TO READ THE INSTRUCTIONS BEFORE YOU DID THIS? GO BACK TO THE GITHUB README AND LEARN TO READ :P")

# Enums and stuff
class Node_Type(Enum):
    UserDefined                    = 0
    Element_S32Selector            = 1
    Element_Sequential             = 2
    Element_Simultaneous           = 3
    Element_F32Selector            = 4
    Element_StringSelector         = 5
    Element_RandomSelector         = 6
    Element_BoolSelector           = 7
    Element_Fork                   = 8
    Element_Join                   = 9
    Element_Alert                  = 10
    Element_Expression             = 20
    Element_ModuleIF_Input_S32     = 100
    Element_ModuleIF_Input_F32     = 101
    Element_ModuleIF_Input_Vec3f   = 102
    Element_ModuleIF_Input_String  = 103
    Element_ModuleIF_Input_Bool    = 104
    Element_ModuleIF_Input_Ptr     = 105
    Element_ModuleIF_Output_S32    = 200
    Element_ModuleIF_Output_F32    = 201
    Element_ModuleIF_Output_Vec3f  = 202
    Element_ModuleIF_Output_String = 203
    Element_ModuleIF_Output_Bool   = 204
    Element_ModuleIF_Output_Ptr    = 205
    Element_ModuleIF_Child         = 300
    Element_StateEnd               = 400
    Element_SplitTiming            = 500

# User-Defined stores pointers to the corresponding structure/class
type_standard = ["int", "bool", "float", "string", "vec3f", "userdefined"] # Data type order

type_global = ["string", "int", "float", "bool", "vec3f", "userdefined"] # Data type order (global parameters)

file_category = {"AI" : 0, "Logic" : 1, "Sequence" : 2}

class AINB:
    def __init__(self, data, from_dict=False):
        self.max_global_index = 0
        self.output_dict = {}

        if not from_dict:
            self.stream = ReadStream(data)

            self.functions = {}
            self.exb_instances = 0 # Track total number of EXB function calls

            # Header (0x74 Bytes)
            self.magic = self.stream.read(4).decode('utf-8')
            if self.magic != "AIB ": # Must be .ainb file with correct magic
                raise Exception(f"Invalid magic {self.magic} - expected 'AIB '")
            self.version = self.stream.read_u32()
            if self.version not in [0x404, 0x407]: # Must be version 4.4 or 4.7 (4.4 isn't actually supported though)
                raise Exception(f"Invalid version {hex(self.version)} - expected 0x404 (S3/NSS) or 0x407 (TotK)")
            
            self._filename_offset = self.stream.read_u32()
            self.command_count = self.stream.read_u32()
            self.node_count = self.stream.read_u32()
            self.precondition_count = self.stream.read_u32()
            self.attachment_count = self.stream.read_u32()
            self.output_count = self.stream.read_u32()
            self.global_parameter_offset = self.stream.read_u32()
            self.string_offset = self.stream.read_u32()
            
            # Create string pool slice
            jumpback = self.stream.tell()
            self.stream.seek(self.string_offset)
            self.string_pool = ReadStream(self.stream.read())
            self.filename = self.string_pool.read_string(self._filename_offset)
            self.stream.seek(jumpback)

            self.resolve_offset = self.stream.read_u32() # v4.4 only - need to add support for v4.4-exclusive features
            self.immediate_offset = self.stream.read_u32()
            self.resident_update_offset = self.stream.read_u32()
            self.io_offset = self.stream.read_u32()
            self.multi_offset = self.stream.read_u32()
            self.attachment_offset = self.stream.read_u32()
            self.attachment_index_offset = self.stream.read_u32()
            self.exb_offset = self.stream.read_u32()
            self.child_replacement_offset = self.stream.read_u32() # Seemingly v4.7 exclusive
            self.precondition_offset = self.stream.read_u32()
            self.x50_section = self.stream.read_u32() # Seemingly unused, always equal to 0x30
            self.x54_value = self.stream.read_u32() # Seemingly unused, always 0
            self.x58_section = self.stream.read_u32() # v4.4 exclusive, purpose unknown
            self.embed_ainb_offset = self.stream.read_u32()
            self.file_category = self.string_pool.read_string(self.stream.read_u32())
            self.x64_value = self.stream.read_u32() # 0 = AI, 1 = Logic, 2 = Sequence (4.7), unused in v4.4
            self.entry_string_offset = self.stream.read_u32()
            self.x6c_section = self.stream.read_u32() # Seemingly unused
            self.file_hash_offset = self.stream.read_u32() # Hashed data is still a mystery, maybe CRC32 hash of file data?

            self.output_dict["Info"] = {
                "Magic" : self.magic, # Don't actually need to store this bc it's always the same
                "Version" : hex(self.version), # Don't actually need to store this
                "Filename" : self.filename,
                "File Category" : self.file_category
            }

            # Commands
            assert self.stream.tell() == 116, "Something went wrong" # Just to make sure we're at the right location
            self.commands = []
            for i in range(self.command_count):
                self.commands.append(self.Command())
            command_end = self.stream.tell()
            
            # We don't parse the nodes yet because they depend on the other sections

            # Global Parameters (copied most from here on down from old code so hopefully it works fine)
            self.stream.seek(self.global_parameter_offset)
            self.global_params = self.GlobalParameters()

            # EXB Section
            self.exb = {}
            if self.exb_offset != 0:
                self.stream.seek(self.exb_offset)
                exb_slice = self.stream.read()
                self.exb = EXB(exb_slice)

            # Immediate Parameters
            self.stream.seek(self.immediate_offset)
            self.immediate_offsets = self.ImmediateHeader()
            self.immediate_parameters = {}
            for i in range(len(self.immediate_offsets)):
                self.stream.seek(self.immediate_offsets[i])
                self.immediate_parameters[type_standard[i]] = []
                if i < 5: # Pointer parameters end at the start of the next section
                    while self.stream.tell() < self.immediate_offsets[i+1]:
                        self.immediate_parameters[type_standard[i]].append(self.ImmediateParameter(type_standard[i]))
                else:
                    while self.stream.tell() < self.io_offset:
                        self.immediate_parameters[type_standard[i]].append(self.ImmediateParameter(type_standard[i]))
            # Remove types with no entries
            self.immediate_parameters = {key : value for key, value in self.immediate_parameters.items() if value}

            # Attachment Parameters
            self.attachment_parameters = []
            if self.attachment_count > 0:
                self.stream.seek(self.attachment_offset)
                self.attachment_parameters = [self.AttachmentEntry()]
                while self.stream.tell() < self.attachment_parameters[0]["Offset"]:
                    self.attachment_parameters.append(self.AttachmentEntry())
                for param in self.attachment_parameters:
                    self.stream.seek(param["Offset"])
                    param["Parameters"] = self.AttachmentParameters()
                    del param["Offset"]
                    if not(param["Parameters"]):
                        del param["Parameters"]
                
                self.attachment_array = [] # This is the array nodes are referencing for attachments
                self.stream.seek(self.attachment_index_offset)
                while self.stream.tell() < self.attachment_offset:
                    self.attachment_array.append(self.stream.read_u32())

            # Input/Output Parameters
            self.stream.seek(self.io_offset)
            self.io_offsets = self.IOHeader()
            self.input_parameters = {}
            self.output_parameters = {}
            for i in range(6):
                self.input_parameters[type_standard[i]] = []
                self.output_parameters[type_standard[i]] = []
                while self.stream.tell() < self.io_offsets["Output"][i]:
                    self.input_parameters[type_standard[i]].append(self.InputEntry(type_standard[i]))
                if not(self.input_parameters[type_standard[i]]):
                    del self.input_parameters[type_standard[i]]
                if i < 5:
                    while self.stream.tell() < self.io_offsets["Input"][i+1]:
                        self.output_parameters[type_standard[i]].append(self.OutputEntry(type_standard[i]))
                else:
                    while self.stream.tell() < self.multi_offset:
                        self.output_parameters[type_standard[i]].append(self.OutputEntry(type_standard[i]))
                if not(self.output_parameters[type_standard[i]]):
                    del self.output_parameters[type_standard[i]]
            self.io_parameters = {"Input Parameters" : self.input_parameters, "Output Parameters" : self.output_parameters}

            # Multi-Parameters
            for type in self.input_parameters:
                for parameter in self.input_parameters[type]:
                    if "Multi Index" in parameter:
                        parameter["Sources"] = []
                        self.stream.seek(self.multi_offset + parameter["Multi Index"] * 8)
                        for i in range(parameter["Multi Count"]):
                            parameter["Sources"].append(self.MultiEntry())
                        del parameter["Multi Index"], parameter["Multi Count"]
                        
            # Resident Update Array
            self.stream.seek(self.resident_update_offset)
            self.resident_update_array = []
            if self.resident_update_offset != self.precondition_offset: # Section doesn't exist if they're equal
                offsets = [self.stream.read_u32()]
                while self.stream.tell() < offsets[0]:
                    offsets.append(self.stream.read_u32())
                for offset in offsets:
                    self.stream.seek(offset)
                    self.resident_update_array.append(self.ResidentEntry())

            # Precondition Nodes
            self.stream.seek(self.precondition_offset)
            self.precondition_nodes = []
            if self.exb_offset != 0:
                end = self.exb_offset
            else:
                end = self.embed_ainb_offset
            while self.stream.tell() < end:
                self.precondition_nodes.append(self.stream.read_u16())
                self.stream.read_u16() # Unsure of the purpose of these two bytes

            # Entry Strings
            self.stream.seek(self.entry_string_offset)
            count = self.stream.read_u32()
            self.entry_strings = []
            for i in range(count):
                self.entry_strings.append(self.EntryStringEntry())

            # Nodes - initialize all nodes and assign corresponding parameters
            self.stream.seek(command_end)
            self.nodes = []
            for i in range(self.node_count):
                self.nodes.append(self.Node())
            if self.nodes:
                # Match Entry Strings (purpose still unknown)
                for entry in self.entry_strings:
                    self.nodes[entry["Node Index"]]["Entry String"] = entry
                    del self.nodes[entry["Node Index"]]["Entry String"]["Node Index"]

            """
            Child Replacement
            These replacements/removals happen upon file initialization (mostly to remove debug nodes)
            We keep the data bc there's no way to recover the replacement table otherwise
            """
            self.stream.seek(self.child_replacement_offset)
            self.is_replaced = self.stream.read_u8() # Set at runtime, just ignore
            self.stream.skip(1)
            count = self.stream.read_u16()
            node_count = self.stream.read_s16() # = Node count - node removal count - 2 * replacement node count
            attachment_count = self.stream.read_s16() # = Attachment count - attachment removal coutn
            self.replacements = []
            for i in range(count):
                self.replacements.append(self.ChildReplace())
            if self.replacements:
                for replacement in self.replacements: # Don't actually replace the node, just leave a note
                    if replacement["Type"] == 0:
                        i = 0
                        for type in self.nodes[replacement["Node Index"]]["Linked Nodes"]:
                            for node in self.nodes[replacement["Node Index"]]["Linked Nodes"][type]:
                                i += 0
                                if i == replacement["Child Index"]:
                                    node["Is Removed at Runtime"] = True
                    if replacement["Type"] == 1:
                        i = 0
                        for type in self.nodes[replacement["Node Index"]]["Linked Nodes"]:
                            for node in self.nodes[replacement["Node Index"]]["Linked Nodes"][type]:
                                if i == replacement["Child Index"]:
                                    node["Replacement Node Index"] = replacement["Replacement Index"]
                                i += 1
                    if replacement["Type"] == 2:
                        self.nodes[replacement["Node Index"]]["Attachments"][replacement["Attachment Index"]]["Is Removed at Runtime"] = True

            # Embedded AINB
            self.stream.seek(self.embed_ainb_offset)
            count = self.stream.read_u32()
            self.ainb_array = []
            for i in range(count):
                entry = {}
                entry["File Path"] = self.string_pool.read_string(self.stream.read_u32())
                entry["File Category"] = self.string_pool.read_string(self.stream.read_u32())
                entry["Count"] = self.stream.read_u32()
                self.ainb_array.append(entry)

            # Resolve Array

            # File Hashes
            self.stream.seek(self.file_hash_offset)
            self.file_hashes = {"Unknown File Hash" : hex(self.stream.read_u32())}
            hash2 = self.stream.read_u32()
            if hash2:
                self.file_hashes["Unknown Parent File Hash"] = hex(hash2)

            # 0x6C Section (always 0 in TotK, presumably completely unused)

            # String Pool (no output, strings are matched already)

            # Deal with functions
            if self.exb:
                i = len(self.functions)
                self.exb.exb_section["Commands"] = [command for command in self.exb.exb_section["Commands"] if command not in list(self.functions.values())]
                for command in self.exb.exb_section["Commands"]:
                    self.functions[i] == command
                    i += 1
                if not self.exb.exb_section["Commands"]:
                    del self.exb.exb_section["Commands"]
            
        else:
            self.magic = data["Info"]["Magic"]
            self.version = int(data["Info"]["Version"], 16)
            self.filename = data["Info"]["Filename"]
            self.file_category = data["Info"]["File Category"]

            # Defaults
            self.commands, self.ainb_array, self.nodes = [], [], []
            self.global_params, self.exb, self.file_hashes = {}, {}, {}
            
            self.functions = {}
            self.exb_instances = 0

            # Get all EXB functions in file
            if "Nodes" in data:
                self.nodes = data["Nodes"]
                for node in self.nodes:
                    if "Immediate Parameters" in node:
                        for type in node["Immediate Parameters"]:
                            for entry in node["Immediate Parameters"][type]:
                                if "Function" in entry:
                                    self.functions[entry["EXB Index"]] = entry["Function"]
                                    self.exb_instances += 1
                                if "Sources" in entry:
                                    for parameter in entry["Sources"]:
                                        if "Function" in parameter:
                                            self.functions[parameter["EXB Index"]] = parameter["Function"]
                                            self.exb_instances += 1
                    if "Input Parameters" in node:
                        for type in node["Input Parameters"]:
                            for entry in node["Input Parameters"][type]:
                                if "Function" in entry:
                                    self.functions[entry["EXB Index"]] = entry["Function"]
                                    self.exb_instances += 1
                                if "Sources" in entry:
                                    for parameter in entry["Sources"]:
                                        if "Function" in parameter:
                                            self.functions[parameter["EXB Index"]] = parameter["Function"]
                                            self.exb_instances += 1
                    if "Attachments" in node:
                        if "Parameters" in node["Attachments"]:
                            for type in node["Attachments"]["Parameters"]:
                                for entry in node["Attachments"]["Parameters"][type]:
                                    if "Function" in entry:
                                        self.functions[entry["EXB Index"]] = entry["Function"]
                                        self.exb_instances += 1
                                    if "Sources" in entry:
                                        for parameter in entry["Sources"]:
                                            if "Function" in parameter:
                                                self.functions[parameter["EXB Index"]] = parameter["Function"]
                                                self.exb_instances += 1

            if "Commands" in data:
                self.commands = data["Commands"]
            if "Global Parameters" in data:
                self.global_params = data["Global Parameters"]
            if self.functions:
                self.exb = EXB(None, self.functions, from_dict)
                i = len(self.functions)
                self.exb.exb_section["Commands"] = [command for command in self.exb.exb_section["Commands"] if command not in list(self.functions.values())]
                for command in self.exb.exb_section["Commands"]:
                    self.functions[i] == command
                    i += 1
                if not self.exb.exb_section["Commands"]:
                    del self.exb.exb_section["Commands"]
            if "File Hashes" in data:
                self.file_hashes = data["File Hashes"]
            if "Embedded AINB Files" in data:
                self.ainb_array = data["Embedded AINB Files"]
        
        self.output_dict["Info"] = {
                "Magic" : self.magic,
                "Version" : hex(self.version),
                "Filename" : self.filename,
                "File Category" : self.file_category
            }
        if self.commands:
            self.output_dict["Commands"] = self.commands
        if self.global_params:
            self.output_dict["Global Parameters"] = self.global_params
        if self.ainb_array:
            self.output_dict["Embedded AINB Files"] = self.ainb_array
        if self.nodes:
            self.output_dict["Nodes"] = self.nodes
        self.output_dict["File Hashes"] = self.file_hashes

    # File Structs
    def GUID(self) -> str:
        return hex(self.stream.read_u32())[2:] + "-" + hex(self.stream.read_u16())[2:] + "-" + hex(self.stream.read_u16())[2:] \
            + "-" + hex(self.stream.read_u16())[2:] + "-" + self.stream.read(6).hex()
    
    def Command(self):
        command = {}
        command["Name"] = self.string_pool.read_string(self.stream.read_u32())
        command["GUID"] = self.GUID()
        command["Left Node Index"] = self.stream.read_u16()
        command["Right Node Index"] = self.stream.read_u16() - 1 # -1 is not a valid node index
        return command

    def GlobalHeaderEntry(self):
        entry = {}
        entry["Count"] = self.stream.read_u16()
        entry["Index"] = self.stream.read_u16()
        entry["Offset"] = self.stream.read_u16()
        self.stream.read_u16() # Unsure of the purpose of these two bytes
        return entry

    def GlobalEntry(self):
        entry = {}
        bitfield = self.stream.read_u32()
        valid_index = bool(bitfield >> 31)
        if valid_index:
            entry["Index"] = (bitfield >> 24) & 0b1111111
            if entry["Index"] > self.max_global_index:
                self.max_global_index = entry["Index"]
        name_offset = bitfield & 0x3FFFFF
        entry["Name"] = self.string_pool.read_string(name_offset)
        entry["Notes"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def GlobalValue(self, type):
        if type == "int":
            value = self.stream.read_u32()
        if type == "bool":
            value = bool(self.stream.read_u8())
        if type == "float":
            value = self.stream.read_f32()
        if type == "string":
            value = self.string_pool.read_string(self.stream.read_u32())
        if type == "vec3f":
            value = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
        if type == "userdefined":
            value = None # Default values are not stored
        return value

    def GlobalFileRef(self):
        entry = {}
        entry["Filename"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Name Hash"] = hex(self.stream.read_u32())
        del entry["Name Hash"]
        entry["Unknown Hash 1"] = hex(self.stream.read_u32())
        entry["Unknown Hash 2"] = hex(self.stream.read_u32())
        return entry

    def GlobalParameters(self):
        self.global_header = {}
        for type in type_global:
            self.global_header[type] = self.GlobalHeaderEntry()
        self.global_parameters = {}
        for type in self.global_header:
            parameters = []
            for i in range(self.global_header[type]["Count"]):
                entry = self.GlobalEntry()
                parameters.append(entry)
            self.global_parameters[type] = parameters
        pos = self.stream.tell()
        for type in self.global_parameters:
            self.stream.seek(pos + self.global_header[type]["Offset"])
            for entry in self.global_parameters[type]:
                entry["Default Value"] = self.GlobalValue(type)
        self.global_references = []
        for i in range(self.max_global_index + 1):
            self.global_references.append(self.GlobalFileRef())
        for type in self.global_parameters: # Match file references to parameters
            for entry in self.global_parameters[type]:
                if "Index" in entry:
                    entry["File Reference"] = self.global_references[entry["Index"]]
                    del entry["Index"]
        self.global_parameters = {key : value for key, value in self.global_parameters.items() if value} # Remove types with no entries
        return self.global_parameters
    
    def ImmediateHeader(self):
        offsets = []
        for  i in range(6):
            offsets.append(self.stream.read_u32())
        return offsets

    def ImmediateParameter(self, type):
        entry = {}
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "userdefined":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x100:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            if (flags & 0xc200) == 0xc200:
                entry["EXB Index"] = index
                entry["Function"] = self.exb.commands[entry["EXB Index"]]
                self.functions[entry["EXB Index"]] = entry["Function"]
            elif flags & 0x8000:
                entry["Global Parameters Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        # User-Defined types don't have values stored
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_u32()
        if type == "float":
            entry["Value"] = self.stream.read_f32()
        if type == "bool":
            entry["Value"] = bool(self.stream.read_u32())
        if type == "vec3f":
            entry["Value"] = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
        return entry
    
    def AttachmentEntry(self):
        entry = {}
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Offset"] = self.stream.read_u32()
        entry["EXB Function Count"] = self.stream.read_u16()
        entry["EXB Input/Output Size"] = self.stream.read_u16()
        entry["Name Hash"] = hex(self.stream.read_u32())
        del entry["Name Hash"], entry["EXB Function Count"], entry["EXB Input/Output Size"]
        return entry
    
    def AttachmentParameters(self):
        self.stream.skip(4)
        parameters = {}
        for i in range(6):
            parameters[type_standard[i]] = []
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            for j in range(count):
                parameters[type_standard[i]].append(self.immediate_parameters[type_standard[i]][index + j])
            if count == 0:
                del parameters[type_standard[i]]
        self.stream.skip(48)
        return parameters
    
    def IOHeader(self):
        offsets = {"Input" : [], "Output" : []}
        for i in range(12):
            if i % 2 == 0:
                offsets["Input"].append(self.stream.read_u32())
            else:
                offsets["Output"].append(self.stream.read_u32())
        return offsets
    
    def InputEntry(self, type):
        entry = {}
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "userdefined":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Node Index"] = self.stream.read_s16()
        entry["Parameter Index"] = self.stream.read_s16()
        if entry["Node Index"] <= -100 and entry["Node Index"] >= -8192:
            entry["Multi Index"] = -100 - entry["Node Index"]
            entry["Multi Count"] = entry["Parameter Index"]
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x100:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            if (flags & 0xc200) == 0xc200:
                entry["EXB Index"] = index
                entry["Function"] = self.exb.commands[entry["EXB Index"]]
                self.functions[entry["EXB Index"]] = entry["Function"]
            elif flags & 0x8000:
                entry["Global Parameters Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_u32()
        if type == "float":
            entry["Value"] = self.stream.read_f32()
        if type == "bool":
            entry["Value"] = bool(self.stream.read_u32())
        if type == "vec3f":
            entry["Value"] = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
        if type == "userdefined":
            entry["Value"] = self.stream.read_u32()
        return entry
    
    def OutputEntry(self, type):
        entry = {}
        flags = self.stream.read_u32()
        entry["Name"] = self.string_pool.read_string(flags & 0x3FFFFFFF)
        flag = flags & 0x80000000
        if flag:
            entry["Set Pointer Flag Bit Zero"] = True
        if type == "userdefined":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def MultiEntry(self):
        entry = {}
        entry["Node Index"] = self.stream.read_u16()
        entry["Parameter Index"] = self.stream.read_u16()
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x100:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            if (flags & 0xc200) == 0xc200:
                entry["EXB Index"] = index
                entry["Function"] = self.exb.commands[entry["EXB Index"]]
                self.functions[entry["EXB Index"]] = entry["Function"]
            elif flags & 0x8000:
                entry["Global Parameters Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        return entry
    
    def ResidentEntry(self):
        entry = {}
        flags = self.stream.read_u32()
        entry["Flags"] = []
        if flags >> 31:
            entry["Flags"].append("Update Post Current Command Calc")
        if flags & 1:
            entry["Flags"].append("Is Valid Update")
        if "Is Valid Update" not in entry["Flags"]:
            entry["String"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def EntryStringEntry(self):
        entry = {}
        entry["Node Index"] = self.stream.read_u32()
        main_state = self.string_pool.read_string(self.stream.read_u32())
        state = self.string_pool.read_string(self.stream.read_u32())
        entry[main_state] = state
        return entry
    
    def Node(self):
        entry = {}
        exb_count = 0
        entry["Node Type"] = Node_Type(self.stream.read_u16()).name
        entry["Node Index"] = self.stream.read_u16()
        entry["Attachment Count"] = self.stream.read_u16()
        flags = self.stream.read_u8()
        if flags:
            entry["Flags"] = []
            if flags & 0b1:
                entry["Flags"].append("Is Precondition Node")
            if flags & 0b10:
                entry["Flags"].append("Is External AINB")
            if flags & 0b100:
                entry["Flags"].append("Is Resident Node")
        self.stream.read_u8()
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Name Hash"] = hex(self.stream.read_u32())
        self.stream.read_u32()
        entry["Parameters Offset"] = self.stream.read_u32()
        entry["EXB Function Count"] = self.stream.read_u16()
        entry["EXB Input/Output Size"] = self.stream.read_u16()
        del entry["EXB Function Count"], entry["EXB Input/Output Size"]
        entry["Multi-Param Count"] = self.stream.read_u16() # Unnecessary as node parameters will already be paired
        self.stream.read_u16()
        entry["Base Attachment Index"] = self.stream.read_u32()
        entry["Base Precondition Node"] = self.stream.read_u16()
        entry["Precondition Count"] = self.stream.read_u16()
        self.stream.read_u32()
        entry["GUID"] = self.GUID()
        if entry["Precondition Count"] > 0:
            entry["Precondition Nodes"] = []
            for i in range(entry["Precondition Count"]):
                entry["Precondition Nodes"].append(self.precondition_nodes[entry["Base Precondition Node"] + i])
        # This is all to get the function count and I know it could be way more efficient but it's late and I can't think
        if entry["Attachment Count"] > 0:
            entry["Attachments"] = []
            for i in range(entry["Attachment Count"]):
                entry["Attachments"].append(self.attachment_parameters[self.attachment_array[entry["Base Attachment Index"] + i]])
            for attachment in entry["Attachments"]:
                if "Parameters" in attachment:
                    for type in attachment["Parameters"]:
                        for entry1 in type:
                            if "Function" in entry1:
                                exb_count += 1
                            if "Sources" in entry1:
                                for parameter in entry1["Sources"]:
                                    if "Function" in parameter:
                                        exb_count += 1
        # We don't need these anymore actually
        del entry["Attachment Count"], entry["Base Attachment Index"], entry["Multi-Param Count"], entry["Precondition Count"], entry["Name Hash"]
        jumpback = self.stream.tell()
        # Match Node Parameters
        self.stream.seek(entry["Parameters Offset"])
        del entry["Parameters Offset"]
        immediate_parameters = {}
        for i in range(6):
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            immediate_parameters[type_standard[i]] = []
            for j in range(count):
                immediate_parameters[type_standard[i]].append(self.immediate_parameters[type_standard[i]][index + j])
                # Unsure if these can even have EXB functions
                if "Function" in self.immediate_parameters[type_standard[i]][index + j]:
                    exb_count += 1
                if "Sources" in self.immediate_parameters[type_standard[i]][index + j]:
                    for parameter in self.immediate_parameters[type_standard[i]][index + j]["Sources"]:
                        if "Function" in parameter:
                            exb_count += 1
            if not(immediate_parameters[type_standard[i]]):
                del immediate_parameters[type_standard[i]]
        if immediate_parameters:
            entry["Immediate Parameters"] = immediate_parameters
        input_parameters = {}
        output_parameters = {}
        for i in range(6):
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            input_parameters[type_standard[i]] = []
            for j in range(count):
                input_parameters[type_standard[i]].append(self.input_parameters[type_standard[i]][index + j])
                if "Function" in self.input_parameters[type_standard[i]][index + j]:
                    exb_count += 1
                if "Sources" in self.input_parameters[type_standard[i]][index + j]:
                    for parameter in self.input_parameters[type_standard[i]][index + j]["Sources"]:
                        if "Function" in parameter:
                            exb_count += 1
            if not(input_parameters[type_standard[i]]):
                del input_parameters[type_standard[i]]
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            output_parameters[type_standard[i]] = []
            for j in range(count):
                output_parameters[type_standard[i]].append(self.output_parameters[type_standard[i]][index + j])
            if not(output_parameters[type_standard[i]]):
                del output_parameters[type_standard[i]]
        if input_parameters:
            entry["Input Parameters"] = input_parameters
        if output_parameters:
            entry["Output Parameters"] = output_parameters
        self.exb_instances += exb_count
        # Child Nodes
        counts = []
        indices = []
        for i in range(10):
            counts.append(self.stream.read_u8())
            indices.append(self.stream.read_u8())
        start = self.stream.tell()
        if sum(counts) != 0:
            entry["Linked Nodes"] = {}
            mapping = {0 : "Output/bool Input/float Input Link",
                       1 : None, # Unused in TotK
                       2 : "Standard Link",
                       3 : "Resident Update Link",
                       4 : "String Input Link",
                       5 : "int Input Link",
                       6 : None, 7 : None, 8 : None, 9 : None} # Unused in TotK
            for i in range(10):
                entry["Linked Nodes"][mapping[i]] = []
                self.stream.seek(start + indices[i] * 4)
                offsets = []
                for j in range(counts[i]):
                    offsets.append(self.stream.read_u32())
                for offset in offsets:
                    self.stream.seek(offset)
                    info = {}
                    info["Node Index"] = self.stream.read_u32()
                    if i in [0, 4, 5]:
                        info["Parameter"] = self.string_pool.read_string(self.stream.read_u32())
                    if i == 2:
                        ref = self.string_pool.read_string(self.stream.read_u32())
                        if ref != '':
                            if entry["Node Type"] == "Element_BoolSelector":
                                info["Condition"] = ref
                            else:
                                info["Connection Name"] = ref
                        else:
                            is_end = bool(offsets.index(offset) == len(offsets) - 1)
                            if entry["Node Type"] == "Element_S32Selector":
                                index = self.stream.read_s16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Global Parameters Index"] = index
                                if is_end:
                                    info["Condition"] = "Default"
                                else:
                                    info["Condition"] = self.stream.read_s32()
                            elif entry["Node Type"] == "Element_F32Selector":
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Global Parameters Index"] = index
                                if not(is_end):
                                    info["Condition Min"] = self.stream.read_f32()
                                    self.stream.read_u32()
                                    info["Condition Max"] = self.stream.read_f32()
                                else:
                                    info[self.string_pool.read_string(self.stream.read_u32())] = "Default"
                            elif entry["Node Type"] == "Element_StringSelector":
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Global Parameters Index"] = index
                                if is_end:
                                    info[self.string_pool.read_string(self.stream.read_u32())] = "Default"
                                else:
                                    info["Condition"] = self.string_pool.read_string(self.stream.read_u32())
                            elif entry["Node Type"] == "Element_RandomSelector":
                                info["Probability"] = self.stream.read_f32()
                            else:
                                info["Connection Name"] = ref
                    if i == 3:
                        update_index = self.stream.read_u32()
                        info["Update Info"] = self.resident_update_array[update_index]
                    entry["Linked Nodes"][mapping[i]].append(info)
                if not(entry["Linked Nodes"][mapping[i]]):
                    del entry["Linked Nodes"][mapping[i]]
        self.stream.seek(jumpback)
        return entry
    
    def ChildReplace(self):
        entry = {}
        entry["Type"] = self.stream.read_u8()
        self.stream.read_u8()
        entry["Node Index"] = self.stream.read_u16()
        if entry["Type"] in [0, 1]:
            entry["Child Index"] = self.stream.read_u16()
            if entry["Type"] == 1:
                entry["Replacement Index"] = self.stream.read_u16()
            else:
                self.stream.read_u16()
        if entry["Type"] == 2:
            entry["Attachment Index"] = self.stream.read_u16()
            self.stream.read_u16()
        return entry

    def ToBytes(self, ainb, dest): # ainb is an AINB object
        buffer = WriteStream(dest)

        # Header (Round 1)
        buffer.write(b'AIB ') # Magic
        buffer.write(b'\x07\x04\x00\x00')
        buffer.add_string(self.filename)
        buffer.write(u32(buffer._string_refs[self.filename]))
        buffer.write(u32(len(self.commands)))
        buffer.write(u32(len(self.nodes)))
        buffer.write(u32(len([precon for precon in [node for node in self.nodes if "Flags" in node] if "Is Precondition Node" in precon["Flags"]])))
        buffer.write(u32(0)) # Skip for now
        buffer.write(u32(len([node for node in self.nodes if "Output" in node["Node Type"]])))
        buffer.write(u32(116 + 24 * len(self.commands) + 60 * len(self.nodes)))
        for i in range(11):
            buffer.write(u32(4)) # Skip writing offsets until they're known
        buffer.write(u64(0)) # Skip 8
        buffer.write(u32(0)) # Used in S3/NSS so will have to change if support for those is added
        buffer.write(u32(0)) # Skip writing offset until it's known
        buffer.add_string(self.file_category)
        buffer.write(u32(buffer._string_refs[self.file_category]))
        buffer.write(u32(file_category[self.file_category]))
        buffer.write(u64(0)) # SKip writing offsets until they're known
        buffer.write(u32(0))

        # Commands
        if self.commands:
            for command in self.commands:
                buffer.add_string(command["Name"])
                buffer.write(u32(buffer._string_refs[command["Name"]]))
                # Scuffed but works
                parts = command["GUID"].split('-')
                parts = [int(i, 16) for i in parts]
                buffer.write(u32(parts[0]))
                buffer.write(u16(parts[1]))
                buffer.write(u16(parts[2]))
                buffer.write(u16(parts[3]))
                parts[4] = hex(parts[4])[2:]
                while len(parts[4]) < 12:
                    parts[4] = "0" + parts[4]
                buffer.write(byte_custom(bytes.fromhex(parts[4]), 6))
                buffer.write(u16(command["Left Node Index"]))
                buffer.write(u16(command["Right Node Index"] + 1))

        immediate_parameters = dict(zip(type_standard, [[], [], [], [], [], []]))
        input_parameters = dict(zip(type_standard, [[], [], [], [], [], []]))
        output_parameters = dict(zip(type_standard, [[], [], [], [], [], []]))            
        attachments = []
        attachment_indices = []
        multis = []
        precondition_nodes = {}
        entry_strings = []
        replacements = []
        multi_counts = {}
        attach_counts = {}
        precon_counts = {}
        exb_info = []
        attach_exb_info = []

        # Nodes
        if self.nodes:
            for node in self.nodes:
                exb_count = 0
                exb_size = 0
                buffer.add_string(node["Name"])
                if "Attachments" in node:
                    i = 0
                    for attachment in node["Attachments"]:
                        attach_exb_count = 0
                        attach_exb_size = 0
                        if "Parameters" in attachment:
                            for type in attachment["Parameters"]:
                                for entry in type:
                                    if "Function" in entry:
                                        exb_count += 1
                                        attach_exb_count += 1
                                        size = 0
                                        for instruction in entry["Function"]["Instructions"]:
                                            if "Data Type" in instruction:
                                                if instruction["Data Type"] == "vec3f":
                                                    type_size = 12
                                                else:
                                                    type_size = 4
                                            if "LHS Source" in instruction or "RHS Source" in instruction:
                                                if instruction["LHS Source"] == "Output":
                                                    size = max(size, instruction["LHS Index/Value"] + type_size)
                                                if instruction["RHS Source"] == "Input":
                                                    size = max(size, instruction["RHS Index/Value"] + type_size)
                                        exb_size += size
                                        attach_exb_size += size
                                    if "Sources" in entry:
                                        for parameter in entry["Sources"]:
                                            exb_count += 1
                                            attach_exb_count += 1
                                            size = 0
                                            for instruction in parameter["Function"]["Instructions"]:
                                                if "Data Type" in instruction:
                                                    if instruction["Data Type"] == "vec3f":
                                                        type_size = 12
                                                    else:
                                                        type_size = 4
                                                if "LHS Source" in instruction or "RHS Source" in instruction:
                                                    if instruction["LHS Source"] == "Output":
                                                        size = max(size, instruction["LHS Index/Value"] + type_size)
                                                    if instruction["RHS Source"] == "Input":
                                                        size = max(size, instruction["RHS Index/Value"] + type_size)
                                            exb_size += size
                                            attach_exb_size += size
                        if attachment not in attachments:
                            if attach_exb_count or attach_exb_size:
                                attach_exb_info.append((attach_exb_count, attach_exb_size))
                            else:
                                attach_exb_info.append((0, 0))
                            attachments.append(attachment)
                        if "Is Removed at Runtime" in attachment:
                            replacements.append((2, node["Node Index"], i))
                        i += 1
                    for attachment in node["Attachments"]:
                        attachment_indices.append(attachments.index(attachment))
                    attach_counts[node["Node Index"]] = len(node["Attachments"])
                else:
                    attach_counts[node["Node Index"]] = 0
                if "Immediate Parameters" in node:
                    for type in node["Immediate Parameters"]:
                        for entry in node["Immediate Parameters"][type]:
                            if "Function" in entry:
                                exb_count += 1
                                size = 0
                                for instruction in entry["Function"]["Instructions"]:
                                    if "Data Type" in instruction:
                                        if instruction["Data Type"] == "vec3f":
                                            type_size = 12
                                        else:
                                            type_size = 4
                                    if "LHS Source" in instruction or "RHS Source" in instruction:
                                        if instruction["LHS Source"] == "Output":
                                            size = max(size, instruction["LHS Index/Value"] + type_size)
                                        if instruction["RHS Source"] == "Input":
                                            size = max(size, instruction["RHS Index/Value"] + type_size)
                                exb_size += size
                            if "Sources" in entry:
                                for parameter in entry["Sources"]:
                                    multis.append(parameter)
                                    if "Function" in parameter:
                                        exb_count += 1
                                        size = 0
                                        for instruction in parameter["Function"]["Instructions"]:
                                            if "Data Type" in instruction:
                                                if instruction["Data Type"] == "vec3f":
                                                    type_size = 12
                                                else:
                                                    type_size = 4
                                            if "LHS Source" in instruction or "RHS Source" in instruction:
                                                if instruction["LHS Source"] == "Output":
                                                    size = max(size, instruction["LHS Index/Value"] + type_size)
                                                if instruction["RHS Source"] == "Input":
                                                    size = max(size, instruction["RHS Index/Value"] + type_size)
                                        exb_size += size
                                if node["Node Index"] in multi_counts:
                                    multi_counts[node["Node Index"]] += len(entry["Sources"])
                                else:
                                    multi_counts[node["Node Index"]] = len(entry["Sources"])
                if "Input Parameters" in node:
                    for type in node["Input Parameters"]:
                        for entry in node["Input Parameters"][type]:
                            if "Function" in entry:
                                exb_count += 1
                                size = 0
                                for instruction in entry["Function"]["Instructions"]:
                                    if "Data Type" in instruction:
                                        if instruction["Data Type"] == "vec3f":
                                            type_size = 12
                                        else:
                                            type_size = 4
                                    if "LHS Source" in instruction or "RHS Source" in instruction:
                                        if instruction["LHS Source"] == "Output":
                                            size = max(size, instruction["LHS Index/Value"] + type_size)
                                        if instruction["RHS Source"] == "Input":
                                            size = max(size, instruction["RHS Index/Value"] + type_size)
                                exb_size += size
                            if "Sources" in entry:
                                for parameter in entry["Sources"]:
                                    multis.append(parameter)
                                    if "Function" in parameter:
                                        exb_count += 1
                                        size = 0
                                        for instruction in parameter["Function"]["Instructions"]:
                                            if "Data Type" in instruction:
                                                if instruction["Data Type"] == "vec3f":
                                                    type_size = 12
                                                else:
                                                    type_size = 4
                                            if "LHS Source" in instruction or "RHS Source" in instruction:
                                                if instruction["LHS Source"] == "Output":
                                                    size = max(size, instruction["LHS Index/Value"] + type_size)
                                                if instruction["RHS Source"] == "Input":
                                                    size = max(size, instruction["RHS Index/Value"] + type_size)
                                        exb_size += size
                                if node["Node Index"] in multi_counts:
                                    multi_counts[node["Node Index"]] += len(entry["Sources"])
                                else:
                                    multi_counts[node["Node Index"]] = len(entry["Sources"])
                if node["Node Index"] not in multi_counts:
                    multi_counts[node["Node Index"]] = 0
                if "Precondition Nodes" in node:
                    for i in range(len(node["Precondition Nodes"])):
                        precondition_nodes.update({node["Base Precondition Node"] + i : node["Precondition Nodes"][i]})
                    precon_counts[node["Node Index"]] = len(node["Precondition Nodes"])
                else:
                    precon_counts[node["Node Index"]] = 0
                if "Entry String" in node:
                    entry_strings.append((node["Node Index"], node["Entry String"]))
                exb_info.append((exb_count, exb_size))
        buffer.skip(len(self.nodes) * 60)

        # Global Parameters
        if self.global_params:
            index = 0
            pos = 0
            for type in type_global:
                if type in self.global_params:
                    buffer.write(u16(len(self.global_params[type])))
                else:
                    buffer.write(u16(0))
                buffer.write(u16(index))
                if type in self.global_params:
                    index += len(self.global_params[type])
                if type == "vec3f" and "vec3f" in self.global_params:
                    buffer.write(u16(pos))
                    pos = pos + len(self.global_params[type]) * 12
                elif type in self.global_params:
                    buffer.write(u16(pos))
                    pos = pos + len(self.global_params[type]) * 4
                else:
                    buffer.write(u16(pos))
                buffer.write(u16(0))
            files = []
            for type in self.global_params:
                for entry in self.global_params[type]:
                    buffer.add_string(entry["Name"])
                    name_offset = buffer._string_refs[entry["Name"]]
                    if "File Reference" in entry:
                        if entry["File Reference"] not in files:
                            files.append(entry["File Reference"])
                        name_offset = name_offset | (1 << 31)
                        name_offset = name_offset | (files.index(entry["File Reference"]) << 24)
                    else:
                        name_offset = name_offset | (1 << 23)
                    buffer.write(u32(name_offset))
                    buffer.add_string(entry["Notes"])
                    buffer.write(u32(buffer._string_refs[entry["Notes"]]))
            start = buffer.tell()
            size = 0
            for type in self.global_params:
                for entry in self.global_params[type]:
                    if type == "int":
                        buffer.write(u32(entry["Default Value"]))
                        size += 4
                    if type == "float":
                        buffer.write(f32(entry["Default Value"]))
                        size += 4
                    if type == "bool":
                        buffer.write(u8(int(entry["Default Value"])))
                        size += 4
                    if type == "vec3f":
                        buffer.write(f32(entry["Default Value"][0]))
                        buffer.write(f32(entry["Default Value"][1]))
                        buffer.write(f32(entry["Default Value"][2]))
                        size += 12
                    if type == "string":
                        buffer.add_string(entry["Default Value"])
                        buffer.write(u32(buffer._string_refs[entry["Default Value"]]))
                        size += 4
            buffer.seek(start + size)
            for file in files:
                buffer.add_string(file["Filename"])
                buffer.write(u32(buffer._string_refs[file["Filename"]]))
                buffer.write(u32(mmh3.hash(file["Filename"], signed=False)))
                buffer.write(u32(int(file["Unknown Hash 1"][2:], 16)))
                buffer.write(u32(int(file["Unknown Hash 2"][2:], 16)))        
        else:
            buffer.skip(48)

        immediate_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0]))
        input_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0]))
        output_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0])) 

        residents = []
        bodies = []
        if self.nodes:
            for node in self.nodes:
                bodies.append(buffer.tell())
                if "Immediate Parameters" in node:
                    for type in type_standard:
                        if type in node["Immediate Parameters"]:
                            for entry in node["Immediate Parameters"][type]:
                                immediate_parameters[type].append(entry)
                            buffer.write(u32(len(immediate_parameters[type]) - len(node["Immediate Parameters"][type])))
                            buffer.write(u32(len(node["Immediate Parameters"][type])))
                            immediate_current[type] = len(immediate_parameters[type])
                        else:
                            buffer.write(u32(immediate_current[type]))
                            buffer.write(u32(0))
                else:
                    for type in type_standard:
                        buffer.write(u32(immediate_current[type]))
                        buffer.write(u32(0))
                for type in type_standard:
                    if "Input Parameters" in node:
                        if type in node["Input Parameters"]:
                            for entry in node["Input Parameters"][type]:
                                input_parameters[type].append(entry)
                            buffer.write(u32(len(input_parameters[type]) - len(node["Input Parameters"][type])))
                            buffer.write(u32(len(node["Input Parameters"][type])))
                            input_current[type] = len(input_parameters[type])
                        else:
                            buffer.write(u32(input_current[type]))
                            buffer.write(u32(0))
                    else:
                        buffer.write(u32(input_current[type]))
                        buffer.write(u32(0))
                    if "Output Parameters" in node:
                        if type in node["Output Parameters"]:
                            for entry in node["Output Parameters"][type]:
                                output_parameters[type].append(entry)
                            buffer.write(u32(len(output_parameters[type]) - len(node["Output Parameters"][type])))
                            buffer.write(u32(len(node["Output Parameters"][type])))
                            output_current[type] = len(output_parameters[type])
                        else:
                            buffer.write(u32(output_current[type]))
                            buffer.write(u32(0))
                    else:
                        buffer.write(u32(output_current[type]))
                        buffer.write(u32(0))
                if "Linked Nodes" in node:
                    total = 0
                    for connection in ["Output/bool Input/float Input Link", 2, "Standard Link",
                                            "Resident Update Link", "String Input Link", "int Input Link",
                                            7, 8, 9, 10]:
                        if connection in node["Linked Nodes"]:
                            buffer.write(u8(len(node["Linked Nodes"][connection])))
                            buffer.write(u8(total))
                            total += len(node["Linked Nodes"][connection])
                        else:
                            buffer.write(u8(0))
                            buffer.write(u8(total))
                    start = buffer.tell()
                    current = start + total * 4
                    i = 0
                    for connection in node["Linked Nodes"]:
                        if connection == "Output/bool Input/float Input Link":
                            for entry in node["Linked Nodes"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                buffer.add_string(entry["Parameter"])
                                buffer.write(u32(buffer._string_refs[entry["Parameter"]]))
                                buffer.seek(pos)
                                is_input = False
                                if "Selector" in node["Node Type"] or node["Node Type"] == "Element_Expression":
                                    if "Input Parameters" in node:
                                        for type in node["Input Parameters"]:
                                            for parameter in node["Input Parameters"][type]:
                                                if entry["Node Index"] == parameter["Node Index"]:
                                                    is_input = True
                                if is_input:
                                    current += 16
                                elif node["Node Type"] == "Element_Expression" and "Output Parameters" in node:
                                    if "vec3f" in node["Output Parameters"]:
                                        for parameter in node["Output Parameters"]["vec3f"]:
                                            if entry["Parameter"] == parameter["Name"]:
                                                current += 24
                                else:
                                    current += 8
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
                        elif connection == "Standard Link":
                            for entry in node["Linked Nodes"][connection]:
                                if node["Node Type"] == "Element_F32Selector":
                                    buffer.write(u32(current))
                                    pos = buffer.tell()
                                    buffer.seek(current)
                                    buffer.write(u32(entry["Node Index"]))
                                    buffer.add_string("")
                                    buffer.write(u32(buffer._string_refs[""]))
                                    if "Input" in entry:
                                        buffer.write(u32(self.global_params["float"].index(entry["Input"]) | (1 << 31)))
                                    else:
                                        buffer.write(u32(0))
                                    if "その他" in entry:
                                        buffer.add_string("その他")
                                        buffer.write(u32(buffer._string_refs["その他"]))
                                    else:
                                        buffer.write(f32(entry["Condition Min"]))
                                    buffer.write(u32(0))
                                    if "Condition Max" in entry:
                                        buffer.write(f32(entry["Condition Max"]))
                                    else:
                                        buffer.write(u32(0))
                                    buffer.seek(pos)
                                    current += 40
                                elif node["Node Type"] in ["Element_StringSelector", "Element_S32Selector", "Element_RandomSelector"]:
                                    buffer.write(u32(current))
                                    pos = buffer.tell()
                                    buffer.seek(current)
                                    buffer.write(u32(entry["Node Index"]))
                                    buffer.add_string("")
                                    buffer.write(u32(buffer._string_refs[""]))
                                    if "Input" in entry:
                                        if node["Node Type"] == "Element_StringSelector":
                                            buffer.write(u32(self.global_params["string"].index(entry["Input"]) | (1 << 31)))
                                        elif node["Node Type"] == "Element_S32Selector":
                                            buffer.write(u32(self.global_params["int"].index(entry["Input"]) | (1 << 31)))
                                        elif node["Node Type"] == "Element_RandomSelector":
                                            buffer.write(u32(self.global_params["float"].index(entry["Input"]) | (1 << 31)))
                                    else:
                                        buffer.write(u32(0))
                                    if "Probability" in entry:
                                        buffer.write(f32(entry["Probability"]))
                                    elif "Condition" in entry:
                                        if entry["Condition"] != "Default":
                                            if node["Node Type"] == "Element_S32Selector":
                                                buffer.write(s32(entry["Condition"]))
                                            else:
                                                buffer.add_string(entry["Condition"])
                                                buffer.write(u32(buffer._string_refs[entry["Condition"]]))
                                        else:
                                            buffer.write(u32(0))
                                    elif "その他" in entry:
                                        buffer.add_string("その他")
                                        buffer.write(u32(buffer._string_refs["その他"]))
                                    buffer.seek(pos)
                                    current += 16
                                else:
                                    buffer.write(u32(current))
                                    pos = buffer.tell()
                                    buffer.seek(current)
                                    buffer.write(u32(entry["Node Index"]))
                                    if "Connection Name" in entry:
                                        buffer.add_string(entry["Connection Name"])
                                        buffer.write(u32(buffer._string_refs[entry["Connection Name"]]))
                                    elif "Condition" in entry:
                                        buffer.add_string(entry["Condition"])
                                        buffer.write(u32(buffer._string_refs[entry["Condition"]]))
                                    buffer.seek(pos)
                                    current += 8
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
                        elif connection != "Resident Update Link":
                            for entry in node["Linked Nodes"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                if "Condition" in entry:
                                    buffer.add_string(entry["Condition"])
                                    buffer.write(u32(buffer._string_refs[entry["Condition"]]))
                                elif "Parameter" in entry:
                                    buffer.add_string(entry["Parameter"])
                                    buffer.write(u32(buffer._string_refs[entry["Parameter"]]))
                                else:
                                    buffer.add_string(entry["Connection Name"])
                                    buffer.write(u32(buffer._string_refs[entry["Connection Name"]]))
                                if "Input" in entry:
                                    if node["Node Type"] == "Element_StringSelector":
                                        buffer.write(u32(self.global_params["string"].index(entry["Input"]) | (1 << 31)))
                                    elif node["Node Type"] == "Element_S32Selector":
                                        buffer.write(u32(self.global_params["int"].index(entry["Input"]) | (1 << 31)))
                                buffer.seek(pos)
                                if "Selector" in node["Node Type"] or node["Node Type"] == "Element_Expression":
                                    current += 16
                                else:
                                    current += 8
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
                        else:
                            for entry in node["Linked Nodes"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                residents.append(entry["Update Info"])
                                buffer.write(u32(len(residents) - 1))
                                current += 8
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
                                buffer.seek(pos)
                    buffer.seek(current)
                else:
                    for i in range(5):
                        buffer.write(u32(0))
        attachment_index_start = buffer.tell()

        if self.nodes:
            base_attach = 0
            buffer.seek(116 + 24 * len(self.commands))
            for node in self.nodes:
                buffer.write(u16(Node_Type[node["Node Type"]].value))
                buffer.write(u16(node["Node Index"]))
                buffer.write(u16(attach_counts[node["Node Index"]]))
                flags = 0
                if "Flags" in node:
                    if "Is Precondition Node" in node["Flags"]:
                        flags = flags | 1
                    if "Is External AINB" in node["Flags"]:
                        flags = flags | 2
                    if "Is Resident Node" in node["Flags"]:
                        flags = flags | 4
                buffer.write(u8(flags) + padding())
                buffer.write(u32(buffer._string_refs[node["Name"]]))
                buffer.write(u32(mmh3.hash(node["Name"], signed=False)))
                buffer.write(u32(0))
                buffer.write(u32(bodies[node["Node Index"]])) # Write offset later
                buffer.write(u16(exb_info[node["Node Index"]][0]))
                buffer.write(u16(exb_info[node["Node Index"]][1]))
                buffer.write(u16(multi_counts[node["Node Index"]]))
                buffer.write(u16(0))
                buffer.write(u32(base_attach))
                buffer.write(u16(node["Base Precondition Node"]))
                buffer.write(u16(precon_counts[node["Node Index"]]))
                buffer.write(u16(0)) # 0x58 Section Offset (Unused in TotK)
                buffer.write(u16(0))
                parts = node["GUID"].split('-')
                parts = [int(i, 16) for i in parts]
                buffer.write(u32(parts[0]))
                buffer.write(u16(parts[1]))
                buffer.write(u16(parts[2]))
                buffer.write(u16(parts[3]))
                parts[4] = hex(parts[4])[2:]
                while len(parts[4]) < 12:
                    parts[4] = "0" + parts[4]
                buffer.write(byte_custom(bytes.fromhex(parts[4]), 6))
                base_attach += attach_counts[node["Node Index"]]
        
        buffer.seek(attachment_index_start)
        if attachments:
            for entry in attachment_indices:
                buffer.write(u32(entry))
            attachment_start = buffer.tell()
            for attachment in attachments:
                buffer.add_string(attachment["Name"])
                buffer.write(u32(buffer._string_refs[attachment["Name"]]))
                buffer.write(u32(attachment_start + 16 * len(attachments) + 100 * attachments.index(attachment)))
                buffer.write(u16(attach_exb_info[attachments.index(attachment)][0]))
                buffer.write(u16(attach_exb_info[attachments.index(attachment)][1]))
                buffer.write(u32(mmh3.hash(attachment["Name"], signed=False)))
            for attachment in attachments:
                if "Debug" in attachment["Name"]:
                    buffer.write(u32(1))
                else:
                    buffer.write(u32(0))
                for type in type_standard:
                    if "Parameters" in attachment:
                        if type in attachment["Parameters"]:
                            for entry in attachment["Parameters"][type]:
                                immediate_parameters[type].append(entry)
                            buffer.write(u32(len(immediate_parameters[type]) - len(attachment["Parameters"][type])))
                            buffer.write(u32(len(attachment["Parameters"][type])))
                            immediate_current[type] = len(immediate_parameters[type])
                        else:
                            buffer.write(u32(immediate_current[type]))
                            buffer.write(u32(0))
                    else:
                        buffer.write(u32(immediate_current[type]))
                        buffer.write(u32(0))
                pos = buffer.tell()
                for i in range(6):
                    buffer.write(u32(0))
                    buffer.write(u32(pos + 24)) # Not sure what the address here means
        else:
            attachment_start = buffer.tell()
        immediate_start = buffer.tell()
        current = immediate_start + 24
        if immediate_parameters:
            for type in type_standard:
                buffer.write(u32(current))
                if type != "vec3f":
                    current += len(immediate_parameters[type] * 12)
                else:
                    current += len(immediate_parameters[type] * 20)
            for type in type_standard:
                for entry in immediate_parameters[type]:
                    buffer.add_string(entry["Name"])
                    buffer.write(u32(buffer._string_refs[entry["Name"]]))
                    flags = 0x0
                    if type == "userdefined":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
                    if "Global Parameters Index" in entry:
                        buffer.write(u16(entry["Global Parameters Index"]))
                        flags += 0x8000
                    elif "EXB Index" in entry:
                        buffer.write(u16(entry["EXB Index"]))
                        flags += 0xc200
                    else:
                        buffer.write(u16(0))
                    if "Flags" in entry:
                        for flag in entry["Flags"]:
                            if flag == "Pulse Thread Local Storage":
                                flags += 0x80
                            if flag == "Set Pointer Flag Bit Zero":
                                flags += 0x100
                        buffer.write(u16(flags))
                    else:
                        buffer.write(u16(0))
                    if type == "int":
                        buffer.write(u32(entry["Value"]))
                    elif type == "bool":
                        buffer.write(u32(int(entry["Value"])))
                    elif type == "float":
                        buffer.write(f32(entry["Value"]))
                    elif type == "string":
                        buffer.add_string(entry["Value"])
                        buffer.write(u32(buffer._string_refs[entry["Value"]]))
                    elif type == "vec3f":
                        for value in entry["Value"]:
                            buffer.write(f32(value))
        else:
            for i in range(6):
                buffer.write(u32(current))
        io_start = buffer.tell()
        current = io_start + 48
        if input_parameters and output_parameters:
            for type in type_standard:
                buffer.write(u32(current))
                if type == "vec3f":
                    current += len(input_parameters[type] * 24)
                elif type == "userdefined":
                    current += len(input_parameters[type] * 20)
                else:
                    current += len(input_parameters[type] * 16)
                buffer.write(u32(current))
                if type != "userdefined":
                    current += len(output_parameters[type] * 4)
                else:
                    current += len(output_parameters[type] * 8)
            for type in type_standard:
                for entry in input_parameters[type]:
                    buffer.add_string(entry["Name"])
                    buffer.write(u32(buffer._string_refs[entry["Name"]]))
                    flags = 0x0
                    if type == "userdefined":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
                    buffer.write(s16(entry["Node Index"]))
                    buffer.write(s16(entry["Parameter Index"]))
                    if "Global Parameters Index" in entry:
                        buffer.write(u16(entry["Global Parameters Index"]))
                        flags += 0x8000
                    elif "EXB Index" in entry:
                        buffer.write(u16(entry["EXB Index"]))
                        flags += 0xc200
                    else:
                        buffer.write(u16(0))
                    if "Flags" in entry:
                        for flag in entry["Flags"]:
                            if flag == "Pulse Thread Local Storage":
                                flags += 0x80
                            if flag == "Set Pointer Flag Bit Zero":
                                flags += 0x100
                        buffer.write(u16(flags))
                    else:
                        buffer.write(u16(0))
                    if type == "int":
                        buffer.write(u32(entry["Value"]))
                    elif type == "bool":
                        buffer.write(u32(int(entry["Value"])))
                    elif type == "float":
                        buffer.write(f32(entry["Value"]))
                    elif type == "string":
                        buffer.add_string(entry["Value"])
                        buffer.write(u32(buffer._string_refs[entry["Value"]]))
                    elif type == "vec3f":
                        for value in entry["Value"]:
                            buffer.write(f32(value))
                    elif type == "userdefined":
                        buffer.write(u32(entry["Value"]))
                for entry in output_parameters[type]:
                    buffer.add_string(entry["Name"])
                    offset = buffer._string_refs[entry["Name"]]
                    if "Set Pointer Flag Bit Zero" in entry:
                        buffer.write(u32(offset | (1 << 31)))
                    else:
                        buffer.write(u32(offset))
                    if type == "userdefined":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
        else:
            for i in range(12):
                buffer.write(u32(current))
        multi_start = buffer.tell()
        if multis:
            for entry in multis:
                buffer.write(s16(entry["Node Index"]))
                buffer.write(s16(entry["Parameter Index"]))
                flags = 0x0
                if "Global Parameters Index" in entry:
                    buffer.write(u16(entry["Global Parameters Index"]))
                    flags += 0x8000
                elif "EXB Index" in entry:
                    buffer.write(u16(entry["EXB Index"]))
                    flags += 0xc200
                else:
                    buffer.write(u16(0))
                if "Flags" in entry:
                    for flag in entry["Flags"]:
                        if flag == "Pulse Thread Local Storage":
                            flags += 0x80
                        if flag == "Set Pointer Flag Bit Zero":
                            flags += 0x100
                    buffer.write(u16(flags))
                else:
                    buffer.write(u16(0))
        resident_start = buffer.tell()
        if residents:
            current = resident_start + len(residents) * 4
            for i in range(len(residents)):
                if "String" in residents[i]:
                    n = 8
                else:
                    n = 4
                buffer.write(u32(current))
                current += n
            for resident in residents:
                flags = 0
                if "Is Valid Update" in resident["Flags"]:
                    flags = flags | 1
                if "Update Post Current Command Calc" in resident["Flags"]:
                    flags = flags | (1 << 31)
                buffer.write(u32(flags))
                if "String" in resident:
                    buffer.add_string(resident["String"])
                    buffer.write(u32(buffer._string_refs[resident["String"]]))
        precondition_start = buffer.tell()
        if precondition_nodes:
            for i in range(len(precondition_nodes)):
                buffer.write(u16(precondition_nodes[i]))
                buffer.write(u16(0)) # Purpose unknown
        exb_start = buffer.tell()
        if self.exb:
            end = self.exb.ToBytes(self.exb, buffer, exb_start, self.exb_instances)
            buffer.seek(end)
        embed_ainb_start = buffer.tell()
        buffer.write(u32(len(self.ainb_array)))
        if self.ainb_array:
            for ainb in self.ainb_array:
                buffer.add_string(ainb["File Path"])
                buffer.write(u32(buffer._string_refs[ainb["File Path"]]))
                buffer.add_string(ainb["File Category"])
                buffer.write(u32(buffer._string_refs[ainb["File Category"]]))
                buffer.write(u32(ainb["Count"]))
        entry_strings_start = buffer.tell()
        buffer.write(u32(len(entry_strings)))
        if entry_strings:
            for entry in entry_strings:
                buffer.write(u32(entry[0]))
                buffer.add_string("メインステート")
                buffer.write(u32(buffer._string_refs["メインステート"]))
                buffer.add_string(entry[1]["メインステート"])
                buffer.write(u32(buffer._string_refs[entry[1]["メインステート"]]))
        hash_start = buffer.tell()
        for hash in self.file_hashes:
            buffer.write(u32(int(self.file_hashes[hash][2:], 16)))
        if "Unknown Parent File Hash" not in self.file_hashes:
            buffer.write(u32(0))
        child_replace_start = buffer.tell()
        buffer.write(u8(0)) # Set at runtime
        buffer.write(u8(0))
        if replacements:
            buffer.write(u16(len(replacements)))
            attach_count = 0
            node_count = 0
            override_node = len(self.nodes)
            override_attach = len(self.attachment_parameters)
            for replacement in replacements:
                if replacement[0] == 2:
                    attach_count += 1
                    override_attach -= 1
                if replacement[0] in [0, 1]:
                    node_count += 1
                    if replacement[0] == 0:
                        override_node -= 1
                    if replacement[0] == 1:
                        override_node -= 2
            if node_count > 0:
                buffer.write(s16(override_node))
            else:
                buffer.write(s16(-1))
            if attach_count > 0:
                buffer.write(s16(override_attach))
            else:
                buffer.write(s16(-1))
            for replacement in replacements:
                buffer.write(u8(replacement[0]))
                buffer.write(u8(0))
                buffer.write(u16(replacement[1]))
                buffer.write(u16(replacement[2]))
                if replacement[0] == 1:
                    buffer.write(u16(replacement[3]))
        else:
            buffer.write(u16(0))
            buffer.write(s16(-1))
            buffer.write(s16(-1))
        x6c_start = buffer.tell()
        buffer.write(u32(0))
        resolve_start = buffer.tell()
        buffer.write(u32(0))
        string_start = buffer.tell()
        buffer.write(buffer._strings)
        buffer.seek(24)
        buffer.write(u32(len(attachments)))
        buffer.seek(36)
        buffer.write(u32(string_start))
        buffer.write(u32(resolve_start))
        buffer.write(u32(immediate_start))
        buffer.write(u32(resident_start))
        buffer.write(u32(io_start))
        buffer.write(u32(multi_start))
        buffer.write(u32(attachment_start))
        buffer.write(u32(attachment_index_start))
        if self.exb:
            buffer.write(u32(exb_start))
        else:
            buffer.write(u32(0))
        buffer.write(u32(child_replace_start))
        buffer.write(u32(precondition_start))
        buffer.write(u32(resident_start)) # 0x50 is always the same as the resident array offset, unused
        buffer.skip(8)
        buffer.write(u32(embed_ainb_start))
        buffer.skip(8)
        buffer.write(u32(entry_strings_start))
        buffer.write(u32(x6c_start))
        buffer.write(u32(hash_start))
        return buffer


if __name__ == "__main__":
    """with open('test.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    test = AINB(data, from_dict=True)"""

    with open('ainb/Npc_Gerudo_Queen_Young.event.root.ainb', 'rb') as file:
        data = file.read()

    test = AINB(data)

    with open('test.json', 'w', encoding='utf-8') as outfile:
        json.dump(test.output_dict, outfile, indent=4, ensure_ascii=False)

    with open('reserialization_test.ainb', 'wb', buffering=1000000) as outfile:
        test.ToBytes(test, outfile)