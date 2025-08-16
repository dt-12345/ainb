from enum import Enum
from utils import *

# Enums and stuff
class Command(Enum):
    Terminator          = 1
    Store               = 2
    Negate              = 3
    NegateBool          = 4
    Add                 = 5
    Subtract            = 6
    Multiply            = 7
    Divide              = 8
    Modulus             = 9
    Increment           = 10
    Decrement           = 11
    ScalarMultiplyVec3f = 12
    ScalarDivideVec3f   = 13
    LeftShift           = 14
    RightShift          = 15
    LessThan            = 16
    LessThanEqual       = 17
    GreaterThan         = 18
    GreaterThanEqual    = 19
    Equal               = 20
    NotEqual            = 21
    And                 = 22
    Xor                 = 23
    Or                  = 24
    LogicalAnd          = 25
    LogicalOr           = 26
    UserFunction        = 27
    JumpIfLhsZero       = 28
    Jump                = 29

class Type(Enum):
    none                = 0 # For operations that don't involve calculations (such as Jump)
    immediate_or_user   = 1 # Only used for the input/output data type field in command info 
    bool                = 2
    s32                 = 3
    f32                 = 4
    string              = 5
    vec3f               = 6

class Source(Enum):
    Imm                 = 0
    ImmStr              = 1 # String reference
    StaticMem           = 2
    ParamTbl            = 3
    ParamTblStr         = 4 # Index to string reference
    Output              = 5
    Input               = 6
    Scratch32           = 7
    Scratch64           = 8
    UserOut             = 9
    UserIn              = 10

class EXB:
    def __init__(self, data, functions=None, from_dict=False):
        if not from_dict:
            self.stream = ReadStream(data)
            self.data = data

            # Header
            self.magic = self.stream.read(4).decode('utf-8')
            if self.magic != "EXB ":
                raise ValueError(f"Invalid magic: {self.magic} - expected 'EXB '")
            
            self.version = self.stream.read_u32()
            if self.version != 0x02:
                raise ValueError(f"Invalid EXB version: {hex(self.version)} - expected 0x2")
            
            self.static_size = self.stream.read_u32()
            self.field_entry_count = self.stream.read_u32()
            self.scratch_32_size = self.stream.read_u32()
            self.scratch_64_size = self.stream.read_u32()
            command_info_offset = self.stream.read_u32()
            command_table_offset = self.stream.read_u32()
            signature_table_offset = self.stream.read_u32()
            self.parameter_region_offset = self.stream.read_u32()
            string_offset = self.stream.read_u32()

            # String pool (slice extends until end of file but it doesn't matter)
            self.stream.seek(string_offset)
            self.string_pool = ReadStream(self.stream.read())

            # Signature offsets
            self.stream.seek(signature_table_offset)
            sig_count = self.stream.read_u32()
            self.signature_offsets = []
            for i in range(sig_count):
                self.signature_offsets.append(self.stream.read_u32())

            # Not directly parsing the parameter region section
            # Instructions will directly reference a parameter here

            # Command Info
            self.stream.seek(command_info_offset)
            info_count = self.stream.read_u32()
            self.commands = []
            for i in range(info_count):
                self.commands.append(self.Info())

            # Command Instructions
            self.stream.seek(command_table_offset)
            instruction_count = self.stream.read_u32()
            self.instructions = []
            for i in range(instruction_count):
                self.instructions.append(self.ReadInstruction())
            
            # Match instructions to commands
            for command in self.commands:
                if (command["Setup Instruction Base Index"]) != -1:
                    command["Setup Expression"] = []
                    for i in range(command["Setup Instruction Count"]):
                        command["Setup Expression"].append(self.instructions[command["Setup Instruction Base Index"] + i])
                command["Main Expression"] = []
                for i in range(command["Instruction Count"]):
                    command["Main Expression"].append(self.instructions[command["Instruction Base Index"] + i])
                del command["Instruction Count"], command["Instruction Base Index"], \
                    command["Setup Instruction Count"], command["Setup Instruction Base Index"] # Remove unnecessary fields from JSON
        else:
            self.commands = list(dict(sorted(functions.items())).values())
            self.instructions = []
            for entry in self.commands:
                for key in entry:
                    if key == "Main Expression":
                        for instruction in entry[key]:
                            self.instructions.append(instruction)

        self.exb_section = {
            "Commands" : self.commands
        }

    def Info(self):
        info = {}
        info["Setup Instruction Base Index"] = self.stream.read_s32()
        info["Setup Instruction Count"] = self.stream.read_u32()
        info["Instruction Base Index"] = self.stream.read_u32()
        info["Instruction Count"] = self.stream.read_u32()
        info["Static Memory Size"] = self.stream.read_u32()
        info["32-bit Scratch Memory Size"] = self.stream.read_u16()
        info["64-bit Scratch Memory Size"] = self.stream.read_u16()
        info["Output Data Type"] = Type(self.stream.read_u16()).name
        info["Input Data Type"] = Type(self.stream.read_u16()).name
        # We don't need to store these fields
        del info["32-bit Scratch Memory Size"], info["64-bit Scratch Memory Size"], info["Static Memory Size"]
        return info
    
    def ReadInstruction(self):
        instruction = {}
        instruction["Type"] = Command(self.stream.read_u8()).name
        if instruction["Type"] == "Terminator":
            self.stream.skip(7)
            return instruction
        instruction["Data Type"] = Type(self.stream.read_u8()).name
        if instruction["Type"] != "UserFunction":
            instruction["LHS Source"] = Source(self.stream.read_u8()).name
            instruction["RHS Source"] = Source(self.stream.read_u8()).name
            instruction["LHS Index/Value"] = self.stream.read_u16()
            instruction["RHS Index/Value"] = self.stream.read_u16()
            for i in ["LHS", "RHS"]: # Match values to parameters where possible (immediates + parameter region)
                if instruction[f"{i} Source"] == "ParamTbl":
                    jumpback = self.stream.tell()
                    self.stream.seek(self.parameter_region_offset + instruction[f"{i} Index/Value"])
                    if instruction["Data Type"] == "bool":
                        instruction[f"{i} Value"] = bool(self.stream.read_u32())
                    elif instruction["Data Type"] == "s32":
                        instruction[f"{i} Value"] = self.stream.read_u32()
                    elif instruction["Data Type"] == "f32":
                        instruction[f"{i} Value"] = self.stream.read_f32()
                    elif instruction["Data Type"] == "vec3f":
                        if i == "RHS" and instruction["Type"] in ["ScalarMultiplyVec3f", "ScalarDivideVec3f"]:
                            instruction[f"{i} Value"] = self.stream.read_f32()
                        else:
                            instruction[f"{i} Value"] = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
                    self.stream.seek(jumpback)
                elif instruction[f"{i} Source"] == "ParamTblStr":
                    jumpback = self.stream.tell()
                    self.stream.seek(self.parameter_region_offset + instruction[f"{i} Index/Value"])
                    instruction[f"{i} Value"] = self.string_pool.read_string()
                    self.stream.seek(jumpback)
                elif instruction[f"{i} Source"] == "Imm":
                    instruction[f"{i} Value"] = instruction[f"{i} Index/Value"]
                elif instruction[f"{i} Source"] == "ImmStr":
                    instruction[f"{i} Value"] = self.string_pool.read_string(instruction[f"{i} Index/Value"])
                elif i == "RHS" and instruction[f"RHS Source"] in ["UserOut", "UserIn"]:
                    if instruction["Data Type"] == "f32" and instruction["RHS Index/Value"] >> 0xf != 0:
                        val = instruction["RHS Index/Value"]
                        instruction["RHS Index/Value"] = val & 0xff
                        component = (val & 0x7f00) >> 8
                        if component not in [0, 4, 8]:
                            raise ValueError(f"Invalid vec3f component: {component}")
                        instruction["Sub Data Type"] = f"vec3f.{'x' if component == 0 else 'y' if component == 4 else 'z'}"
            return instruction
        else:
            instruction["Static Memory Index"] = self.stream.read_u16()
            instruction["Signature"] = self.string_pool.read_string(self.signature_offsets[self.stream.read_u32()])
            return instruction
        
    def ToBytes(self, exb, dest, offset=0, exb_instance_count=0): # exb is an EXB object
        buffer = dest
        buffer.seek(offset)
        buffer.write(b'EXB ') # Magic
        buffer.write(b'\x02\x00\x00\x00')
        buffer.skip(36) # Will be written at the end
        buffer.write(u32(len(exb.commands)))
        # Temporary variables to track memory allocation sizes
        instruction_index = 0
        max_static = 0
        max_32 = 0
        max_64 = 0
        for command in exb.commands:
            if "Setup Expression" in command:
                buffer.write(u32(instruction_index))
                buffer.write(u32(len(command["Setup Expression"])))
                instruction_index += len(command["Setup Expression"])
            else:
                buffer.write(s32(-1))
                buffer.write(u32(0))
            buffer.write(u32(instruction_index))
            buffer.write(u32(len(command["Main Expression"])))
            instruction_index += len(command["Main Expression"])
            static_size = 0
            for instruction in command["Main Expression"]:
                if "LHS Source" in instruction or "RHS Source" in instruction:
                    if instruction["Data Type"] == "vec3f":
                        size = 12
                    else:
                        size = 4
                    if instruction["LHS Source"] == "StaticMem":
                        static_size = max(static_size, instruction["LHS Index/Value"] + size)
                    if instruction["RHS Source"] == "StaticMem":
                        static_size = max(static_size, instruction["RHS Index/Value"] + size)
                elif "Static Memory Index" in instruction:
                    if instruction["Data Type"] == "vec3f":
                        size = 12
                    else:
                        size = 4
                    static_size = max(static_size, instruction["Static Memory Index"] + size)
            max_static = max(max_static, static_size)
            buffer.write(u32(static_size))
            scratch32_size = 0
            for instruction in command["Main Expression"]:
                if "LHS Source" in instruction or "RHS Source" in instruction:
                    if instruction["Data Type"] == "vec3f":
                        size = 12
                    else:
                        size = 4
                    if instruction["LHS Source"] == "Scratch32":
                        scratch32_size = max(scratch32_size, instruction["LHS Index/Value"] + size)
                    if instruction["RHS Source"] == "Scratch32":
                        scratch32_size = max(scratch32_size, instruction["RHS Index/Value"] + size)
            max_32 += scratch32_size
            buffer.write(u16(scratch32_size))
            scratch64_size = 0
            for instruction in command["Main Expression"]:
                if "LHS Source" in instruction or "RHS Source" in instruction:
                    if instruction["Data Type"] == "vec3f":
                        size = 12
                    else:
                        size = 4
                    if instruction["LHS Source"] == "Scratch64":
                        scratch64_size = max(scratch64_size, instruction["LHS Index/Value"] + size)
                    if instruction["RHS Source"] == "Scratch64":
                        scratch64_size = max(scratch64_size, instruction["RHS Index/Value"] + size)
            max_64 += scratch64_size
            buffer.write(u16(scratch64_size))
            buffer.write(u16(Type[command["Output Data Type"]].value))
            buffer.write(u16(Type[command["Input Data Type"]].value))
        command_start = buffer.tell()
        buffer.write(u32(len(exb.instructions)))
        signature_offsets = []
        for instruction in exb.instructions:
            if instruction["Type"] != "Terminator":
                for key in instruction:
                    if key == "Type":
                        buffer.write(u8(Command[instruction[key]].value))
                    elif key == "Data Type":
                        buffer.write(u8(Type[instruction[key]].value))
                    elif "Source" in key:
                        buffer.write(u8(Source[instruction[key]].value))
                    elif "Index/Value" in key:
                        if "Sub Data Type" in instruction:
                            if "RHS" in key and instruction[key.strip("Index/Value") + "Source"] in ["UserIn", "UserOut"]:
                                if instruction["Sub Data Type"] == "vec3f.x":
                                    instruction[key] |= 0x8000
                                elif instruction["Sub Data Type"] == "vec3f.y":
                                    instruction[key] |= 0x8400
                                elif instruction["Sub Data Type"] == "vec3f.z":
                                    instruction[key] |= 0x8800
                                else:
                                    raise ValueError("Unknown vec3f component!")
                        buffer.write(u16(instruction[key]))
                    elif key == "Static Memory Index":
                        buffer.write(u16(instruction[key]))
                    elif key == "Signature":
                        buffer.add_string_exb(instruction[key])
                        if buffer._string_refs_exb[instruction[key]] not in signature_offsets:
                            signature_offsets.append(buffer._string_refs_exb[instruction[key]])
                        buffer.write(u32(signature_offsets.index(buffer._string_refs_exb[instruction[key]])))
            else:
                buffer.write(u8(1))
                buffer.skip(7)
        sig_start = buffer.tell()
        buffer.write(u32(len(signature_offsets)))
        for offset1 in signature_offsets:
            buffer.write(u32(offset1))
        param_start = buffer.tell()
        string_start = param_start # We need to figure out where the string pool because we are jumping around
        for instruction in exb.instructions:
            for key in instruction:
                if " Value" in key:
                    if instruction[key.strip("Value") + "Source"] == "ParamTbl":
                        buffer.seek(param_start + instruction[key.strip("Value") + "Index/Value"])
                        if type(instruction[key]) == tuple:
                            for value in instruction[key]:
                                buffer.write(f32(value))
                        elif instruction["Data Type"] == "s32":
                            buffer.write(u32(instruction[key]))
                        elif instruction["Data Type"] in ["f32", "vec3f"]: # check vec3f for RHS of vec scalar operations
                            buffer.write(f32(instruction[key]))
                        elif instruction["Data Type"] == "bool":
                            buffer.write(u32(1 if instruction[key] else 0))
                        if buffer.tell() > string_start:
                            string_start = buffer.tell()
                    if instruction[key.strip("Value") + "Source"] == "ParamTblStr":
                        buffer.seek(param_start + instruction[key.strip("Value") + "Index/Value"])
                        buffer.add_string_exb(instruction[key])
                        buffer.write(u32(buffer._string_refs_exb[instruction[key]]))
                        if buffer.tell() > string_start:
                            string_start = buffer.tell()
        buffer.seek(string_start)
        buffer.write(buffer._strings_exb)
        end = buffer.tell()
        buffer.seek(offset + 8)
        buffer.write(u32(max_static))
        buffer.write(u32(exb_instance_count))
        buffer.write(u32(max_32))
        buffer.write(u32(max_64))
        buffer.write(u32(44)) # Command info is always right after header
        buffer.write(u32(command_start - offset))
        buffer.write(u32(sig_start - offset))
        buffer.write(u32(param_start - offset))
        buffer.write(u32(string_start - offset))
        return end