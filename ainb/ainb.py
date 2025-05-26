from exb import EXB
from utils import *
from enum import Enum
import json
import os
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
type_standard = ["int", "bool", "float", "string", "vec3f", "pointer"] # Data type order

type_global = ["string", "int", "float", "bool", "vec3f", "pointer"] # Data type order (global parameters)

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
            if self.version not in [0x404, 0x407]: # Must be version 4.4 or 4.7
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
                    param["Properties"] = self.AttachmentParameters()
                    del param["Offset"]
                    if not(param["Properties"]):
                        del param["Properties"]
                
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
            self.io_parameters = {"Inputs" : self.input_parameters, "Outputs" : self.output_parameters}

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

            # Queries
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
                    self.functions[i] = command
                    i += 1
                if not self.exb.exb_section["Commands"]:
                    del self.exb.exb_section["Commands"]

            # Nodes - initialize all nodes and assign corresponding parameters
            self.stream.seek(command_end)
            self.nodes = []
            for i in range(self.node_count):
                self.nodes.append(self.Node())
            if self.nodes:
                # Match Entry Strings (purpose still unknown)
                for entry in self.entry_strings:
                    self.nodes[entry["Node Index"]]["XLink Actions"] = entry
                    del self.nodes[entry["Node Index"]]["XLink Actions"]["Node Index"]

            """
            Child Replacement
            These replacements/removals happen upon file initialization (mostly to remove debug nodes)
            We keep the data bc there's no way to recover the replacement table otherwise
            Note: not present in v404
            """
            if(self.version > 0x404):
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
                            for type in self.nodes[replacement["Node Index"]]["Plugs"]:
                                for node in self.nodes[replacement["Node Index"]]["Plugs"][type]:
                                    i += 0
                                    if i == replacement["Child Index"]:
                                        node["Is Removed at Runtime"] = True
                        if replacement["Type"] == 1:
                            i = 0
                            for type in self.nodes[replacement["Node Index"]]["Plugs"]:
                                for node in self.nodes[replacement["Node Index"]]["Plugs"][type]:
                                    if i == replacement["Child Index"]:
                                        node["Replacement Node Index"] = replacement["Replacement Index"]
                                    i += 1
                        if replacement["Type"] == 2:
                            self.nodes[replacement["Node Index"]]["Attachments"][replacement["Attachment Index"]]["Is Removed at Runtime"] = True
            
        else:
            self.magic = data["Info"]["Magic"]
            self.version = int(data["Info"]["Version"], 16)
            self.filename = data["Info"]["Filename"]
            self.file_category = data["Info"]["File Category"]

            # Defaults
            self.commands, self.ainb_array, self.nodes, self.attachment_parameters = [], [], [], []
            self.global_params, self.exb, self.file_hashes = {}, {}, {}
            
            self.functions = {}
            self.exb_instances = 0

            # Get all EXB functions in file
            if "Nodes" in data:
                self.nodes = data["Nodes"]
                for node in self.nodes:
                    if "Properties" in node:
                        for type in node["Properties"]:
                            for entry in node["Properties"][type]:
                                if "Expression" in entry:
                                    self.functions[entry["Expression Index"]] = entry["Expression"]
                                    self.exb_instances += 1
                                if "Sources" in entry:
                                    for parameter in entry["Sources"]:
                                        if "Expression" in parameter:
                                            self.functions[parameter["Expression Index"]] = parameter["Expression"]
                                            self.exb_instances += 1
                    if "Inputs" in node:
                        for type in node["Inputs"]:
                            for entry in node["Inputs"][type]:
                                if "Expression" in entry:
                                    self.functions[entry["Expression Index"]] = entry["Expression"]
                                    self.exb_instances += 1
                                if "Sources" in entry:
                                    for parameter in entry["Sources"]:
                                        if "Expression" in parameter:
                                            self.functions[parameter["Expression Index"]] = parameter["Expression"]
                                            self.exb_instances += 1
                    if "Attachments" in node:
                        for attachment in node["Attachments"]:
                            self.attachment_parameters.append(attachment)
                            if "Properties" in attachment:
                                for type in attachment["Properties"]:
                                    for entry in attachment["Properties"][type]:
                                        if "Expression" in entry:
                                            self.functions[entry["Expression Index"]] = entry["Expression"]
                                            self.exb_instances += 1
                                        if "Sources" in entry:
                                            for parameter in entry["Sources"]:
                                                if "Expression" in parameter:
                                                    self.functions[parameter["Expression Index"]] = parameter["Expression"]
                                                    self.exb_instances += 1

            if "Commands" in data:
                self.commands = data["Commands"]
            if "Blackboard Parameters" in data:
                self.global_params = data["Blackboard Parameters"]
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
            if "Modules" in data:
                self.ainb_array = data["Modules"]
        
        self.output_dict["Info"] = {
                "Magic" : self.magic,
                "Version" : hex(self.version),
                "Filename" : self.filename,
                "File Category" : self.file_category
            }
        if self.commands:
            self.output_dict["Commands"] = self.commands
        if self.global_params:
            self.output_dict["Blackboard Parameters"] = self.global_params
        if self.ainb_array:
            self.output_dict["Modules"] = self.ainb_array
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
            value = bool(self.stream.read_u32())
        if type == "float":
            value = self.stream.read_f32()
        if type == "string":
            value = self.string_pool.read_string(self.stream.read_u32())
        if type == "vec3f":
            value = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
        if type == "pointer":
            value = None # Default values are not stored
        return value

    def GlobalFileRef(self):
        entry = {}
        entry["Filename"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Name Hash"] = hex(self.stream.read_u32())
        entry["Filename Hash"] = hex(self.stream.read_u32())
        entry["Extension Hash"] = hex(self.stream.read_u32())
        del entry["Name Hash"], entry["Filename Hash"], entry["Extension Hash"]
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
        if type == "pointer":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse TLS")
            if flags & 0x100:
                entry["Flags"].append("Is Output")
            if (flags & 0xc200) == 0xc200:
                entry["Expression Index"] = index
                entry["Expression"] = self.exb.commands[entry["Expression Index"]]
                self.functions[entry["Expression Index"]] = entry["Expression"]
            elif flags & 0x8000:
                entry["Blackboard Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        # User-Defined types don't have values stored
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_s32()
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
        entry["Expression Count"] = self.stream.read_u16()
        entry["Expression Input/Output Size"] = self.stream.read_u16()
        if(self.version > 0x404):
            entry["Name Hash"] = hex(self.stream.read_u32()) # not present in v404
        del entry["Expression Count"], entry["Expression Input/Output Size"]
        if(self.version > 0x404):
            del entry["Name Hash"]
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
        if type == "pointer":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Node Index"] = self.stream.read_s16()
        entry["Output Index"] = self.stream.read_s16()
        if entry["Node Index"] <= -100 and entry["Node Index"] >= -8192:
            entry["Multi Index"] = -100 - entry["Node Index"]
            entry["Multi Count"] = entry["Output Index"]
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse TLS")
            if flags & 0x100:
                entry["Flags"].append("Is Output")
            if (flags & 0xc200) == 0xc200:
                entry["Expression Index"] = index
                entry["Expression"] = self.exb.commands[entry["Expression Index"]]
                self.functions[entry["Expression Index"]] = entry["Expression"]
            elif flags & 0x8000:
                entry["Blackboard Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_s32()
        if type == "float":
            entry["Value"] = self.stream.read_f32()
        if type == "bool":
            entry["Value"] = bool(self.stream.read_u32())
        if type == "vec3f":
            entry["Value"] = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
        if type == "pointer":
            entry["Value"] = self.stream.read_u32()
        return entry
    
    def OutputEntry(self, type):
        entry = {}
        flags = self.stream.read_u32()
        entry["Name"] = self.string_pool.read_string(flags & 0x3FFFFFFF)
        flag = flags & 0x80000000
        if flag:
            entry["Is Output"] = True
        if type == "pointer":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def MultiEntry(self):
        entry = {}
        entry["Node Index"] = self.stream.read_u16()
        entry["Output Index"] = self.stream.read_u16()
        index = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x80:
                entry["Flags"].append("Pulse TLS")
            if flags & 0x100:
                entry["Flags"].append("Is Output")
            if (flags & 0xc200) == 0xc200:
                entry["Expression Index"] = index
                entry["Expression"] = self.exb.commands[entry["Expression Index"]]
                self.functions[entry["Expression Index"]] = entry["Expression"]
            elif flags & 0x8000:
                entry["Blackboard Index"] = index
            if not(entry["Flags"]):
                del entry["Flags"]
        return entry
    
    def ResidentEntry(self):
        entry = {}
        flags = self.stream.read_u32()
        entry["Flags"] = []
        if flags >> 31:
            entry["Flags"].append("Update Post Calc")
        if flags & 1:
            entry["Flags"].append("Is Valid Update")
        if "Is Valid Update" not in entry["Flags"]:
            entry["String"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def EntryStringEntry(self):
        entry = {}
        entry["Node Index"] = self.stream.read_u32()
        action_slot = self.string_pool.read_string(self.stream.read_u32())
        action = self.string_pool.read_string(self.stream.read_u32())
        entry["Action Slot"] = action_slot
        entry["Action"] = action
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
                entry["Flags"].append("Is Query")
            if flags & 0b10:
                entry["Flags"].append("Is Module")
            if flags & 0b100:
                entry["Flags"].append("Is Resident Node")
        self.stream.read_u8()
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        if(self.version > 0x404):
            entry["Name Hash"] = hex(self.stream.read_u32()) # not present in v404
        self.stream.read_u32()
        entry["Parameters Offset"] = self.stream.read_u32()
        entry["Expression Count"] = self.stream.read_u16()
        entry["Expression Input/Output Size"] = self.stream.read_u16()
        del entry["Expression Count"], entry["Expression Input/Output Size"]
        entry["Multi-Param Count"] = self.stream.read_u16() # Unnecessary as node parameters will already be paired
        self.stream.read_u16()
        entry["Base Attachment Index"] = self.stream.read_u32()
        entry["Base Query"] = self.stream.read_u16()
        entry["Query Count"] = self.stream.read_u16()
        self.stream.read_u32()
        entry["GUID"] = self.GUID()
        if entry["Query Count"] > 0:
            entry["Queries"] = []
            for i in range(entry["Query Count"]):
                entry["Queries"].append(self.precondition_nodes[entry["Base Query"] + i])
        del entry["Base Query"]
        # This is all to get the function count and I know it could be way more efficient but it's late and I can't think
        if entry["Attachment Count"] > 0:
            entry["Attachments"] = []
            for i in range(entry["Attachment Count"]):
                entry["Attachments"].append(self.attachment_parameters[self.attachment_array[entry["Base Attachment Index"] + i]])
            for attachment in entry["Attachments"]:
                if "Properties" in attachment:
                    for type in attachment["Properties"]:
                        for entry1 in type:
                            if "Expression" in entry1:
                                exb_count += 1
                            if "Sources" in entry1:
                                for parameter in entry1["Sources"]:
                                    if "Expression" in parameter:
                                        exb_count += 1
        # We don't need these anymore actually
        del entry["Attachment Count"], entry["Base Attachment Index"], entry["Multi-Param Count"], entry["Query Count"]
        if(self.version > 0x404):
            del entry["Name Hash"]
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
                if "Expression" in self.immediate_parameters[type_standard[i]][index + j]:
                    exb_count += 1
                if "Sources" in self.immediate_parameters[type_standard[i]][index + j]:
                    for parameter in self.immediate_parameters[type_standard[i]][index + j]["Sources"]:
                        if "Expression" in parameter:
                            exb_count += 1
            if not(immediate_parameters[type_standard[i]]):
                del immediate_parameters[type_standard[i]]
        if immediate_parameters:
            entry["Properties"] = immediate_parameters
        input_parameters = {}
        output_parameters = {}
        for i in range(6):
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            input_parameters[type_standard[i]] = []
            for j in range(count):
                input_parameters[type_standard[i]].append(self.input_parameters[type_standard[i]][index + j])
                if "Expression" in self.input_parameters[type_standard[i]][index + j]:
                    exb_count += 1
                if "Sources" in self.input_parameters[type_standard[i]][index + j]:
                    for parameter in self.input_parameters[type_standard[i]][index + j]["Sources"]:
                        if "Expression" in parameter:
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
            entry["Inputs"] = input_parameters
        if output_parameters:
            entry["Outputs"] = output_parameters
        self.exb_instances += exb_count
        # Child Nodes
        counts = []
        indices = []
        for i in range(10):
            counts.append(self.stream.read_u8())
            indices.append(self.stream.read_u8())
        start = self.stream.tell()
        if sum(counts) != 0:
            entry["Plugs"] = {}
            mapping = {0 : "Bool/Float Input Link and Output Link",
                       1 : None, # Unused in TotK
                       2 : "Standard Link",
                       3 : "Resident Update Link",
                       4 : "String Input Link",
                       5 : "Int Input Link",
                       6 : None, 7 : None, 8 : None, 9 : None} # Unused in TotK
            for i in range(10):
                entry["Plugs"][mapping[i]] = []
                self.stream.seek(start + indices[i] * 4)
                offsets = []
                for j in range(counts[i]):
                    offsets.append(self.stream.read_u32())
                for offset in offsets:
                    self.stream.seek(offset)
                    info = {}
                    info["Node Index"] = self.stream.read_u32()
                    if i == 0:
                        info["Plug Name"] = self.string_pool.read_string(self.stream.read_u32())
                    elif i in [2, 4, 5]:
                        ref = self.string_pool.read_string(self.stream.read_u32())
                        info["Plug Name"] = ref
                        if entry["Node Type"] in ["Element_S32Selector", "Element_F32Selector", "Element_StringSelector", "Element_RandomSelector"]:
                            is_end = bool(offsets.index(offset) == len(offsets) - 1) and i == 2
                            if entry["Node Type"] == "Element_S32Selector":
                                index = self.stream.read_s16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Blackboard Index"] = index
                                if is_end:
                                    info["Condition"] = "Default"
                                else:
                                    info["Condition"] = self.stream.read_s32()
                            elif entry["Node Type"] == "Element_F32Selector":
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Blackboard Index"] = index
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
                                    entry["Blackboard Index"] = index
                                if is_end:
                                    info[self.string_pool.read_string(self.stream.read_u32())] = "Default"
                                else:
                                    info["Condition"] = self.string_pool.read_string(self.stream.read_u32())
                            elif entry["Node Type"] == "Element_RandomSelector":
                                info["Weight"] = self.stream.read_f32()
                        elif entry["Name"] in ["SelectorBSABrainVerbUpdater", "SelectorBSAFormChangeUpdater"]: # hmm
                            info["Unknown 1"] = self.stream.read_u32()
                            info["Unknown 2"] = self.stream.read_u32()
                    if i == 3:
                        update_index = self.stream.read_u32()
                        info["Update Info"] = self.resident_update_array[update_index]
                    entry["Plugs"][mapping[i]].append(info)
                if not(entry["Plugs"][mapping[i]]):
                    del entry["Plugs"][mapping[i]]
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
        buffer.write(u32(self.version))
        buffer.add_string(self.filename)
        buffer.write(u32(buffer._string_refs[self.filename]))
        buffer.write(u32(len(self.commands)))
        buffer.write(u32(len(self.nodes)))
        buffer.write(u32(len([precon for precon in [node for node in self.nodes if "Flags" in node] if "Is Query" in precon["Flags"]])))
        buffer.write(u32(0)) # Skip for now
        buffer.write(u32(len([node for node in self.nodes if "Output" in node["Node Type"]])))
        nodeSize = 60 if self.version > 0x404 else 56
        buffer.write(u32(116 + 24 * len(self.commands) + nodeSize * len(self.nodes)))
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
        base_precon = 0
        base_precons = []

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
                        if "Properties" in attachment:
                            for type in attachment["Properties"]:
                                for entry in attachment["Properties"][type]:
                                    if "Expression" in entry:
                                        exb_count += 1
                                        attach_exb_count += 1
                                        size = 0
                                        for instruction in entry["Expression"]["Instructions"]:
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
                                            for instruction in parameter["Expression"]["Instructions"]:
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
                if "Properties" in node:
                    for type in node["Properties"]:
                        for entry in node["Properties"][type]:
                            if "Expression" in entry:
                                exb_count += 1
                                size = 0
                                for instruction in entry["Expression"]["Instructions"]:
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
                                    if "Expression" in parameter:
                                        exb_count += 1
                                        size = 0
                                        for instruction in parameter["Expression"]["Instructions"]:
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
                if "Inputs" in node:
                    for type in node["Inputs"]:
                        for entry in node["Inputs"][type]:
                            if "Expression" in entry:
                                exb_count += 1
                                size = 0
                                for instruction in entry["Expression"]["Instructions"]:
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
                                    if "Expression" in parameter:
                                        exb_count += 1
                                        size = 0
                                        for instruction in parameter["Expression"]["Instructions"]:
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
                if "Queries" in node:
                    base_precons.append(base_precon)
                    for i in range(len(node["Queries"])):
                        precondition_nodes.update({base_precon + i : node["Queries"][i]})
                    base_precon += len(node["Queries"])
                    precon_counts[node["Node Index"]] = len(node["Queries"])
                else:
                    base_precons.append(0)
                    precon_counts[node["Node Index"]] = 0
                if "XLink Actions" in node:
                    entry_strings.append((node["Node Index"], node["XLink Actions"]))
                exb_info.append((exb_count, exb_size))
        buffer.skip(len(self.nodes) * nodeSize)

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
                        buffer.write(u32(int(entry["Default Value"])))
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
                buffer.write(u32(mmh3.hash(os.path.splitext(os.path.basename(file["Filename"]))[0], signed=False)))
                buffer.write(u32(mmh3.hash(os.path.splitext(file["Filename"])[1].replace('.', ''), signed=False)))  
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
                if "Properties" in node:
                    for type in type_standard:
                        if type in node["Properties"]:
                            for entry in node["Properties"][type]:
                                immediate_parameters[type].append(entry)
                            buffer.write(u32(len(immediate_parameters[type]) - len(node["Properties"][type])))
                            buffer.write(u32(len(node["Properties"][type])))
                            immediate_current[type] = len(immediate_parameters[type])
                        else:
                            buffer.write(u32(immediate_current[type]))
                            buffer.write(u32(0))
                else:
                    for type in type_standard:
                        buffer.write(u32(immediate_current[type]))
                        buffer.write(u32(0))
                for type in type_standard:
                    if "Inputs" in node:
                        if type in node["Inputs"]:
                            for entry in node["Inputs"][type]:
                                input_parameters[type].append(entry)
                            buffer.write(u32(len(input_parameters[type]) - len(node["Inputs"][type])))
                            buffer.write(u32(len(node["Inputs"][type])))
                            input_current[type] = len(input_parameters[type])
                        else:
                            buffer.write(u32(input_current[type]))
                            buffer.write(u32(0))
                    else:
                        buffer.write(u32(input_current[type]))
                        buffer.write(u32(0))
                    if "Outputs" in node:
                        if type in node["Outputs"]:
                            for entry in node["Outputs"][type]:
                                output_parameters[type].append(entry)
                            buffer.write(u32(len(output_parameters[type]) - len(node["Outputs"][type])))
                            buffer.write(u32(len(node["Outputs"][type])))
                            output_current[type] = len(output_parameters[type])
                        else:
                            buffer.write(u32(output_current[type]))
                            buffer.write(u32(0))
                    else:
                        buffer.write(u32(output_current[type]))
                        buffer.write(u32(0))
                if "Plugs" in node:
                    total = 0
                    for connection in ["Bool/Float Input Link and Output Link", 2, "Standard Link",
                                            "Resident Update Link", "String Input Link", "Int Input Link",
                                            7, 8, 9, 10]:
                        if connection in node["Plugs"]:
                            buffer.write(u8(len(node["Plugs"][connection])))
                            buffer.write(u8(total))
                            total += len(node["Plugs"][connection])
                        else:
                            buffer.write(u8(0))
                            buffer.write(u8(total))
                    start = buffer.tell()
                    current = start + total * 4
                    i = 0
                    for connection in node["Plugs"]:
                        if connection == "Resident Update Link":
                            for entry in node["Plugs"][connection]:
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
                        elif connection == "Bool/Float Input Link and Output Link":
                            for entry in node["Plugs"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                buffer.add_string(entry["Plug Name"])
                                buffer.write(u32(buffer._string_refs[entry["Plug Name"]]))
                                buffer.seek(pos)
                                is_input = False
                                if "Selector" in node["Node Type"] or node["Node Type"] == "Element_Expression":
                                    if "Inputs" in node:
                                        for type in node["Inputs"]:
                                            for parameter in node["Inputs"][type]:
                                                if entry["Node Index"] == parameter["Node Index"]:
                                                    is_input = True
                                if is_input:
                                    current += 16
                                elif node["Node Type"] == "Element_Expression" and "Outputs" in node:
                                    if "vec3f" in node["Outputs"]:
                                        for parameter in node["Outputs"]["vec3f"]:
                                            if entry["Plug Name"] == parameter["Name"]:
                                                current += 24
                                else:
                                    current += 8
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
                        else:
                            for entry in node["Plugs"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                buffer.add_string(entry["Plug Name"])
                                buffer.write(u32(buffer._string_refs[entry["Plug Name"]]))
                                if node["Node Type"] == "Element_F32Selector":
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
                                    current += 40
                                elif node["Node Type"] in ["Element_StringSelector", "Element_S32Selector", "Element_RandomSelector"]:
                                    if "Input" in entry:
                                        if node["Node Type"] == "Element_StringSelector":
                                            buffer.write(u32(self.global_params["string"].index(entry["Input"]) | (1 << 31)))
                                        elif node["Node Type"] == "Element_S32Selector":
                                            buffer.write(u32(self.global_params["int"].index(entry["Input"]) | (1 << 31)))
                                        elif node["Node Type"] == "Element_RandomSelector":
                                            buffer.write(u32(self.global_params["float"].index(entry["Input"]) | (1 << 31)))
                                    else:
                                        buffer.write(u32(0))
                                    if "Weight" in entry:
                                        buffer.write(f32(entry["Weight"]))
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
                                    current += 16
                                elif node["Node Type"] == "Element_Expression":
                                    current += 16
                                elif node["Name"] in ["SelectorBSABrainVerbUpdater", "SelectorBSAFormChangeUpdater"]:
                                    buffer.write(u32(entry["Unknown 1"]))
                                    buffer.write(u32(entry["Unknown 2"]))
                                    current += 16
                                else:
                                    current += 8
                                buffer.seek(pos)
                                if "Is Removed at Runtime" in entry:
                                    replacements.append((0, node["Node Index"], i))
                                elif "Replacement Node Index" in entry:
                                    replacements.append((1, node["Node Index"], i, entry["Replacement Node Index"]))
                                i += 1
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
                    if "Is Query" in node["Flags"]:
                        flags = flags | 1
                    if "Is Module" in node["Flags"]:
                        flags = flags | 2
                    if "Is Resident Node" in node["Flags"]:
                        flags = flags | 4
                buffer.write(u8(flags) + padding())
                buffer.write(u32(buffer._string_refs[node["Name"]]))
                if(self.version > 0x404):
                    buffer.write(u32(mmh3.hash(node["Name"], signed=False))) # not present in v404
                buffer.write(u32(0))
                buffer.write(u32(bodies[node["Node Index"]])) # Write offset later
                buffer.write(u16(exb_info[node["Node Index"]][0]))
                buffer.write(u16(exb_info[node["Node Index"]][1]))
                buffer.write(u16(multi_counts[node["Node Index"]]))
                buffer.write(u16(0))
                buffer.write(u32(base_attach))
                buffer.write(u16(base_precons[node["Node Index"]]))
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
            attSize = 16 if (self.version > 0x404) else 12
            for attachment in attachments:
                buffer.add_string(attachment["Name"])
                buffer.write(u32(buffer._string_refs[attachment["Name"]]))
                buffer.write(u32(attachment_start + attSize * len(attachments) + 100 * attachments.index(attachment)))
                buffer.write(u16(attach_exb_info[attachments.index(attachment)][0]))
                buffer.write(u16(attach_exb_info[attachments.index(attachment)][1]))
                if(self.version > 0x404):
                    buffer.write(u32(mmh3.hash(attachment["Name"], signed=False))) # not present in v404
            for attachment in attachments:
                if "Debug" in attachment["Name"]:
                    buffer.write(u32(1))
                else:
                    buffer.write(u32(0))
                for type in type_standard:
                    if "Properties" in attachment:
                        if type in attachment["Properties"]:
                            for entry in attachment["Properties"][type]:
                                immediate_parameters[type].append(entry)
                            buffer.write(u32(len(immediate_parameters[type]) - len(attachment["Properties"][type])))
                            buffer.write(u32(len(attachment["Properties"][type])))
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
                    if type == "pointer":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
                    if "Blackboard Index" in entry:
                        buffer.write(u16(entry["Blackboard Index"]))
                        flags += 0x8000
                    elif "Expression Index" in entry:
                        buffer.write(u16(entry["Expression Index"]))
                        flags += 0xc200
                    else:
                        buffer.write(u16(0))
                    if "Flags" in entry:
                        for flag in entry["Flags"]:
                            if flag == "Pulse TLS":
                                flags += 0x80
                            if flag == "Is Output":
                                flags += 0x100
                    buffer.write(u16(flags))
                    if type == "int":
                        buffer.write(s32(entry["Value"]))
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
                elif type == "pointer":
                    current += len(input_parameters[type] * 20)
                else:
                    current += len(input_parameters[type] * 16)
                buffer.write(u32(current))
                if type != "pointer":
                    current += len(output_parameters[type] * 4)
                else:
                    current += len(output_parameters[type] * 8)
            for type in type_standard:
                for entry in input_parameters[type]:
                    buffer.add_string(entry["Name"])
                    buffer.write(u32(buffer._string_refs[entry["Name"]]))
                    flags = 0x0
                    if type == "pointer":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
                    if "Sources" not in entry:
                        buffer.write(s16(entry["Node Index"]))
                    else:
                        buffer.write(s16(-100 - [x for x in range(len(multis) - len(entry["Sources"]) + 1) if multis[x:x+len(entry["Sources"])] == entry["Sources"]][0]))
                    buffer.write(s16(entry["Output Index"]))
                    if "Blackboard Index" in entry:
                        buffer.write(u16(entry["Blackboard Index"]))
                        flags += 0x8000
                    elif "Expression Index" in entry:
                        buffer.write(u16(entry["Expression Index"]))
                        flags += 0xc200
                    else:
                        buffer.write(u16(0))
                    if "Flags" in entry:
                        for flag in entry["Flags"]:
                            if flag == "Pulse TLS":
                                flags += 0x80
                            if flag == "Is Output":
                                flags += 0x100
                    buffer.write(u16(flags))
                    if type == "int":
                        buffer.write(s32(entry["Value"]))
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
                    elif type == "pointer":
                        buffer.write(u32(entry["Value"]))
                for entry in output_parameters[type]:
                    buffer.add_string(entry["Name"])
                    offset = buffer._string_refs[entry["Name"]]
                    if "Is Output" in entry:
                        buffer.write(u32(offset | (1 << 31)))
                    else:
                        buffer.write(u32(offset))
                    if type == "pointer":
                        buffer.add_string(entry["Class"])
                        buffer.write(u32(buffer._string_refs[entry["Class"]]))
        else:
            for i in range(12):
                buffer.write(u32(current))
        multi_start = buffer.tell()
        if multis:
            for entry in multis:
                buffer.write(s16(entry["Node Index"]))
                buffer.write(s16(entry["Output Index"]))
                flags = 0x0
                if "Blackboard Index" in entry:
                    buffer.write(u16(entry["Blackboard Index"]))
                    flags += 0x8000
                elif "Expression Index" in entry:
                    buffer.write(u16(entry["Expression Index"]))
                    flags += 0xc200
                else:
                    buffer.write(u16(0))
                if "Flags" in entry:
                    for flag in entry["Flags"]:
                        if flag == "Pulse TLS":
                            flags += 0x80
                        if flag == "Is Output":
                            flags += 0x100
                buffer.write(u16(flags))
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
                if "Update Post Calc" in resident["Flags"]:
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
                buffer.add_string(entry[1]["Action Slot"])
                buffer.write(u32(buffer._string_refs[entry[1]["Action Slot"]]))
                buffer.add_string(entry[1]["Action"])
                buffer.write(u32(buffer._string_refs[entry[1]["Action"]]))
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
        if self.version > 0x404:
            buffer.write(u32(child_replace_start))
        else:
            buffer.write(u32(0))
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