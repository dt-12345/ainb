from exb import EXB
from utils import *
from enum import Enum
import json
import time

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

type_standard = ["int", "bool", "float", "string", "vec3f", "userdefined"] # Data type order

type_global = ["string", "int", "float", "bool", "vec3f", "userdefined"] # Data type order (global parameters)

file_category = {"AI" : 0, "Logic" : 1, "Sequence" : 2}

class AINB:
    def __init__(self, data, from_dict=False):
        self.max_global_index = 0
        self.output_dict = {}

        if not from_dict:
            self.stream = ReadStream(data)

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
                "Magic" : self.magic,
                "Version" : hex(self.version),
                "Filename" : self.filename,
                "Command Count" : self.command_count,
                "Node Count" : self.node_count,
                "Precondition Node Count" : self.precondition_count,
                "Attachment Count" : self.attachment_count,
                "Output Node Count" : self.output_count,
                "File Category" : self.file_category
            }

            # Commands
            assert self.stream.tell() == 116, "Something went wrong" # Just to make sure we're at the right location
            self.commands = []
            for i in range(self.command_count):
                self.commands.append(self.Command())
            command_end = self.stream.tell()
            
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
                if i < 5:
                    while self.stream.tell() < self.immediate_offsets[i+1]:
                        self.immediate_parameters[type_standard[i]].append(self.ImmediateParameter(type_standard[i]))
                else:
                    while self.stream.tell() < self.io_offset:
                        self.immediate_parameters[type_standard[i]].append(self.ImmediateParameter(type_standard[i]))
            # Remove types with no entries
            self.immediate_parameters = {key : value for key, value in self.immediate_parameters.items() if value}

            # Attachment Parameters
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
            while self.stream.tell() < self.precondition_offset:
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
                self.stream.skip(2)

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

            # Child Replacement
            self.stream.seek(self.child_replacement_offset)
            self.is_replaced = self.stream.read_u8() # Set at runtime, just ignore
            self.stream.skip(1)
            count = self.stream.read_u16()
            node_count = self.stream.read_s16() # Number of overwritten nodes
            attachment_count = self.stream.read_s16() # Number of overwritten attachment parameters
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
        else:
            self.magic = data["Info"]["Magic"]
            self.version = int(data["Info"]["Version"], 16)
            self.filename = data["Info"]["Filename"]
            self.command_count = data["Info"]["Command Count"]
            self.node_count = data["Info"]["Node Count"]
            self.precondition_count = data["Info"]["Precondition Node Count"]
            self.attachment_count = data["Info"]["Attachment Count"]
            self.output_count = data["Info"]["Output Node Count"]
            self.file_category = data["Info"]["File Category"]

            # Defaults
            self.commands, self.ainb_array, self.nodes = [], [], []
            self.global_params, self.exb, self.file_hashes = {}, {}, {}

            if "Commands" in data:
                self.commands = data["Commands"]
            if "Global Parameters" in data:
                self.global_params = data["Global Parameters"]
            if "EXB Section" in data:
                self.exb = EXB(data["EXB Section"], from_dict=True)
            if "File Hashes" in data:
                self.file_hashes = data["File Hashes"]
            if "Embedded AINB Files" in data:
                self.ainb_array = data["Embedded AINB Files"]
            if "Nodes" in data:
                self.nodes = data["Nodes"]
        
        self.output_dict["Info"] = {
                "Magic" : self.magic,
                "Version" : hex(self.version),
                "Filename" : self.filename,
                "Command Count" : self.command_count,
                "Node Count" : self.node_count,
                "Precondition Node Count" : self.precondition_count,
                "Attachment Count" : self.attachment_count,
                "Output Node Count" : self.output_count,
                "File Category" : self.file_category
            }
        if self.commands:
            self.output_dict["Commands"] = self.commands
        if self.global_params:
            self.output_dict["Global Parameters"] = self.global_params
        if self.exb:
            self.output_dict["EXB Section"] = self.exb.exb_section
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
        self.stream.skip(2)
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
        entry["Null String"] = self.string_pool.read_string(self.stream.read_u32())
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
            value = (self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32())
        if type == "userdefined":
            value = None
        return value

    def GlobalFileRef(self):
        entry = {}
        entry["Filename"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Name Hash"] = hex(self.stream.read_u32())
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
        entry["Global/EXB Index"] = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x8000:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x01:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            entry["Flags"].append(hex(flags))
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_u32()
        if type == "float":
            entry["Value"] = self.stream.read_f32()
        if type == "bool":
            entry["Value"] = bool(self.stream.read_u32())
        if type == "vec3f":
            entry["Value"] = (self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32())
        if "Flags" in entry:
            if "0xc200" in entry["Flags"]:
                entry["Function"] = self.exb.commands[entry["Global/EXB Index"]]
                entry["Flags"].remove("0xc200")
        else:
            if entry["Global/EXB Index"] == 0:
                del entry["Global/EXB Index"]
        return entry
    
    def AttachmentEntry(self):
        entry = {}
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Offset"] = self.stream.read_u32()
        self.stream.skip(4)
        entry["Name Hash"] = hex(self.stream.read_u32())
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
        entry["Global/EXB Index"] = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x8000:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x01:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            entry["Flags"].append(hex(flags))
        if type == "string":
            entry["Value"] = self.string_pool.read_string(self.stream.read_u32())
        if type == "int":
            entry["Value"] = self.stream.read_u32()
        if type == "float":
            entry["Value"] = self.stream.read_f32()
        if type == "bool":
            entry["Value"] = bool(self.stream.read_u32())
        if type == "vec3f":
            entry["Value"] = (self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32())
        if type == "userdefined":
            self.stream.skip(4)
        if "Flags" in entry:
            if "0xc200" in entry["Flags"]:
                entry["Function"] = self.exb.commands[entry["Global/EXB Index"]]
                entry["Flags"].remove("0xc200")
        else:
            if entry["Global/EXB Index"] == 0:
                del entry["Global/EXB Index"]
        return entry
    
    def OutputEntry(self, type):
        entry = {}
        flags = self.stream.read_u32()
        entry["Name"] = self.string_pool.read_string(flags & 0x3FFFFFFF)
        flag = flags >> 31
        if flag:
            entry["Set Pointer Flag Bit Zero"] = True
        if type == "userdefined":
            entry["Class"] = self.string_pool.read_string(self.stream.read_u32())
        return entry
    
    def MultiEntry(self):
        entry = {}
        entry["Node Index"] = self.stream.read_u16()
        entry["Parameter Index"] = self.stream.read_u16()
        entry["Global/EXB Index"] = self.stream.read_u16()
        flags = self.stream.read_u16()
        if flags:
            entry["Flags"] = []
            if flags & 0x8000:
                entry["Flags"].append("Pulse Thread Local Storage")
            if flags & 0x01:
                entry["Flags"].append("Set Pointer Flag Bit Zero")
            entry["Flags"].append(hex(flags))
            if "0xc200" in entry["Flags"]:
                entry["Function"] = self.exb.commands[entry["Global/EXB Index"]]
                entry["Flags"].remove("0xc200")
        else:
            if entry["Global/EXB Index"] == 0:
                del entry["Global/EXB Index"]
        return entry
    
    def ResidentEntry(self):
        entry = {}
        flags = self.stream.read_u32()
        entry["Flags"] = []
        if flags >> 31:
            entry["Flags"].append("Update Post Current Command Calc")
        if flags & 0xFF:
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
        self.stream.skip(1)
        entry["Name"] = self.string_pool.read_string(self.stream.read_u32())
        entry["Name Hash"] = hex(self.stream.read_u32())
        self.stream.skip(4)
        entry["Parameters Offset"] = self.stream.read_u32()
        entry["EXB Field Count"] = self.stream.read_u16()
        entry["EXB Value Size"] = self.stream.read_u16()
        entry["Multi-Param Count"] = self.stream.read_u16() # Unnecessary as node parameters will already be paired
        self.stream.skip(2)
        entry["Base Attachment Index"] = self.stream.read_u32()
        entry["Base Precondition Node"] = self.stream.read_u16()
        entry["Precondition Count"] = self.stream.read_u16()
        self.stream.skip(4)
        entry["GUID"] = self.GUID()
        if entry["Precondition Count"] > 0:
            entry["Precondition Nodes"] = []
            for i in range(entry["Precondition Count"]):
                entry["Precondition Nodes"].append(self.precondition_nodes[entry["Base Precondition Node"] + i])
        if entry["Attachment Count"] > 0:
            entry["Attachments"] = []
            for i in range(entry["Attachment Count"]):
                entry["Attachments"].append(self.attachment_parameters[self.attachment_array[entry["Base Attachment Index"] + i]])
        jumpback = self.stream.tell()
        # Match Node Parameters
        self.stream.seek(entry["Parameters Offset"])
        immediate_parameters = {}
        for i in range(6):
            index = self.stream.read_u32()
            count = self.stream.read_u32()
            immediate_parameters[type_standard[i]] = []
            for j in range(count):
                immediate_parameters[type_standard[i]].append(self.immediate_parameters[type_standard[i]][index + j])
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
        # Child Nodes (selectors may need some more work)
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
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Input"] = self.global_params["int"][index]
                                if is_end:
                                    info["Condition"] = "Default"
                                else:
                                    info["Condition"] = self.stream.read_s32()
                            elif entry["Node Type"] == "Element_F32Selector":
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Input"] = self.global_params["float"][index]
                                if not(is_end):
                                    info["Condition Min"] = self.stream.read_f32()
                                    self.stream.skip(4)
                                    info["Condition Max"] = self.stream.read_f32()
                                else:
                                    info[self.string_pool.read_string(self.stream.read_u32())] = "Default"
                            elif entry["Node Type"] == "Element_StringSelector":
                                index = self.stream.read_u16()
                                flag = self.stream.read_u16() >> 15 # Is valid index
                                if flag:
                                    entry["Input"] = self.global_params["string"][index]
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
        self.stream.skip(1)
        entry["Node Index"] = self.stream.read_u16()
        if entry["Type"] in [0, 1]:
            entry["Child Index"] = self.stream.read_u16()
            if entry["Type"] == 1:
                entry["Replacement Index"] = self.stream.read_u16()
            else:
                self.stream.skip(2)
        if entry["Type"] == 2:
            entry["Attachment Index"] = self.stream.read_u16()
            self.stream.skip(2)
        return entry

    def ToBytes(self, ainb, dest): # ainb is an AINB object
        buffer = WriteStream(dest)

        # Header (Round 1)
        buffer.write(b'AIB ') # Magic
        buffer.write(b'\x07\x04\x00\x00')
        buffer.add_string(self.filename)
        buffer.write(u32(buffer._string_refs[self.filename]))
        buffer.write(u32(self.command_count))
        buffer.write(u32(self.node_count))
        buffer.write(u32(self.precondition_count))
        buffer.write(u32(self.attachment_count))
        buffer.write(u32(self.output_count))
        buffer.write(u32(116 + 24 * self.command_count + 60 * self.node_count))
        buffer.skip(44) # Skip writing offsets until they're known
        buffer.skip(8)
        buffer.write(u32(0)) # Used in S3/NSS so will have to change if support for those is added
        buffer.skip(4) # Skip writing offset until it's known
        buffer.add_string(self.file_category)
        buffer.write(u32(buffer._string_refs[self.file_category]))
        buffer.write(u32(file_category[self.file_category]))
        buffer.skip(12) # SKip writing offsets until they're known

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

        # Nodes
        if self.nodes:
            for node in self.nodes:
                buffer.write(u16(Node_Type[node["Node Type"]].value))
                buffer.write(u16(node["Node Index"]))
                buffer.write(u16(node["Attachment Count"]))
                flags = 0
                if "Flags" in node:
                    if "Is Precondition Node" in node["Flags"]:
                        flags = flags | 1
                    if "Is External AINB" in node["Flags"]:
                        flags = flags | 2
                    if "Is Resident Node" in node["Flags"]:
                        flags = flags | 4
                buffer.write(u8(flags) + padding())
                buffer.add_string(node["Name"])
                buffer.write(u32(buffer._string_refs[node["Name"]]))
                buffer.write(u32(int(node["Name Hash"][2:], 16)))
                buffer.skip(4)
                buffer.write(u32(node["Parameters Offset"]))
                buffer.write(u16(node["EXB Field Count"]))
                buffer.write(u16(node["EXB Value Size"]))
                buffer.write(u16(node["Multi-Param Count"]))
                buffer.write(u16(0))
                buffer.write(u32(node["Base Attachment Index"]))
                buffer.write(u16(node["Base Precondition Node"]))
                buffer.write(u16(node["Precondition Count"]))
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

        # Global Parameters
        if self.global_params:
            index = 0
            for type in type_global:
                if type in self.global_params:
                    buffer.write(u16(len(self.global_params[type])))
                else:
                    buffer.write(u16(0))
                buffer.write(u16(index))
                if type == "vec3f" and "vec3f" in self.global_params:
                    buffer.write(u16(index * 4 + len(self.global_params[type] * 8)))
                else:
                    buffer.write(u16(index * 4))
                if type in self.global_params:
                    index += len(self.global_parameters[type])
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
                    buffer.write(u32(name_offset))
                    buffer.add_string(entry["Null String"])
                    buffer.write(u32(buffer._string_refs[entry["Null String"]]))
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
                    if type == "vector3f":
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
                buffer.write(u32(int(file["Name Hash"][2:], 16)))
                buffer.write(u32(int(file["Unknown Hash 1"][2:], 16)))
                buffer.write(u32(int(file["Unknown Hash 2"][2:], 16)))        
        else:
            buffer.skip(48)

        immediate_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0]))
        input_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0]))
        output_current = dict(zip(type_standard, [0, 0, 0, 0, 0, 0]))        

        if self.nodes:
            for node in self.nodes:
                buffer.seek(node["Parameters Offset"])
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
                            buffer.skip(4)
                else:
                    for type in type_standard:
                        buffer.write(u32(immediate_current[type]))
                        buffer.skip(4)
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
                            buffer.skip(4)
                    else:
                        buffer.write(u32(input_current[type]))
                        buffer.skip(4)
                    if "Output Parameters" in node:
                        if type in node["Output Parameters"]:
                            for entry in node["Output Parameters"][type]:
                                output_parameters[type].append(entry)
                            buffer.write(u32(len(output_parameters[type]) - len(node["Output Parameters"][type])))
                            buffer.write(u32(len(node["Output Parameters"][type])))
                            output_current[type] = len(output_parameters[type])
                        else:
                            buffer.write(u32(output_current[type]))
                            buffer.skip(4)
                    else:
                        buffer.write(u32(output_current[type]))
                        buffer.skip(4)
                if "Linked Nodes" in node:
                    total = 0
                    residents = []
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
                    for connection in node["Linked Nodes"]:
                        if connection == "Output/bool Input/float Input Link":
                            for entry in node["Linked Nodes"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                buffer.add_string(entry["Parameter"])
                                buffer.write(u32(buffer._string_refs[entry["Parameter"]]))
                                buffer.skip(8)
                                buffer.seek(pos)
                                is_input = False
                                if "Selector" in node["Node Type"]:
                                    if "Input Parameters" in node:
                                        for type in node["Input Parameters"]:
                                            for parameter in node["Input Parameters"][type]:
                                                if entry["Node Index"] == parameter["Node Index"]:
                                                    is_input = True
                                if is_input:
                                    current += 16
                                else:
                                    current += 8
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
                                    buffer.skip(4)
                                    if "Condition Max" in entry:
                                        buffer.write(f32(entry["Condition Max"]))
                                    else:
                                        buffer.skip(4)
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
                                            buffer.skip(4)
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
                                if "Selector" in node["Node Type"]:
                                    current += 16
                                else:
                                    current += 8
                        else:
                            for entry in node["Linked Nodes"][connection]:
                                buffer.write(u32(current))
                                pos = buffer.tell()
                                buffer.seek(current)
                                buffer.write(u32(entry["Node Index"]))
                                residents.append(entry["Update Info"])
                                buffer.write(u32(len(residents) - 1))
                                current += 8
        print(buffer._string_refs)
        return buffer


if __name__ == "__main__":
    with open('Npc_Gerudo_Queen_Young.event.root.ainb', 'rb') as file:
        data = file.read()

    test = AINB(data)

    with open('test.json', 'w', encoding='utf-8') as outfile:
        json.dump(test.output_dict, outfile, indent=4, ensure_ascii=False)

    with open('reserialization_test.ainb', 'wb', buffering=1000000) as outfile:
        test.ToBytes(test, outfile)


"""
- Finish the entire file
- Find ways to improve speed
- Use functions listed with nodes rather than in the EXB section
- Maybe this? https://stackoverflow.com/questions/5804052/improve-speed-of-reading-and-converting-from-binary-file
- Figure out entry lengths for output/input connections
"""