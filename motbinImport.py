# --- Ton-Chan's Motbin import --- #
# Python 3.6.5

from Addresses import game_addresses, GameClass, VirtualAllocEx, VirtualFreeEx, GetLastError, MEM_RESERVE, MEM_COMMIT, MEM_DECOMMIT, MEM_RELEASE, PAGE_EXECUTE_READWRITE
from Aliases import getTag2Requirement, getTag2ExtraMoveProperty, fillAliasesDictonnaries, getTag2HitboxAliasedValue, replaceRequirement, applyCharacterSpecificFixes
import json
import os
import sys

importVersion = "0.8.0"

requirement_size = 0x8
cancel_size = 0x28
move_size = 0xb0
reaction_list_size = 0x70
hit_condition_size = 0x18
pushback_size = 0x10
pushback_extra_size = 0x2
extra_move_property_size = 0xC
voiceclip_size = 0x4
input_sequence_size = 0x10
input_extradata_size = 0x8
projectile_size = 0xa8
throw_extras_size = 0xC
throws_size = 0x10

forbiddenMoves = ['Co_DA_Ground', '___________']
    
class Importer:
    def __init__(self):
        self.T = GameClass("TekkenGame-Win64-Shipping.exe")

    def readInt(self, addr, bytes_length=4):
        return self.T.readInt(addr, bytes_length)
        
    def writeInt(self, addr, value, bytes_length=0):
        return self.T.writeInt(addr, value, bytes_length=bytes_length)

    def readBytes(self, addr, bytes_length):
        return self.T.readBytes(addr, bytes_length)
        
    def writeBytes(self, addr, data):
        return self.T.writeBytes(addr, data)
        
    def writeString(self, addr, text):
        return self.writeBytes(addr, bytes(text + "\x00", 'ascii'))
        
    def readString(self, addr):
        offset = 0
        while self.readInt(addr + offset, 1) != 0:
            offset += 1
        return self.readBytes(addr, offset).decode("ascii")

    def allocateMem(self, allocSize):
        return VirtualAllocEx(self.T.handle, 0, allocSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
                
    def importMoveset(self, playerAddr, folderName):
        moveset = self.loadMoveset(folderName)
        
        motbin_ptr_addr = playerAddr + 0x14a0
        current_motbin_ptr = self.readInt(motbin_ptr_addr, 8)
        old_character_name = self.readString(self.readInt(current_motbin_ptr + 0x8, 8))
        moveset.copyUnknownOffsets(current_motbin_ptr) #Required because we aren't self sufficient yet
        
        print("\nOLD moveset pointer: 0x%x (%s)" % (current_motbin_ptr, old_character_name))
        print("NEW moveset pointer: 0x%x (%s)" % (moveset.motbin_ptr, moveset.m['character_name']))
        self.writeInt(motbin_ptr_addr, moveset.motbin_ptr, 8)
        return moveset
        
    def loadMoveset(self, folderName):
        m = None
        
        jsonFilename = next(file for file in os.listdir(folderName) if file.endswith(".json"))
        print("Reading %s..." % (jsonFilename))
        with open("%s/%s" % (folderName, jsonFilename), "r") as f:
            m = json.load(f)
            f.close()
            
        if 'export_version' not in m or not versionMatches(m['export_version']):
            print("Error: trying to import outdated moveset, please extract again.")
            if 'export_version' in m:
                raise Exception("Moveset version: %s. Importer version: %s." % (m['export_version'], importVersion))
            

        if m['version'] == "Tag2":
            fillAliasesDictonnaries()
            applyCharacterSpecificFixes(m)
        p = MotbinStruct(m, folderName, self)
            
        character_name = p.writeString(m['character_name'])
        creator_name = p.writeString(m['creator_name'])
        date = p.writeString(m['date'])
        fulldate = p.writeString(m['fulldate'])
        
        requirements_ptr, requirement_count = p.allocateRequirements()
        cancel_extradata_ptr, cancel_extradata_size = p.allocateCancelExtradata()
        cancel_ptr, cancel_count = p.allocateCancels(m['cancels'])
        group_cancel_ptr, group_cancel_count = p.allocateCancels(m['group_cancels'], grouped=True)
        pushback_extras_ptr, pushback_extras_count = p.allocatePushbackExtras()
        pushback_ptr, pushback_list_count = p.allocatePushbacks()
        reaction_list_ptr, reaction_list_count = p.allocateReactionList()
        extra_move_properties_ptr, extra_move_properties_count = p.allocateExtraMoveProperties()
        voiceclip_list_ptr, voiceclip_list_count = p.allocateVoiceclipIds()
        hit_conditions_ptr, hit_conditions_count = p.allocateHitConditions()
        moves_ptr, move_count = p.allocateMoves()
        input_extradata_ptr, input_extradata_count = p.allocateInputExtradata()
        input_sequences_ptr, input_sequences_count = p.allocateInputSequences()
        projectiles_ptr, projectiles_count = p.allocateProjectiles()
        throw_extras_ptr, throw_extras_count = p.allocateThrowExtras()
        throws_ptr, throws_count = p.allocateThrows()
        
        self.writeInt(p.motbin_ptr + 0x0, 65536, 4)
        self.writeInt(p.motbin_ptr + 0x4, 4475208, 4)
        
        self.writeInt(p.motbin_ptr + 0x8, character_name, 8)
        self.writeInt(p.motbin_ptr + 0x10, creator_name, 8)
        self.writeInt(p.motbin_ptr + 0x18, date, 8)
        self.writeInt(p.motbin_ptr + 0x20, fulldate, 8)
        
        self.writeAliases(p.motbin_ptr, m)
        
        self.writeInt(p.motbin_ptr + 0x150, reaction_list_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x158, reaction_list_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x160, requirements_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x168, requirement_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x170, hit_conditions_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x178, hit_conditions_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x180, projectiles_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x188, projectiles_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x190, pushback_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x198, pushback_list_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x1A0, pushback_extras_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x1A8, pushback_extras_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x1b0, cancel_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x1b8, cancel_count, 8)

        self.writeInt(p.motbin_ptr + 0x1c0, group_cancel_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x1c8, group_cancel_count, 8)

        self.writeInt(p.motbin_ptr + 0x1d0, cancel_extradata_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x1d8, cancel_extradata_size, 8)
        
        self.writeInt(p.motbin_ptr + 0x1e0, extra_move_properties_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x1e8, extra_move_properties_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x210, moves_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x218, move_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x220, voiceclip_list_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x228, voiceclip_list_count, 8)
       
        self.writeInt(p.motbin_ptr + 0x230, input_sequences_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x238, input_sequences_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x240, input_extradata_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x248, input_extradata_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x260, throw_extras_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x268, throw_extras_count, 8)
        
        self.writeInt(p.motbin_ptr + 0x270, throws_ptr, 8)
        self.writeInt(p.motbin_ptr + 0x278, throws_count, 8)
        
        print("%s successfully imported in memory at 0x%x." % (jsonFilename, p.motbin_ptr))
        print("%d/%d bytes left." % (p.size - (p.curr_ptr - p.head_ptr), p.size))
        
        return p
    
    def writeAliases(self, motbin_ptr, m):
        alias_offset = 0x28
        for alias in m['aliases']:
            self.writeInt(motbin_ptr + alias_offset, alias, 2)
            alias_offset += 2
        
def versionMatches(version):
    pos = version.rfind('.')
    exportUpperVersion = version[:pos]
    
    pos = importVersion.rfind('.')
    importUpperVersion = importVersion[:pos]
    
    if importUpperVersion == exportUpperVersion and version != importVersion:
        print("\nVersion mismatch: consider exporting the moveset again.")
        print("Moveset version: %s. Importer version: %s.\n" % (version, importVersion))
    
    return importUpperVersion == exportUpperVersion

def getTag2RequirementAlias(req, param):
    requirement_detail = getTag2Requirement(req)
    if requirement_detail == None:
        return req, param
    if 'param_alias' in requirement_detail:
        param = requirement_detail['param_alias'].get(param, param)
            
    return requirement_detail['t7_id'], param

def getTag2ExtramovePropertyAlias(type, id):
    new_extra_property = getTag2ExtraMoveProperty(id)
    if new_extra_property == None:
        return type, id
    return type, new_extra_property['t7_id']
        
def align8Bytes(value):
    return value + (8 - (value % 8))
    
def reverseBitOrder(number):
    res = 0
    for i in range(7): #skip last bit
        bitVal = (number & (1 << i)) != 0
        res |= (bitVal << (7 - i))
    return res

def convertU15(number):
    return (number >> 7) | ((reverseBitOrder(number)) << 24)
    
def getTotalSize(m, folderName):
    size = 0
    size += len(m['character_name']) + 1
    size += len(m['creator_name']) + 1
    size += len(m['date']) + 1
    size += len(m['fulldate']) + 1
        
    size = align8Bytes(size)
    size += len(m['requirements']) * 8
        
    size = align8Bytes(size)
    size += len(m['cancel_extradata']) * 4
    
    size = align8Bytes(size)
    size += len(m['cancels']) * 0x28

    size = align8Bytes(size)
    size += len(m['group_cancels']) * 0x28
    
    size = align8Bytes(size)
    size += len(m['pushback_extras']) * 0x2
    
    size = align8Bytes(size)
    size += len(m['pushbacks']) * 0x10
    
    size = align8Bytes(size)
    size += len(m['reaction_list']) * 0x70
    
    size = align8Bytes(size)
    size += len(m['hit_conditions']) * 0x18
    
    size = align8Bytes(size)
    size += len(m['extra_move_properties']) * 0xC
        
    size = align8Bytes(size)
    size += len(m['voiceclips']) * 0x4

    size = align8Bytes(size)
    for animName in m['anims']: 
        size += len(animName) + 1
    
    size = align8Bytes(size)
    for anim in m['anims']:
        size += os.path.getsize("%s/anim/%s.bin" % (folderName, anim))

    size = align8Bytes(size)
    for move in m['moves']:
        size += len(move['name']) + 1   
    
    size = align8Bytes(size)
    size += len(m['moves']) * 0xB0
    
    size = align8Bytes(size)
    size += len(m['input_extradata']) * input_extradata_size
    
    size = align8Bytes(size)
    size += len(m['input_sequences']) * input_sequence_size
    
    size = align8Bytes(size)
    size += len(m['projectiles']) * projectile_size
    
    size = align8Bytes(size)
    size += len(m['throw_extras']) * throw_extras_size
    
    size = align8Bytes(size)
    size += len(m['throws']) * throws_size
    
    return size
    
class MotbinStruct:
    def __init__(self, motbin, folderName, importerObject):
        self.importer = importerObject
        allocSize = getTotalSize(motbin, folderName)
        head_ptr = self.importer.allocateMem(allocSize)
        
        self.motbin_ptr = self.importer.allocateMem(0x2e0)
        self.importer.writeBytes(self.motbin_ptr, bytes([0] * 0x2e0))
        
        self.folderName = folderName
        
        self.m = motbin
        self.size = allocSize
        self.head_ptr = head_ptr
        self.curr_ptr = self.head_ptr
        
        self.cancel_ptr = 0
        self.grouped_cancel_ptr = 0
        self.requirements_ptr = 0
        self.movelist_ptr = 0
        self.animation_ptr = 0
        self.movelist_names_ptr = 0
        self.animation_names_ptr = 0
        self.extra_data_ptr = 0
        self.reaction_list_ptr = 0
        self.hit_conditions_ptr = 0
        self.pushback_ptr = 0
        self.pushback_extras_ptr = 0
        self.extra_move_properties_ptr = 0
        self.voiceclip_ptr = 0
        self.input_extradata_ptr = 0
        self.input_sequences_ptr = 0
        self.projectile_ptr = 0
        self.throw_extras_ptr = 0
        self.throws_ptr = 0
        
        self.move_names_table = {}
        self.animation_table = {}
    
    def getCurrOffset(self):
        return self.curr_ptr - self.head_ptr
     
    def isDataFittable(self, size):
        return (self.getCurrOffset()  + size) <= self.size
        
    def writeBytes(self, data):
        data_len = len(data)
        if not self.isDataFittable(data_len):
            raise
        
        dataPtr = self.curr_ptr
        self.importer.writeBytes(dataPtr, data)
        self.curr_ptr += data_len
        return dataPtr
        
    def writeString(self, text):
        text_len = len(text)
        if not self.isDataFittable(text_len):
            raise
            
        textAddr = self.curr_ptr
        self.importer.writeString(textAddr, text)
        self.curr_ptr += text_len + 1
        return textAddr
        
    def writeInt(self, value, bytes_length):
        if not self.isDataFittable(bytes_length):
            raise
            
        valueAddr = self.curr_ptr
        self.importer.writeInt(valueAddr, value, bytes_length)
        self.curr_ptr += bytes_length
        return valueAddr
        
    def align(self):
        offset = (8 - (self.curr_ptr % 8))
        if not self.isDataFittable(offset):
            raise
        self.curr_ptr += offset
        return self.curr_ptr
        
    def skip(self, offset):
        if not self.isDataFittable(offset):
            raise
            
        self.curr_ptr += offset
        return self.curr_ptr
        
    def getCancelFromId(self, idx):
        if self.cancel_ptr == 0:
            return 0
        return self.cancel_ptr + (idx * cancel_size)
        
    def getRequirementFromId(self, idx):
        if self.requirements_ptr == 0:
            return 0
        return self.requirements_ptr + (idx * requirement_size)
        
    def getCancelExtradataFromId(self, idx):
        if self.extra_data_ptr == 0:
            return 0
        return self.extra_data_ptr + (idx * 4)
        
    def getThrowExtraFromId(self, idx):
        if self.throw_extras_ptr == 0:
            return 0
        return self.throw_extras_ptr + (idx * throw_extras_size)
        
    def getReactionListFromId(self, idx):
        if self.reaction_list_ptr == 0:
            return 0
        return self.reaction_list_ptr + (idx * reaction_list_size)
        
    def getExtraMovePropertiesFromId(self, idx):
        if self.extra_move_properties_ptr == 0 or idx == -1:
            return 0
        return self.extra_move_properties_ptr + (idx * extra_move_property_size)
        
    def getVoiceclipFromId(self, idx):
        if self.voiceclip_ptr == 0 or idx == -1:
            return 0
        return self.voiceclip_ptr + (idx * voiceclip_size)
        
    def getHitConditionFromId(self, idx):
        if self.hit_conditions_ptr == 0:
            return 0
        return self.hit_conditions_ptr + (idx * hit_condition_size)
        
    def getPushbackExtraFromId(self, idx):
        if self.pushback_ptr == 0:
            return 0
        return self.pushback_extras_ptr + (idx * pushback_extra_size)
        
    def getPushbackFromId(self, idx):
        if self.pushback_ptr == 0:
            return 0
        return self.pushback_ptr + (idx * pushback_size)
        
    def getInputExtradataFromId(self, idx):
        if self.input_extradata_ptr == 0:
            return 0
        return self.input_extradata_ptr + (idx * input_extradata_size)
                
    def forbidCancel(self, move_id, groupedCancels=False):
        cancel_list = self.m['group_cancels' if groupedCancels else 'cancels']
        cancel_head_ptr = self.grouped_cancel_ptr if groupedCancels else self.cancel_ptr
        
        if cancel_head_ptr == 0:
            return
        
        cancels_toedit = [(i, c) for i, c in enumerate(cancel_list) if c['move_id'] == move_id]
        
        for i, cancel in cancels_toedit:
            addr = cancel_head_ptr + (i * cancel_size)
            self.importer.writeInt(addr, 0xFFFFFFFFFFFFFFFF, 8)
        
    def allocateInputExtradata(self):
        if self.input_extradata_ptr != 0:
            return
        self.input_extradata_ptr = self.align()
        
        for extradata in self.m['input_extradata']:
            self.writeInt(extradata['u1'], 4)
            self.writeInt(extradata['u2'], 4)
        
        return self.input_extradata_ptr, len(self.m['input_extradata'])
        
    def allocateInputSequences(self):
        if self.input_sequences_ptr != 0:
            return
        self.input_sequences_ptr = self.align()
        
        for input_sequence in self.m['input_sequences']:
            self.writeInt(input_sequence['u1'], 2)
            self.writeInt(input_sequence['u2'], 2)
            self.writeInt(input_sequence['u3'], 4)
            extradata_addr = self.getInputExtradataFromId(input_sequence['extradata_id'])
            self.writeInt(extradata_addr, 8)
        
        return self.input_sequences_ptr, len(self.m['input_sequences'])
        
    def allocateRequirements(self):
        if self.requirements_ptr != 0:
            return
        print("Allocating requirements...")
        self.requirements_ptr = self.align()
        requirements = self.m['requirements']
        requirement_count = len(requirements)
        
        for requirement in requirements:
            req = requirement['req']
            param = requirement['param']
            if self.m['version'] == "Tag2":
                req, param = getTag2RequirementAlias(req, param)
            req, param = replaceRequirement(req, param)
            self.writeInt(req, 4)
            self.writeInt(param, 4)
        
        return self.requirements_ptr, requirement_count
        
    def allocateCancelExtradata(self):
        if self.extra_data_ptr != 0:
            return
        print("Allocating cancel extradatas...")
        self.extra_data_ptr = self.align()
        
        for c in self.m['cancel_extradata']:
            self.writeInt(c, 4)
        
        return self.extra_data_ptr, len(self.m['cancel_extradata'])
        
    def allocateVoiceclipIds(self):
        if self.voiceclip_ptr != 0:
            return
        print("Allocating voiceclips IDs...")
        self.voiceclip_ptr = self.align()
        
        for voiceclip in self.m['voiceclips']:
            self.writeInt(voiceclip, 4)
        
        return self.voiceclip_ptr, len(self.m['voiceclips'])
        
        
    def allocateCancels(self, cancels, grouped=False):
        if grouped:
            print("Allocating grouped cancels...")
            self.grouped_cancel_ptr = self.align()
        else:
            print("Allocating cancels...")
            self.cancel_ptr = self.align()
        cancel_count = len(cancels)
        
        for cancel in cancels:
            self.writeInt(cancel['command'], 8)
            
            requirements_addr = self.getRequirementFromId(cancel['requirement'])
            self.writeInt(requirements_addr, 8)
            
            extraDataAddr = self.getCancelExtradataFromId(cancel['extradata'])
            self.writeInt(extraDataAddr, 8)
            
            self.writeInt(cancel['frame_window_start'], 4)
            self.writeInt(cancel['frame_window_end'], 4)
            self.writeInt(cancel['starting_frame'], 4)
            self.writeInt(cancel['move_id'], 2)
            self.writeInt(cancel['unknown'], 2)
                
        return self.cancel_ptr if not grouped else self.grouped_cancel_ptr, cancel_count
        
    def allocatePushbackExtras(self):
        print("Allocating pushback extradata...")
        self.pushback_extras_ptr = self.align()
        
        for extra in self.m['pushback_extras']:
            self.writeInt(extra, 2)
        
        return self.pushback_extras_ptr, len(self.m['pushback_extras'])
        
    def allocatePushbacks(self):
        print("Allocating pushbacks...")
        self.pushback_ptr = self.align()
        
        for pushback in self.m['pushbacks']:
            self.writeInt(pushback['val1'], 2)
            self.writeInt(pushback['val2'], 2)
            self.writeInt(pushback['val3'], 4)
            self.writeInt(self.getPushbackExtraFromId(pushback['extra_index']), 8)
        
        return self.pushback_ptr, len(self.m['pushbacks'])
                
    def allocateReactionList(self):
        print("Allocating reaction list...")
        self.reaction_list_ptr = self.align()
        
        for reaction_list in self.m['reaction_list']:
            self.importer.writeBytes(self.curr_ptr, bytes([0] * reaction_list_size))
            
            for pushback in reaction_list['pushback_indexes']:
                self.writeInt(self.getPushbackFromId(pushback), 8)
            for unknown in reaction_list['u1list']:
                self.writeInt(unknown, 2)
                
            self.skip(0x8)
            self.writeInt(reaction_list['vertical_pushback'], 4)
            self.writeInt(reaction_list['standing'], 2)
            self.writeInt(reaction_list['crouch'], 2)
            self.writeInt(reaction_list['ch'], 2)
            self.writeInt(reaction_list['crouch_ch'], 2)
            self.writeInt(reaction_list['left_side'], 2)
            self.writeInt(reaction_list['left_side_crouch'], 2)
            self.writeInt(reaction_list['right_side'], 2)
            self.writeInt(reaction_list['right_side_crouch'], 2)
            self.writeInt(reaction_list['back'], 2)
            self.writeInt(reaction_list['back_crouch'], 2)
            self.writeInt(reaction_list['block'], 2)
            self.writeInt(reaction_list['crouch_block'], 2)
            self.writeInt(reaction_list['wallslump'], 2)
            self.writeInt(reaction_list['downed'], 2)
            self.skip(4)
        
        return self.reaction_list_ptr, len(self.m['reaction_list'])
        
    def allocateHitConditions(self):
        print("Allocating hit conditions...")
        self.hit_conditions_ptr = self.align()
        
        for hit_condition in self.m['hit_conditions']:
            requirement_addr = self.getRequirementFromId(hit_condition['requirement'])
            reaction_list_addr = self.getReactionListFromId(hit_condition['reaction_list'])
            self.writeInt(requirement_addr, 8)
            self.writeInt(hit_condition['damage'], 4) 
            self.writeInt(0, 4) 
            self.writeInt(reaction_list_addr, 8)
        
        return self.hit_conditions_ptr, len(self.m['hit_conditions'])
        
    def allocateProjectiles(self):
        print("Allocating projectiles...")
        self.projectile_ptr = self.align()
        
        for p in self.m['projectiles']:
            curr = self.curr_ptr
            self.importer.writeBytes(self.curr_ptr, bytes([0] * projectile_size))
            
            for short in p['u1']:
                self.writeInt(short, 2)
            
            on_hit_addr = 0
            cancel_addr = 0
            if p['hit_condition'] != -1:
                on_hit_addr = self.getHitConditionFromId(p['hit_condition'])
            if p['hit_condition'] != -1:
                cancel_addr = self.getCancelFromId(p['cancel'])
            self.writeInt(on_hit_addr, 8)
            self.writeInt(cancel_addr, 8)
            
            for short in p['u2']:
                self.writeInt(short, 2)
            
            y = self.curr_ptr - curr 
            if y != 0xa8:
                print("Error, %d %x" % (y, y))
                raise
        
        return self.projectile_ptr, len(self.m['projectiles'])
        
    def allocateThrowExtras(self):
        print("Allocating throw extras...")
        self.throw_extras_ptr = self.align()
        
        for t in self.m['throw_extras']:
            self.writeInt(t['u1'], 4)
            for short in t['u2']:
                self.writeInt(short, 2)
        
        return self.throw_extras_ptr, len(self.m['throw_extras'])
        
    def allocateThrows(self):
        print("Allocating throws...")
        self.throws_ptr = self.align()
        
        for t in self.m['throws']:
            self.writeInt(t['u1'], 8)
            extra_addr = self.getThrowExtraFromId(t['unknown_idx'])
            self.writeInt(extra_addr, 8)
        
        return self.throws_ptr, len(self.m['throws'])
        
    def allocateExtraMoveProperties(self):
        print("Allocating extra move properties...")
        self.extra_move_properties_ptr = self.align()
        
        for extra_property in self.m['extra_move_properties']:
            type, id, value = extra_property.values()
            if self.m['version'] == "Tag2":
                type, id = getTag2ExtramovePropertyAlias(type, id)
            self.writeInt(type, 4)
            self.writeInt(id, 4)
            self.writeInt(value, 4)
        
        return self.extra_move_properties_ptr, len(self.m['extra_move_properties'])
        
    def allocateAnimations(self):
        print("Allocating animations...")
        self.animation_names_ptr = self.align()
        self.animation_table = {name:{'name_ptr':self.writeString(name)} for name in self.m['anims']}
        
        self.animation_ptr = self.align()
        for name in self.m['anims']:
            with open("%s/anim/%s.bin" % (self.folderName, name), "rb") as f:
                self.animation_table[name]['data_ptr'] = self.writeBytes(f.read())
        
    def allocateMoves(self):
        self.allocateAnimations()
    
        print("Allocating moves...")
        self.movelist_names_ptr =  self.align()
        moves = self.m['moves']
        moveCount = len(moves)
        
        self.move_names_table = {move['name']:self.writeString(move['name']) for move in moves}
        
        forbiddenMoveIds = []
        
        self.movelist_ptr = self.align()
        for i, move in enumerate(moves):
            if move['name'] in forbiddenMoves:
                forbiddenMoveIds.append(i)
        
            name_addr = self.move_names_table.get(move['name'], 0)
            anim_dict = self.animation_table.get(move['anim_name'], None)
            anim_name, anim_ptr = anim_dict['name_ptr'], anim_dict['data_ptr']
            
            self.writeInt(name_addr, 8)
            self.writeInt(anim_name, 8)
            self.writeInt(anim_ptr, 8)
            self.writeInt(move['vuln'], 4)
            self.writeInt(move['hitlevel'], 4)
            self.writeInt(self.getCancelFromId(move['cancel']), 8)
            
            self.writeInt(0, 8) #['u1'], ptr
            self.writeInt(move['u2'], 8)
            self.writeInt(move['u3'], 8)
            self.writeInt(move['u4'], 8)
            self.writeInt(0, 8) #['u5'], ptr
            self.writeInt(move['u6'], 4)
            
            self.writeInt(move['transition'], 2)
            
            self.writeInt(move['u7'], 2)
            self.writeInt(move['u8'], 2)
            self.writeInt(move['u8_2'], 2)
            self.writeInt(move['u9'], 4)
            
            on_hit_addr = self.getHitConditionFromId(move['hit_condition'])
            self.writeInt(on_hit_addr, 8)
            self.writeInt(move['anim_max_len'], 4)
            
            if self.m['version'] == "Tag2": #Pushback correction
                move['u15'] = convertU15(move['u15'])
                
            self.writeInt(move['u10'], 4)
            self.writeInt(move['u11'], 4)
            self.writeInt(move['u12'], 4)
            
            voiceclip_addr = self.getVoiceclipFromId(move['voiceclip'])
            extra_properties_addr = self.getExtraMovePropertiesFromId(move['extra_properties_id'])
            
            self.writeInt(voiceclip_addr, 8)
            self.writeInt(extra_properties_addr, 8)
            
            self.writeInt(0, 8) #['u13'], ptr
            self.writeInt(0, 8) #['u14'], ptr
            self.writeInt(move['u15'], 4)
            
            hitbox = move['hitbox_location']
            if self.m['version'] == "Tag2":
                hitbox = getTag2HitboxAliasedValue(hitbox)
            
            self.writeInt(hitbox, 4)
            self.writeInt(move['startup'], 4)
            self.writeInt(move['recovery'], 4)
            
            self.writeInt(move['u16'], 2)
            self.writeInt(move['u17'], 2)
            self.writeInt(move['u18'], 4)
        
        for move_id in forbiddenMoveIds:
            self.forbidCancel(move_id, groupedCancels = True)
            self.forbidCancel(move_id, groupedCancels = False)
            
        return self.movelist_ptr, moveCount
    
    def copyUnknownOffsets(self, motbin_ptr):
        offsets = [
            (0x1f0, 8),
            (0x1f8, 8),
            (0x200, 8),
            (0x208, 8),
            (0x250, 8),
            (0x258, 8),
            (0x280, 0x60)
        ]
        
        for offset, read_size in offsets:
            offsetBytes = self.importer.readBytes(motbin_ptr + offset, read_size)
            self.importer.writeBytes(self.motbin_ptr + offset, offsetBytes)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: [FOLDER_NAME]")
        os._exit(1)
        
    TekkenImporter = Importer()
    TekkenImporter.importMoveset(game_addresses.addr['p1_addr'], sys.argv[1])
    
    if len(sys.argv) > 2:
        TekkenImporter.importMoveset(game_addresses.addr['p2_addr'], sys.argv[2])
    