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
    none                = 0
    bool                = 2
    u32                 = 3
    f32                 = 4
    string              = 5
    vec3f               = 6

class Source(Enum):
    Imm                 = 0
    ImmStr              = 1
    StaticMem           = 2
    ParamTbl            = 3
    ParamTblStr         = 4
    Output              = 5
    Input               = 6
    Scratch32           = 7
    Scratch64           = 8
    UserOut             = 9
    UserIn              = 10

class EXB:
    def __init__(self, data, from_dict=False):
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
                command["Instructions"] = []
                for i in range(command["Instruction Count"]):
                    command["Instructions"].append(self.instructions[command["Instruction Base Index"] + i])
        else:
            self.magic = data["Info"]["Magic"]
            self.version = data["Info"]["Version"]
            self.static_size = data["Info"]["Static Memory Size"]
            self.field_entry_count = data["Info"]["EXB Field Entry Count"]
            self.scratch_32_size = data["Info"]["32-bit Scratch Memory Size"]
            self.scratch_64_size = data["Info"]["64-bit Scratch Memory Size"]
            self.commands = data["Commands"]
            self.instructions = []
            for command in data["Commands"]:
                for key in command:
                    if key == "Instructions":
                        for instruction in command[key]:
                            self.instructions.append(instruction)

        self.exb_section = {
            "Info" : {
                "Magic" : self.magic,
                "Version" : self.version,
                "Static Memory Size" : self.static_size,
                "EXB Field Entry Count" : self.field_entry_count,
                "32-bit Scratch Memory Size" : self.scratch_32_size,
                "64-bit Scratch Memory Size" : self.scratch_64_size
            },
            "Commands" : self.commands
        }

    def Info(self):
        info = {}
        info["Base Index Pre-Command Entry"] = self.stream.read_s32()
        info["Pre-Entry Static Memory Usage"] = self.stream.read_u32()
        info["Instruction Base Index"] = self.stream.read_u32()
        info["Instruction Count"] = self.stream.read_u32()
        info["Unknown 1"] = self.stream.read_u32()
        info["32-bit Scratch Memory Size"] = self.stream.read_u16()
        info["64-bit Scratch Memory Size"] = self.stream.read_u16()
        info["Unknown 2"] = self.stream.read_u16()
        info["Input Data Type Enum"] = self.stream.read_u16()
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
                    elif instruction["Data Type"] == "u32":
                        instruction[f"{i} Value"] = self.stream.read_u32()
                    elif instruction["Data Type"] == "f32":
                        instruction[f"{i} Value"] = self.stream.read_f32()
                    elif instruction["Data Type"] == "vec3f":
                        instruction[f"{i} Value"] = (self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32())
                    self.stream.seek(jumpback)
                if instruction[f"{i} Source"] == "ParamTblStr":
                    jumpback = self.stream.tell()
                    self.stream.seek(self.parameter_region_offset + instruction[f"{i} Index/Value"])
                    instruction[f"{i} Value"] = self.string_pool.read_string()
                    self.stream.seek(jumpback)
                if instruction[f"{i} Source"] == "Imm":
                    instruction[f"{i} Value"] = instruction[f"{i} Index/Value"]
                if instruction[f"{i} Source"] == "ImmStr":
                    instruction[f"{i} Value"] = self.string_pool.read_string(instruction[f"{i} Index/Value"])
            return instruction
        else:
            instruction["Static Memory Index"] = self.stream.read_u16()
            instruction["Signature"] = self.string_pool.read_string(self.signature_offsets[self.stream.read_u32()])
            return instruction
        
    def ToBytes(self, exb, dest, offset=0): # exb is an EXB object
        buffer = WriteStream(dest)
        buffer.seek(offset)
        buffer.write(b'EXB ') # Magic
        buffer.write(b'\x02\x00\x00\x00')
        buffer.write(u32(exb.static_size))
        buffer.write(u32(exb.field_entry_count))
        buffer.write(u32(exb.scratch_32_size))
        buffer.write(u32(exb.scratch_64_size))
        buffer.write(u32(44)) # Command info is always right after header
        buffer.skip(16) # Addresses will be written to later
        buffer.write(u32(len(exb.commands)))
        for command in exb.commands:
            for key in command:
                if key != "Instructions" and " Value" not in key:
                    if key in ["32-bit Scratch Memory Size", "64-bit Scratch Memory Size", "Unknown 2", "Input Data Type Enum"]:
                        buffer.write(u16(command[key]))
                    elif key == "Base Index Pre-Command Entry":
                        buffer.write(s32(command[key]))
                    else:
                        buffer.write(u32(command[key]))
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
                        buffer.write(u16(instruction[key]))
                    elif key == "Static Memory Index":
                        buffer.write(u16(instruction[key]))
                    elif key == "Signature":
                        buffer.add_string(instruction[key])
                        signature_offsets.append(buffer._string_refs[instruction[key]])
                        buffer.write(u32(signature_offsets.index(buffer._string_refs[instruction[key]])))
            else:
                buffer.write(u8(1))
                buffer.skip(7)
        sig_start = buffer.tell()
        buffer.write(u32(len(signature_offsets)))
        for offset1 in signature_offsets:
            buffer.write(u32(offset1))
        param_start = buffer.tell()
        string_start = param_start
        for instruction in exb.instructions:
            for key in instruction:
                if " Value" in key:
                    if instruction[key.strip("Value") + "Source"] == "ParamTbl":
                        buffer.seek(param_start + instruction[key.strip("Value") + "Index/Value"])
                        if type(instruction[key]) == tuple:
                            for value in instruction[key]:
                                buffer.write(f32(value))
                                if buffer.tell() > string_start:
                                    string_start = buffer.tell()
                        elif instruction["Data Type"] == "u32":
                            buffer.write(u32(instruction[key]))
                            if buffer.tell() > string_start:
                                string_start = buffer.tell()
                        elif instruction["Data Type"] == "f32":
                            buffer.write(f32(instruction[key]))
                            if buffer.tell() > string_start:
                                string_start = buffer.tell()
                        elif instruction["Data Type"] == "bool":
                            buffer.write(u32(1 if instruction[key] else 0))
                            if buffer.tell() > string_start:
                                string_start = buffer.tell()
                    if instruction[key.strip("Value") + "Source"] == "ParamTblStr":
                        buffer.seek(param_start + instruction[key.strip("Value") + "Index/Value"])
                        buffer.add_string(instruction[key])
                        buffer.write(u32(buffer._string_refs[instruction[key]]))
                        if buffer.tell() > string_start:
                            string_start = buffer.tell()
        buffer.seek(string_start)
        buffer.write(buffer._strings)
        buffer.seek(offset + 28)
        buffer.write(u32(command_start))
        buffer.write(u32(sig_start))
        buffer.write(u32(param_start))
        buffer.write(u32(string_start))
        return buffer