 # -*- coding: utf-8 -*-
#A Sci-Fi/Cyberpunk Roguelike written by Andrew Wright.
#Special thanks to "Jotaf", the Roguebasin, and all of the contributors to the libtcodpy project.
#Inspired by "Dwarf Fortress", "Dungeon Crawl Stone Soup", "Angband", "IVAN", "Fallout", "Rogue", "Metroid", "Crypt of the Necrodancer", "The Slimy Lichmummy", "The Binding of Isaac", and many others.

#Copyright 2012-2015 Andrew Wright
#
#The distributed works are licensed under a Creative Commons Attribution-NonCommercial 3.0 License.
#
#Feel free to copy and share the works provided, but don't sell them!
#
#For more information please visit the web address provided below.
#
#http://creativecommons.org/licenses/by-nc/3.0/

#Grid is shipped with SDL.dll. The official license is:

###Licensing the Simple DirectMedia Layer library

###The Simple DirectMedia Layer library is currently available under the
###GNU Lesser General Public License (LGPL) version 2.1 or newer. This
###license allows you to link with the library in such a way that users
###can modify the library and have your application use the new version.

###The GNU LGPL license can be found online at:
###http://www.gnu.org/copyleft/lgpl.html

###To comply with this license, you must give prominent notice that you use the Simple DirectMedia Layer library, and that it is included under the terms of the LGPL license. You must provide a copy of the LGPL license.
###You must also do one of the following:
###1. Link with the library as a shared object (e.g. SDL.dll or libSDL.so)
###2. Provide the object or source code to your application along with any libraries and custom tools not available with a standard platform development kit.
###You may also simply provide a written offer, valid for three years, to provide these materials upon request to anyone with a legal copy of your application.
###If you include the SDL library in binary form, you should also make available the source code to the version you provide, including any customizations you have made.
###If you link to a standard version of the library, simply referring to the SDL website is sufficient.

#The simplest way to acquire SDL is to visit the official website here: http://www.libsdll.org

import libtcodpy as libtcod
import math
import textwrap
import os
import sys
import shelve
import dbhash
import datetime
import random
import pyglet
import logging

def importData(filename):
    import imp
    f = open(filename)
    global data
    data = imp.load_source("data", "", f)
    f.close()

importData("config.txt")

SCREEN_WIDTH = data.width
SCREEN_HEIGHT = data.height
MAP_WIDTH = data.map_width
MAP_HEIGHT = data.map_height

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 9 #default 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT - 1
MSG_X = BAR_WIDTH + 3
MSG_WIDTH = SCREEN_WIDTH - 35
MSG_HEIGHT = PANEL_HEIGHT
INVENTORY_WIDTH = 50
PANEL_BUMP = 12
MAP_BUMP = (PANEL_BUMP*-1)-3

#parameters for dungeon generator
ROOM_MAX_SIZE = 12
ROOM_MIN_SIZE = 4
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 4
MAX_ROOM_EQUIPMENT = 1
MAX_ROOM_CONSUMABLES = 1
MONSTER_COUNT = 0
BOSS_COUNT = 0

WIZ_MODE = False

turncount = 1
playcount = 0
wincount = 0
sound_state = True
pet_type = 0
dungeon_seed = 0

FOV_ALGO = libtcod.FOV_SHADOW #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not

TORCH_RADIUS = 8 #default 8; set to 10 if BIG BROTHER; set to 4 if CYBERDAEMON OF DARKNESS; set to 5 if BIG BROTHER & CYBERDAEMON OF DARKNESS

LIMIT_FPS = 120

hit_sound = pyglet.resource.media('dat/sounds/combo2.wav', streaming=False)
lose_sound = pyglet.resource.media('dat/sounds/lose.wav', streaming=False)
win_sound = pyglet.resource.media('dat/sounds/win.wav', streaming=False)
oil_sound = pyglet.resource.media('dat/sounds/oil.wav', streaming=False)
mask_sound = pyglet.resource.media('dat/sounds/mask.wav', streaming=False)
pickup_sound = pyglet.resource.media('dat/sounds/pickup.wav', streaming=False)
explosion_sound = pyglet.resource.media('dat/sounds/explosion.wav', streaming=False)

wallColor = libtcod.Color(255, 255, 255)

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight=None, color=None, flag=None, clouds=None):
        self.blocked = blocked
        self.flag = flag
        self.clouds = {'Smoke':0, 'Miasma':0, 'Mist':0, 'Curse':0}
        self.block_sight = block_sight

        self.color = libtcod.white

        self.base_color = self.color

        self.explored = False

class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
    #this is a generic object: the player, a monster, an item, the stairs...
    #it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, examineMSG=None, special_flag=False, boss=False, took_turn=False, effect_flag=False, NPC_flag=False, always_visible=False, blocks=False, fighter=None, PC=None, ai=None, item=None, equipment=None, teleporter=None, bg_color=libtcod.black):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.original_color = color
        self.color = color
        self.bg_color = bg_color
        self.original_bg_color = bg_color
        self.blocks = blocks
        self.fighter = fighter
        self.always_visible = always_visible
        self.PC = PC
        self.boss = boss
        self.effect_flag = effect_flag
        self.teleporter = teleporter
        self.NPC_flag = NPC_flag
        self.took_turn = took_turn
        self.examineMSG = examineMSG
        self.special_flag = special_flag

        if self.fighter:  #let the fighter component know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai:  #let the AI component know who owns it
            self.ai.owner = self

        self.item = item
        if self.item:  #let the Item component know who owns it
            self.item.owner = self

        self.equipment = equipment
        if self.equipment:  #let the Equipment component know who owns it
            self.equipment.owner = self

            #there must be an Item component for the Equipment component to work properly
            self.item = Item()
            self.item.owner = self

    def move(self, dx, dy):
        #move by the given amount, if the destination is not blocked
        if 0 <= (self.x + dx) < MAP_WIDTH and 0 <= (self.y + dy) < MAP_HEIGHT:
            if not is_blocked(self.x + dx, self.y + dy) or (self.fighter and self.fighter.status.get('Acidic') > 0):
                if (self.ai and ('swims' in self.ai.tags and map[self.x+dx][self.y+dy].flag == 'water')) or (self.ai and 'swims' not in self.ai.tags) or (not self.ai):
                    if map[self.x+dx][self.y+dy].flag != 'shop' and is_blocked(self.x + dx, self.y + dy):
                        map[self.x+dx][self.y+dy] = Tile(False, False, flag=None)
                        if self == player:
                            message('You melt through the wall.', libtcod.white)
                    if map[self.x+dx][self.y+dy].flag != 'shop':
                        self.x += dx
                        self.y += dy
                        if self.fighter:
                            if self.fighter.status.get('Stuck') > 0:
                                self.x -= dx
                                self.y -= dy
                                if self == player:
                                    message('You are stuck!', libtcod.red)

                    if self.fighter and self.fighter.status.get('Confused') > 0:
                        if libtcod.random_get_int(dungeon_seed, 1, 3) != 1:
                            self.x -= dx
                            self.y -= dy
                            if not is_blocked(self.x - dx, self.y - dy) or (self.fighter.status.get('Acidic') > 0):
                                self.x -= dx
                                self.y -= dy
                            if self == player:
                                message('You stumble around in confusion.')

    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        #only show if it's visible to the player
        if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored) or (self.fighter and self.fighter.status.get('Faerie Fire') > 0) or (self.fighter and player.fighter.status.get('Telepathy') > 0):
            #set the color and then draw the character that represents this object at its position
            if libtcod.map_is_in_fov(fov_map, self.x, self.y):
                libtcod.console_put_char_ex(con, self.x, self.y, self.char, self.color, self.bg_color)
            else:
                libtcod.console_put_char_ex(con, self.x, self.y, self.char, self.color*libtcod.grey, self.bg_color*libtcod.grey)

    def clear(self):
        #erase the character that represents this object
        if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.fighter and self.fighter.status.get('Faerie Fire') > 0) or (player.fighter.status.get('Telepathy') > 0):
            if not map[self.x][self.y].explored:
                libtcod.console_put_char_ex(con, self.x, self.y, ' ', libtcod.black, libtcod.black)
            else:
                libtcod.console_put_char_ex(con, self.x, self.y, '.', libtcod.Color(238, 238, 238), libtcod.black)

    def move_astar(self, target):
        #Create a FOV map that has the dimensions of the map
        if (self.ai and ('swims' in self.ai.tags and map[self.x][self.y].flag == 'water')) or (self.ai and 'swims' not in self.ai.tags) or (not self.ai):
            fov = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
     
            #Scan the current map each turn and set all the walls as unwalkable
            for y1 in range(MAP_HEIGHT):
                for x1 in range(MAP_WIDTH):
                    if self.fighter and self.fighter.status.get('Acidic') <= 0:
                        libtcod.map_set_properties(fov, x1, y1, not map[x1][y1].block_sight, not map[x1][y1].blocked)
     
            #Scan all the objects to see if there are objects that must be navigated around
            #Check also that the object isn't self or the target (so that the start and the end points are free)
            #The AI class handles the situation if self is next to the target so it will not use this A* function anyway   
            for obj in objects:
                if obj.blocks and obj != self and obj != target:
                    #Set the tile as a wall so it must be navigated around
                    libtcod.map_set_properties(fov, obj.x, obj.y, True, False)
     
            #Allocate a A* path
            #The 1.41 is the normal diagonal cost of moving, it can be set as 0.0 if diagonal moves are prohibited
            my_path = libtcod.path_new_using_map(fov, 1.41)
     
            #Compute the path between self's coordinates and the target's coordinates
            libtcod.path_compute(my_path, self.x, self.y, target.x, target.y)
     
            #Check if the path exists, and in this case, also the path is shorter than 25 tiles
            #The path size matters if you want the monster to use alternative longer paths (for example through other rooms) if for example the player is in a corridor
            #It makes sense to keep path size relatively low to keep the monsters from running around the map if there's an alternative path really far away        
            if not libtcod.path_is_empty(my_path) and libtcod.path_size(my_path) < 25:
                #Find the next coordinates in the computed full path
                x, y = libtcod.path_walk(my_path, True)
                if x or y:
                    #Set self's coordinates to the next path tile
                    self.x = x
                    self.y = y
            else:
                #Keep the old move function as a backup so that if there are no paths (for example another monster blocks a corridor)
                #it will still try to move towards the player (closer to the corridor opening)
                self.move_towards(target.x, target.y)  
     
            #Delete the path to free memory
            libtcod.path_delete(my_path)

class PC:
    def __init__(self, pp, experience, brightness, agility, dexterity, strength):
        self.daily_check = False
        self.floor_turncount = 0
        self.old_dungeon_level = 1
        self.base_max_pp = pp #system core for AV-Protocol
        self.pp = pp
        self.base_agility = agility
        self.base_dexterity = dexterity
        self.base_strength = strength
        self.experience = experience
        self.total_experience = 0
        self.brightness = brightness
        self.interaction_checker = []

    @property
    def weapon_type(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.weapon_type for equipment in get_all_equipped(player))
        return bonus

    @property
    def brightness(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.brightness for equipment in get_all_equipped(player))
        if player.PC.known_songs.get('light') > 0:
            bonus = bonus + 70
        if player.PC.map_type != 'darkness':
            return max(2, self.base_brightness + bonus)
        else:
            return max(2, self.base_brightness + bonus - 4)

    @property
    def max_pp(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_pp for equipment in get_all_equipped(player))
        return self.base_max_pp + bonus

    @property
    def agility(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.agility for equipment in get_all_equipped(player))
        return self.base_agility + bonus

    @property
    def dexterity(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.dexterity for equipment in get_all_equipped(player))
        return self.base_dexterity + bonus

    @property
    def strength(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.strength for equipment in get_all_equipped(player))
        return self.base_strength + bonus

    def heal_pp(self, amount):
        #heal by the given amount, without going over the maximum
        self.pp += amount
        if self.pp > self.max_pp:
            self.pp = self.max_pp

    def interact(self, thing):
        global dungeon_level, game_state
        if thing != None:
            if thing.special_flag == True:
                if thing.name == 'orb':
                    libtcod.console_set_color_control(libtcod.COLCTRL_3,libtcod.light_green,libtcod.black)
                    setup = '%c%s%c'%(libtcod.COLCTRL_3, 'orb of experience!', libtcod.COLCTRL_STOP)
                    base_message = 'You collect an ' + setup
                    message(base_message)
                    player.PC.experience += 1
                    player.PC.total_experience += 1
                    objects.remove(thing)
                    render_all()

                    if sound_state == True:
                        explosion_sound.play()

                    if player.PC.total_experience >= 27:
                        message('You collected 27 orbs of experience and won!', libtcod.light_green)
                        message('Your quest lasted for ' + str(turncount) + ' turns.', libtcod.white)
                        message('You can restart by pressing <R> [capital <r>].', libtcod.light_blue)
                        game_state = 'dead'
                        save_game()
                        save_meta()

                elif thing.name == 'upstairs':
                    player.PC.old_dungeon_level = dungeon_level
                    dungeon_level = 98
                    next_level()
                    libtcod.console_set_color_control(libtcod.COLCTRL_4,libtcod.light_violet,libtcod.black)
                    setup = '%c%s%c'%(libtcod.COLCTRL_4, 'Lotus.', libtcod.COLCTRL_STOP)
                    base_message = 'You return to the town called ' + setup
                    message(base_message)
                    
                elif thing.name == 'stairs':
                    base_message = ''
                    if dungeon_level == 99:
                        base_message = 'You portal back into the dungeon and arrive on floor '
                        dungeon_level = player.PC.old_dungeon_level
                    else:
                        base_message = 'You take the stairs from floor ' + str(dungeon_level) + ' to '
                    player.PC.old_dungeon_level = dungeon_level 
                    next_level()
                    libtcod.console_set_color_control(libtcod.COLCTRL_5,libtcod.orange,libtcod.black)
                    setup = '%c%s%c'%(libtcod.COLCTRL_5, (str(dungeon_level)+'.'), libtcod.COLCTRL_STOP)
                    message(base_message+setup)

                elif thing.name == 'pit':
                    base_message = 'You fall down the pit!'
                    player.PC.old_dungeon_level = dungeon_level
                    next_level()
                    damage = libtcod.random_get_int(dungeon_seed, 5, player.fighter.max_hp+5)
                    player.fighter.take_damage(damage)
                    base_message = base_message + ' You take ' + str(damage) + ' damage.'
                    if player.fighter.hp <= 0:
                        base_message = base_message + ' You die from the fall...'
                    message(base_message, libtcod.light_grey)

                elif thing.name == 'temple':
                    if player.PC.experience > 0:
                        player.PC.interaction_checker.append('temple')
                    else:
                        message('You need experience to spend time at the temple...', libtcod.orange)

                elif thing.name == 'blacksmith':
                    if player.PC.experience > 0:
                        player.PC.interaction_checker.append('blacksmith')
                    else:
                        message('You need experience to spend time at the blacksmith...', libtcod.orange)

                elif thing.name == 'training grounds':
                    if player.PC.experience > 0:
                        player.PC.interaction_checker.append('training grounds')
                    else:
                        message('You need experience to spend time at the training grounds...', libtcod.orange)

                save_game()

    def player_turn(self):
        #updates the player's turn and does all necessary turn-to-turn actions (health regen, food up, etc)
        global turncount, MONSTER_COUNT, dungeon_level, TORCH_RADIUS, fov_recompute, map, identified_objects

        self.ability_counter = 0
        self.mechanic_check = 0
        turncount = turncount + 1
        self.floor_turncount += 1

        if turncount % 10 == 1:
            player.fighter.heal(1)

##        player.fighter.status['Telepathy'] += 10

        cloud_manage()

        ring = get_equipped_in_slot('ring')

        if ring != None:
            if ring.owner.name == 'ring of telepathy':
                if libtcod.random_get_int(dungeon_seed, 1, 3) == 3:
                    player.fighter.status['Telepathy'] += 1
            elif ring.owner.name == 'ring of purity':
                player.fighter.dot_tick()
            elif ring.owner.name == 'ring of the assassin':
                for object in objects:
                    if object.fighter and object.ai:
                        object.ai.tracking -= 2

        for object in objects:
            object.took_turn = False

class Fighter:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, dmg, attack_range, dmg_clumps, last_direction=0, dmg_bonus=0, armor=0, describe_attack=None, comes_into_view=None, death_function=None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_dmg = dmg
        self.death_function = death_function
        self.describe_attack = describe_attack
        self.comes_into_view = 0
        self.base_attack_range = attack_range
        self.invinc_ticks = 0
        self.last_direction = last_direction
        self.status = {'Stuck':0, 'Floating':0, 'Damage Taken':0, 'Attack Limit':0, 'Telepathy':0, 'Frozen':0, 'Acidic':0, 'Cursed':0, 'Faerie Fire':0, 'Hypothermia':0, 'Confused':0}
        self.poison_ticks = 0
        self.base_armor = armor
        self.base_dmg_clumps = dmg_clumps
        self.base_dmg_bonus = dmg_bonus

    @property
    def dmg(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.dmg for equipment in get_all_equipped(self.owner))
        return self.base_dmg + bonus

    @property
    def dmg_clumps(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.dmg_clumps for equipment in get_all_equipped(self.owner))
        return self.base_dmg_clumps + bonus

    @property
    def dmg_bonus(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.enchant_level for equipment in get_all_equipped(self.owner))
        return self.base_dmg_bonus + bonus

    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    @property
    def armor(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.armor for equipment in get_all_equipped(self.owner))
        return self.base_armor + bonus

    @property
    def attack_range(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.attack_range for equipment in get_all_equipped(self.owner))
        if self.owner == player:
            if bonus >= self.base_attack_range:
                return bonus
            else:
                return self.base_attack_range
        else:
            return self.base_attack_range

    def attack(self, target):
        global TORCH_RADIUS, fov_recompute
        #a simple formula for melee attacks
        if self.status.get('Frozen') == 0 and self.dmg > 0:
            name = None

            hit_chance = 0
            
            crit_chance = 0

            clump_check = self.dmg_clumps

            dmg_check = self.dmg

            hit_roll = libtcod.random_get_int(dungeon_seed, 1, 100)
            
            if self.owner == player:
                dmg_check -= 1
                name = 'You'
                hit_chance = 75 + (self.owner.PC.dexterity)
                if hit_chance >= hit_roll:
                    crit_chance = (hit_chance-hit_roll)//2
                    if crit_chance >= libtcod.random_get_int(dungeon_seed, 1, 100):
                        clump_check += 1 #if the player crits with excess Dexterity, give them an extra dice

                if self.owner.PC.strength >= libtcod.random_get_int(dungeon_seed, 1, 100):
                    dmg_check += 1 #if the players crits with excess Strength, give them an extra pip on each dice                                                                    
            else:
                name = self.owner.name
                hit_chance = 85
                if target == player:
                    hit_chance = hit_chance - player.PC.agility

            if hit_chance < 25:
                hit_chance = 25

            message_color = libtcod.white

            combat_color = None

            alt_combat_color = None

            hit_message = ' hit '

            distance = 0

            damage = 0

            if hit_chance >= hit_roll:
                if self.dmg_bonus > 0:
                    setup_rolls = str(clump_check) + 'd' + str(dmg_check) + '+' + str(self.dmg_bonus)
                else:
                    setup_rolls = str(clump_check) + 'd' + str(dmg_check)
                while clump_check > 0:
                    clump_check -= 1
                    damage += libtcod.random_get_int(dungeon_seed, 1, dmg_check)
                else:
                    damage += self.dmg_bonus
                    damage_message = ' for ' + str(damage) + '.'
                    libtcod.console_set_color_control(libtcod.COLCTRL_2,libtcod.grey,libtcod.black)
                    setup = '%c(%s)%c'%(libtcod.COLCTRL_2, setup_rolls, libtcod.COLCTRL_STOP)
                    damage_message = damage_message + setup

                    if self.owner == player:
                        if sound_state == True:
                            hit_sound.play()
                            
                        hit_message = ' hit '

                        weapon = get_equipped_in_slot('weapon')

                        if target.fighter.invinc_ticks == 0:
                            if target.boss and 'Duke of' not in target.name and 'Bell Keeper' is not target.name:
                                if weapon == None:
                                    message('You punch ' + target.name + damage_message, message_color)
                                else:
                                    message('You hit ' + target.name + damage_message, message_color)
                            else:
                                if weapon == None:
                                    message('You punch the ' + target.name + damage_message, message_color)
                                else:
                                    message('You hit the ' + target.name + damage_message, message_color)
                    else:
                        if target.fighter.invinc_ticks == 0:
                            if self.describe_attack != None:
                                if target == player and self.owner.boss and self.owner.name != 'sand worm':
                                    if 'Duke of' in name or 'Bell Keeper' is name:
                                        message('The ' + name + ' ' + self.describe_attack + ' you' + damage_message, message_color)
                                    else:
                                        message(name.capitalize() + ' ' +  self.describe_attack + ' you' + damage_message, message_color)

                                elif target == player:
                                    message('The ' + name + ' ' +  self.describe_attack + ' you' + damage_message, message_color)
                                else:
                                    message('The ' + name + ' ' +  self.describe_attack + ' the ' + target.name + damage_message, message_color)
                            else:
                                message('The ' + name + ' hits you ' + damage_message, message_color)

                    int(damage)
                    target.fighter.take_damage(damage)
            else:
                if self.owner == player:
                    message('You miss.(' + str(hit_chance) + ' vs ' + str(hit_roll) + ')', libtcod.grey)
                else:
                    message('The ' + name + ' misses.(' + str(hit_chance) + ' vs ' + str(hit_roll) + ')', libtcod.grey)

    def dot_tick(self):
        combat_color = None
        name = None
        if self.hp > 0:
            if self.poison_ticks > 0:
                self.poison_ticks -= 1
                if self.owner.effect_flag == False:
                    self.take_damage(2)
                else:
                    self.take_damage(1)

            if self.invinc_ticks > 0:
                self.owner.bg_color = libtcod.desaturated_yellow
                self.invinc_ticks -=1
                if self.invinc_ticks == 0:
                    self.owner.bg_color = None

            if self.status.get('Damage Taken') > 0:
                if self.status.get('Damage Taken') > 1:
                    self.status['Damage Taken'] = 1
                elif self.status.get('Damage Taken') == 1:
                    self.status['Damage Taken'] = 0
                    self.owner.color = self.owner.original_color
                else:
                    self.status['Damage Taken'] = 0
                    self.owner.color = self.owner.original_color

            if self.status.get('Stuck') > 0:
                self.status['Stuck'] -= 1

            if self.status.get('Confused') > 0:
                self.status['Confused'] -= 1

            if self.status.get('Attack Limit') > 0:
                self.status['Attack Limit'] -= 1

            if self.status.get('Acidic') > 0:
                self.status['Acidic'] -= 1
                if self.status.get('Acidic') > 0:
                    self.owner.bg_color = libtcod.light_chartreuse*libtcod.random_get_float(0, 0.67, 1.33)
                else:
                    self.owner.bg_color = self.owner.original_bg_color

    def cast_knockback(self, knock_x, knock_y, distance):
        global fov_recompute
        check_x = self.owner.x
        check_y = self.owner.y
        try:
            if knock_x > self.owner.x and knock_y == self.owner.y:
                while distance > 0:
                    self.owner.move(-1, 0)
                    distance -= 1
            elif knock_x == self.owner.x and knock_y > self.owner.y:
                while distance > 0:
                    self.owner.move(0, -1)
                    distance -= 1
            elif knock_x < self.owner.x and knock_y == self.owner.y:
                while distance > 0:
                    self.owner.move(1, 0)
                    distance -= 1
            elif knock_x == self.owner.x and knock_y < self.owner.y:
                while distance > 0:
                    self.owner.move(0, 1)
                    distance -= 1
            elif knock_x > self.owner.x and knock_y > self.owner.y:
                while distance > 0:
                    self.owner.move(-1, -1)
                    distance -= 1
            elif knock_x > self.owner.x and knock_y < self.owner.y:
                while distance > 0:
                    self.owner.move(-1, 1)
                    distance -= 1
            elif knock_x < self.owner.x and knock_y > self.owner.y:
                while distance > 0:
                    self.owner.move(1, -1)
                    distance -= 1
            elif knock_x < self.owner.x and knock_y < self.owner.y:
                while distance > 0:
                    self.owner.move(1, 1)
                    distance -= 1
            elif knock_x == self.owner.x and knock_y == self.owner.y:
                while distance > 0:
                    self.owner.move(libtcod.random_get_int(dungeon_seed, -1, 1), libtcod.random_get_int(dungeon_seed, -1, 1))
                    distance -= 1
        except Exception as ex:
            logging.exception('Caught an error')

        if self.owner == player:
            fov_recompute = True

    def take_damage(self, damage):
        #apply damage if possible

        if damage < 0:
            damage = 1

        if self.owner != player:
            ring = get_equipped_in_slot('ring')
            if ring != None:
                if ring.owner.name == 'ring of vampirism':
                    player.fighter.heal(1)
                elif ring.owner.name == 'ring of the mageblade':
                    player.PC.heal_pp(1)

        if self.invinc_ticks > 0:
            damage = 0
            if self.owner == player:
                message('You shrug off the attack!', libtcod.gold)
            else:
                message(self.owner.name.capitalize() + ' is immune to damage!', libtcod.red)

        if damage > 0:
            self.status['Damage Taken'] += damage
            self.hp -= damage

            if self.owner.ai:
                self.owner.ai.tracking += libtcod.random_get_int(dungeon_seed, 1, 3)
                if self.hp <= 0:
                    if 'returns' in self.owner.ai.tags:
                        if libtcod.random_get_int(dungeon_seed, 1, 3) != 1:
                            message('The ' + self.owner.name + ' refuses to die!', libtcod.red)
                            self.hp = 1
                            
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def heal_mp(self, amount):
        #heal by the given amount, without going over the maximum
        self.mp += amount
        if self.mp > self.max_mp:
            self.mp = self.max_mp

    def max_heal(self, amount):
        #adjust maximum hit points by the given amount and force current hit points to adjust
        self.max_hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    def __init__(self, mob_flag=0, tracking=0, attack_chance=0, special_chance=0, tags=[]):
        self.mob_flag = mob_flag
        self.tracking = tracking
        self.attack_chance = attack_chance
        self.special_chance = special_chance
        self.tags = tags

    def wander_around(self):
        monster = self.owner
        monster.move(libtcod.random_get_int(dungeon_seed, -1, 1), libtcod.random_get_int(dungeon_seed, -1, 1))

    def move_around(self):
        monster = self.owner
        numOfMoves = 1
        if 'sprints' in self.tags:
            if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
                numOfMoves += 1
        if 'crawls' in self.tags:
            if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
                numOfMoves -= 1
        try:
            while numOfMoves > 0:
                numOfMoves -= 1
                if 'shouts' not in self.tags or ('shouts' in self.tags and libtcod.random_get_int(dungeon_seed, 1, 8) != 8):
##                    direction_multi = 1
##                    if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
##                        if 'evades' in self.tags:
##                            direction_multi = -1

                    if self.owner.distance_to(player) >= 2:
                        if 'evades' in self.tags:
                            if libtcod.random_get_int(dungeon_seed, 1, 3) != 1:
                                self.owner.move_towards(player.x*-1, player.y*-1)
                            else:
                                self.owner.move_astar(player)
                        else:
                            self.owner.move_astar(player)

                    if 'flutters' in self.tags: #mobs with the flutter flag have a 1-in-3 chance of moving around randomly after their standard move
                        if libtcod.random_get_int(dungeon_seed, 1, 3) == 3:
                            monster.move(libtcod.random_get_int(dungeon_seed, -1, 1), libtcod.random_get_int(dungeon_seed, -1, 1))

                    if 'slurps' in self.tags:
                        for object in objects:
                            if object.item and object.x == self.owner.x and object.y == self.owner.y:
                                objects.remove(object)
                                if libtcod.map_is_in_fov(fov_map, self.owner.x, self.owner.y):
                                    message(self.owner.name.capitalize() + ' consumes the ' + object.name + '.')
                                else:
                                    message('You hear a slurping sound.')

                else:
                    if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
                        if monster.name != 'giant wolf':
                            message('The ' + monster.name + ' shouts for help!', libtcod.white)
                        else:
                            message('The ' + monster.name + ' howls!', libtcod.white)
                        for object in objects:
                            if object.fighter and object.effect_flag == False and object != player and object.fighter.hp > 0:
                                object.ai.tracking += libtcod.random_get_int(dungeon_seed, 4, 6)

        except Exception as ex:
            logging.exception('Caught an error')

    def mob_hit(self): #tells the mob to make an attack and triggers any "on attack" effects
        monster = self.owner
        if 'nurse' not in self.tags:
            self.owner.fighter.attack(player)
        else:
            random_doctor = libtcod.random_get_int(dungeon_seed, 1, 100) #70% chance to heal for 1d6, 20% chance to cause blood poisoning, and 10% chance to disappear
            if random_doctor > 30: #heal
                player.fighter.heal(libtcod.random_get_int(dungeon_seed, 1, 6))
                message('The ' + self.owner.name + ' makes you feel right as rain.', libtcod.cyan)
            elif random_doctor > 10: #blood poisoning
                random_blood_poisoning = libtcod.random_get_int(dungeon_seed, 1, 6)
                player.fighter.max_heal(random_blood_poisoning*-1)
                player.fighter.take_damage(random_blood_poisoning)
                message('The ' + self.owner.name + ' accidentally reused a needle...Ouch!', libtcod.cyan)
            else: #despawn
                message('The ' + self.owner.name + ' leaves for an emergency house call!', libtcod.cyan)
                try:
                    self.owner.x = libtcod.random_get_int(dungeon_seed, 1, SCREEN_WIDTH-10)
                    self.owner.y = libtcod.random_get_int(dungeon_seed, 1, SCREEN_HEIGHT-10)
                except Exception as ex:
                    logging.exception('Caught an error')
                cast_demolish(self.owner.x, self.owner.y)
                self.tracking = 0
            
        monster.ai.tracking += libtcod.random_get_int(dungeon_seed, 1, 3)

        if 'arbites' in self.tags:
            player_hp_base = player.fighter.hp
            player_pp_base = player.PC.pp
            player.fighter.hp = player_pp_base
            player.PC.pp = player_hp_base

        if 'knockbacks' in self.tags:
            if libtcod.random_get_int(dungeon_seed, 1, 4) != 1:
                knockback_distance = 1
                message('The ' + self.owner.name + '\'s attack knocks you back.')
                if monster.x == player.x:
                    if monster.y > player.y:
                        for object in objects:
                            if monster.x == object.x and monster.y > object.y and object.fighter:
                                object.fighter.cast_knockback(monster.x, monster.y, knockback_distance)

                    elif player.y > monster.y:
                        for object in objects:
                            if monster.x == object.x and object.y > monster.y and object.fighter:
                                object.fighter.cast_knockback(monster.x, monster.y, knockback_distance)

                elif monster.y == player.y:
                    if monster.x > player.x:
                        for object in objects:
                            if monster.y == object.y and monster.x > object.x and object.fighter:
                                object.fighter.cast_knockback(monster.x, monster.y, knockback_distance)

                    elif player.x > monster.x:
                        for object in objects:
                            if monster.y == object.y and object.x > monster.x and object.fighter:
                                object.fighter.cast_knockback(monster.x, monster.y, knockback_distance)

        if 'displaces' in self.tags:
            try:
                blinks = libtcod.random_get_int(dungeon_seed, 11, 99)
                while blinks > 0:
                    blinks -= 1
                    player.move(libtcod.random_get_int(dungeon_seed, -1, 1), libtcod.random_get_int(dungeon_seed, -1, 1))
            except Exception as ex:
                logging.exception('Caught an error')

        if 'mana burns' in self.tags:
            if player.PC.pp > 0:
                burn_amount = (player.PC.pp // 2) + 1
                player.PC.pp -= burn_amount
                message('The ' + self.owner.name + ' burns ' + str(burn_amount) + ' of your power points.')

                if player.PC.pp < 0:
                    player.PC.pp = 0
            else:
                self.owner.fighter.dmg += 1
                print str(self.owner.fighter.dmg_clumps) + 'd' + str(self.owner.fighter.dmg)

        if 'roots' in self.tags:
            if libtcod.random_get_int(dungeon_seed, 1, 10) != 1:
                player.fighter.status['Stuck'] += 1

    def mob_special(self):
        global fov_recompute
        monster = self.owner

        if 'zaps' in self.tags:
            if self.owner.x == player.x or self.owner.y == player.y:
                clumps = 4
                damage_total = 0
                try:
                    while clumps > 0:
                        clumps -= 1
                        damage_total += libtcod.random_get_int(dungeon_seed, 1, 3)
                    else:
                        message('The ' + self.owner.name + ' zaps you for ' + str(damage_total) + '.')
                        player.fighter.take_damage(damage_total)
                except Exception as ex:
                    logging.exception('Caught an error')

        if 'breathes fire' in self.tags:
            if self.owner.x == player.x or self.owner.y == player.y:
                clumps = 3
                damage_total = 0
                cast_demolish(player.x, player.y)
                try:
                    while clumps > 0:
                        clumps -= 1
                        damage_total += libtcod.random_get_int(dungeon_seed, 1, 6)
                    else:
                        message('The ' + self.owner.name + ' breathes fire!', libtcod.red)
                        for object in objects:
                            if object.fighter and object.fighter.hp > 0 and object != self.owner and object.distance_to(player) <= 2 and not (object.ai and 'breathes fire' in object.ai.tags):
                                if object == player:
                                    message('You were scorched by the ' + self.owner.name + '\'s fire for ' + str(damage_total) + '.')
                                else:
                                    message(object.name.capitalize() + ' was scorched by the ' + self.owner.name + '\'s fire for ' + str(damage_total) + '.')
                                object.fighter.take_damage(damage_total)
                except Exception as ex:
                    logging.exception('Caught an error')                        

    def take_turn(self):
        #a basic monster takes its turn. if you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            if monster.ai.special_chance >= libtcod.random_get_int(dungeon_seed, 1, 100):
                if monster.distance_to(player) < 2:
                    monster.ai.mob_hit()
                elif monster.x == player.x or monster.y == player.y:
                    monster.ai.mob_special()
            else:
                if monster.distance_to(player) < 2: #mobs don't waste their time attacking if the player is frozen
                    monster.ai.mob_hit()
                elif monster.distance_to(player) <= monster.fighter.attack_range:
                    if monster.ai.attack_chance >= libtcod.random_get_int(dungeon_seed, 1, 100):
                        if monster.x == player.x or monster.y == player.y:
                            monster.ai.mob_hit()
                        else:
                            self.move_around()
                    else:
                        self.move_around()
                else:
                    self.move_around()
        else:
            if monster.ai.tracking > 0:
                self.move_around()
                monster.ai.tracking -= 1
            elif 'wanders' in self.tags:
                self.wander_around()

        if 'swims' in self.tags:
            try:
                if libtcod.random_get_int(dungeon_seed, 1, 3) != 1:
                    check = True
                    pulse = 0
                    while check == True:
                        random_x = libtcod.random_get_int(dungeon_seed, -1, 1)
                        random_y = libtcod.random_get_int(dungeon_seed, -1, 1)
                        pulse += 1
                        if pulse != 9:
                            if map[self.owner.x+random_x][self.owner.y+random_y].flag != 'water':
                                map[self.owner.x+random_x][self.owner.y+random_y] = Tile(False, False, flag='water')
                                libtcod.map_set_properties(fov_map, self.owner.x+random_x, self.owner.y+random_y, not map[self.owner.x+random_x][self.owner.y+random_y].block_sight, not map[self.owner.x+random_x][self.owner.y+random_y].blocked)
                                check = False
                        else:
                            check = False
            except Exception as ex:
                logging.exception('Caught an error')

        if 'confuses' in self.tags:
            try:
                for object in objects:
                    if object.fighter and ((object.ai and 'confuses' not in object.ai.tags) or object == player) and object.distance_to(self.owner) <= 2:
                        object.fighter.status['Confused'] += libtcod.random_get_int(dungeon_seed, 2, 3)
            except Exception as ex:
                logging.exception('Caught an error')

        if 'regenerates' in self.tags:
            heal_amount = (self.owner.fighter.max_hp // 6) + 1
            self.owner.fighter.heal(heal_amount)

class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function=None, cast_function=None, dippable=False, powerup=False, skill=False, character=False, name_update=False, spell_type=None, plural_name=None, real_name=None, stacks=None, charges=None, mana_cost=None, cost=None, item_type=None, wand_chance=None, stop_function=None):
        self.use_function = use_function #depreciated, use magic() instead
        self.stop_function = stop_function #not currently used
        self.cast_function = cast_function #not currently used
        self.skill = skill #not currently used
        self.character = character #not currently used
        self.name_update = name_update #not currently used
        self.stacks = stacks #allows certain types of items (e.g., scrolls & potions) to stack in a single inventory slot (e.g., 3 potions of healing)
        self.charges = charges #not currently used
        self.powerup = powerup #not currently used
        self.cost = cost #not currently used
        self.item_type = item_type #is the item a potion, scroll, wand, spellbook, or sometihng else?
        self.mana_cost = mana_cost #actually PP cost
        self.wand_chance = wand_chance #chance for the wand to explode on usage
        self.real_name = real_name #used to remember the real name of an unidentified item (e.g., an ash wand might have a real_name of 'wand of striking')
        self.plural_name = plural_name #used to give custom pluralization to stacks of items (e.g., scrollS of pacification)
        self.dippable = dippable #whether or not the item can be dipped in fountains (used for inventory menu management)
        self.spell_type = spell_type #the actual spell being cast by the item (e.g., wand of striking has "spell_type='striking'"

    def pick_up(self, quiet=False):
        if len(inventory) >= 26:
            message('Your inventory is full.', libtcod.white)
        else:
            if sound_state == True:
                pickup_sound.play()
            #add to the player's inventory and remove from the map
            if self.powerup == False:
                equipment = self.owner.equipment
                if equipment:

                    if get_equipped_in_slot(equipment.slot) is None:
                        equipment.equip()
                    else:
                        equipment.toggle_equip()

                    if equipment.slot == 'weapon':
                        if self.name_update == False:
                            self.name_update = True
                else:
                    if quiet == False:
                        message('You picked up a ' + self.owner.name + '.')
                    if self.stacks == None:
                        inventory.append(self.owner)
                        objects.remove(self.owner)
                    else:
                        inventory.append(self.owner)
                        objects.remove(self.owner)
                        for obj in inventory:
                            if obj.name == self.owner.name and obj != self.owner:
                                self.stacks += obj.item.stacks
                                inventory.remove(obj)                    
            else:
                objects.remove(self.owner)
                self.use_function()

    def identify(self):
        global identified_objects
        if self.owner.name != self.real_name:
            check_others = self.owner.name
            message('Your ' + self.owner.name + ' is a ' + self.real_name + '!', libtcod.cyan)
            self.owner.name = self.real_name
            identified_objects.append(self.owner.name)
            for object in objects:
                if object.name == check_others:
                    object.name = self.real_name
            for object in inventory:
                if object.name == check_others:
                    object.name = self.real_name

    def dip(self, dipped_into=None):
        if dipped_into != None:
            if self.dippable == True:
                if self.item_type == 'wand':
                    self.identify()
                    message('You dip your ' + self.owner.name + ' into the ' + dipped_into.name + '. It explodes into a torrent of magical energy!', libtcod.cyan)
                    wand_explosion()
                    inventory.remove(self.owner)
                    objects.remove(dipped_into)
                    render_all()
                if self.item_type == 'spellbook':
                    self.identify()
                    message('You dip your ' + self.owner.name + ' into the ' + dipped_into.name + '. The magical aura surrounding the book dissipates and the pages turn blank.', libtcod.cyan)
                    inventory.remove(self.owner)
                    create_item('blank spellbook', player.x, player.y, False, 'start')
                    render_all()
                if self.item_type == 'scroll':
                    self.identify()
                    message('You dip your ' + self.owner.name + ' into the ' + dipped_into.name + '. The text fades away and all that remains is a blank scroll.', libtcod.cyan)
                    if self.stacks > 1:
                        self.stacks -= 1
                    else:
                        inventory.remove(self.owner)
                    create_item('blank scroll', player.x, player.y, False, 'start')
                    render_all()

    def magic(self):
        if self.owner.name != self.real_name: #used items are automatically identified
            self.identify() 
        monster = None #gathers information that might be used later, depending on the spell being cast
        thing = None
        
        if player.fighter.last_direction == 'up':
            monster = closest_monster(70, 'up')
        if player.fighter.last_direction == 'down':
            monster = closest_monster(70, 'down')
        if player.fighter.last_direction == 'left':
            monster = closest_monster(70, 'left')
        if player.fighter.last_direction == 'right':
            monster = closest_monster(70, 'right')

        if player.fighter.last_direction == 'up':
            thing = closest_object(70, 'up')
        if player.fighter.last_direction == 'down':
            thing = closest_object(70, 'down')
        if player.fighter.last_direction == 'left':
            thing = closest_object(70, 'left')
        if player.fighter.last_direction == 'right':
            thing = closest_object(70, 'right')

        type_message = ''

        if self.item_type == 'wand':
            type_message = 'You zap a wand of ' + self.spell_type + '. '
        elif self.item_type == 'spellbook':
            type_message = 'You read from a spellbook of ' + self.spell_type + '. '
        elif self.item_type == 'scroll':
            type_message = 'You read from a scroll of ' + self.spell_type + '. '
        else:
            type_message = 'Error 2 (item type missing). '

        if self.spell_type == 'striking': #attacks a distant for damage equal to the player's current combat step
            if monster != None:
                libtcod.console_set_color_control(libtcod.COLCTRL_1,libtcod.orange,libtcod.black)
                setup = '%c%s%c'%(libtcod.COLCTRL_1, monster.name, libtcod.COLCTRL_STOP)
                base_message = 'You zap the ' + setup + ' for '
                damage_value = libtcod.random_get_int(dungeon_seed, 1, ((player.fighter.dmg_clumps*player.fighter.dmg)-1)*2)

                monster.fighter.take_damage(damage_value)

                message(base_message + str(damage_value) + '.', libtcod.white)

        elif self.spell_type == 'pacification': #makes all enemies unable to track the the player for 15-30 turns and increases their chance to do something special (usually: "do nothing")
            for object in objects:
                if object.fighter and object.fighter.hp > 0 and object.ai != None:
                    object.ai.tracking = libtcod.random_get_int(dungeon_seed, -90, -45)
                    object.ai.special_chance += libtcod.random_get_int(dungeon_seed, 2, 10)

            libtcod.console_set_color_control(libtcod.COLCTRL_1,libtcod.orange,libtcod.black)
            setup = '%c%s%c'%(libtcod.COLCTRL_1, 'dungeon', libtcod.COLCTRL_STOP)
            message(type_message + 'Tranquility fills the ' + setup + '.', libtcod.fuchsia)

        elif self.spell_type == 'digging':
            base_message = 'A magical bolt rips out, tearing the earth asunder.'
            if player.fighter.last_direction == 'up':
                for new_y in range(player.y-8, player.y):
                    if libtcod.map_is_in_fov(fov_map, player.x, new_y):
                        cast_demolish(player.x, new_y)
            elif player.fighter.last_direction == 'down':
                for new_y in range(player.y, player.y+8):
                    if libtcod.map_is_in_fov(fov_map, player.x, new_y):
                        cast_demolish(player.x, new_y)
            elif player.fighter.last_direction == 'left':
                for new_x in range(player.x-8, player.x):
                    if libtcod.map_is_in_fov(fov_map, new_x, player.y):
                        cast_demolish(new_x, player.y)
            elif player.fighter.last_direction == 'right':
                for new_x in range(player.x, player.x+8):
                    if libtcod.map_is_in_fov(fov_map, new_x, player.y):
                        cast_demolish(new_x, player.y)                
            else:
                create_special('pit', player.x, player.y)
                base_message = base_message + ' The bolt strikes the ground beneath you. A pit appears!'

            if thing != None:
                if thing.special_flag and thing.name != 'pit':
                    objects.remove(special)
                    base_message = base_message + ' The bolt strikes the ' + thing.name + ' and destroys it.'

            if monster != None:
                monster.fighter.take_damage(1)
                base_message = base_message + ' The bolt hits the ' + monster.name + ' for 1.'

            render_all()
            message(type_message + base_message, libtcod.fuchsia)

        elif self.spell_type == 'cancellation':
            if monster != None:
                libtcod.console_set_color_control(libtcod.COLCTRL_1,libtcod.orange,libtcod.black)
                for object in objects:
                    if object.ai and object.distance_to(monster) <= 2:
                        if 'cancelled' in object.ai.tags:
                            if object.fighter:
                                object.fighter.take_damage(object.fighter.hp*6) #kill enemies that have the 'cancelled' tag (i.e., vortices, will-o'-the-wisps, and shadows)
                        del object.ai.tags[:]
                        object.ai.tracking = 0
                        setup = '%c%s%c'%(libtcod.COLCTRL_1, object.name, libtcod.COLCTRL_STOP)
                        base_message = 'You cancel the ' + setup + '.'
                        message(base_message, libtcod.white)

        elif self.spell_type == 'healing':
            clumps = 3
            healing_amount = 0
            while clumps > 0:
                clumps -= 1
                healing_amount += libtcod.random_get_int(dungeon_seed, 1, 6)
            else:
                player.fighter.heal(healing_amount)
                message('You heal for ' + str(healing_amount) + '.')
        
    def use(self):
        if self.use_function is None and self.mana_cost == None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if (player.PC.pp >= self.mana_cost) or (self.mana_cost == None):
                if self.mana_cost != None:
                    self.magic()
                    player.PC.heal_pp(self.mana_cost*-1)
                if self.item_type != 'spellbook' and self.item_type != 'wand' and self.item_type != 'misc':
                    if self.stacks == None and self.charges == None:
                        inventory.remove(self.owner)
                    elif self.stacks > 1:
                        self.stacks -= 1
                    elif self.stacks == 1:
                        inventory.remove(self.owner)
                    elif self.charges > 1:
                        self.charges -= 1
                    elif self.charges == 1:
                        message('Your ' + self.owner.name + ' crumbles into dust.', libtcod.red)
                        inventory.remove(self.owner)
                elif self.item_type == 'wand':
                    if self.wand_chance >= libtcod.random_get_int(dungeon_seed, 1, 100):
                        message('Your ' + self.owner.name + ' explodes into a torrent of magical energy.', libtcod.cyan)
                        wand_explosion()
                        inventory.remove(self.owner)
                    else:
                        self.wand_chance = self.wand_chance * 2
                        if self.wand_chance <= 0:
                            self.wand_chance = libtcod.random_get_int(dungeon_seed, 1, 4)
                        if self.wand_chance >= 100:
                            self.wand_chance = 100
            elif self.mana_cost != None and self.mana_cost > player.PC.pp:
                message('You don\'t have enough magical power to use the ' + self.owner.name + '.', libtcod.white)

def wand_explosion():
    for object in objects:
        if libtcod.map_is_in_fov(fov_map, object.x, object.y) and object.fighter and object.fighter.hp > 0 and object.effect_flag == False:
            cast_demolish(object.x, object.y)
            object.fighter.take_damage(libtcod.random_get_int(dungeon_seed, 6, 36))

class Equipment:
    #an object that can be equipped, yielding bonuses. automatically adds the Item component.
    def __init__(self, slot, dmg=0, dmg_clumps=0, enchant_level=0, max_hp=0, max_mp=0, max_pp=0, cost=0, attack_range=0, armor=0, brightness=0, agility=0, dexterity=0, strength=0, use_function=None):
        self.dmg = dmg
        self.dmg_clumps = dmg_clumps
        self.max_hp = max_hp
        self.max_mp = max_mp
        self.attack_range = attack_range
        self.cost = cost
        self.max_pp = max_pp
        self.use_function = use_function
        self.slot = slot
        self.armor = armor
        self.brightness = brightness
        self.agility = agility
        self.dexterity = dexterity
        self.strength = strength
        self.enchant_level = enchant_level
        self.is_equipped = False

    def toggle_equip(self):  #toggle equip/dequip status
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self, silence=False):
        #if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()

        #equip object and show a message about it
        self.is_equipped = True
        merged_items.append(self.owner)
        objects.remove(self.owner)
        if silence == False:
            if self.slot == 'weapon':
                message('You wield the +' + str(self.enchant_level) + ' ' + self.owner.name + '.', libtcod.light_green)
            elif self.slot == 'ring':
                message('You slide the ' + self.owner.name + ' onto your right index finger.', libtcod.light_green)
            elif self.slot == 'chest':
                message('You begin wearing the ' + self.owner.name + '.', libtcod.light_green)
            elif self.slot == 'oil':
                message('You prepare the flask of ' + self.owner.name.lower() + '.', libtcod.light_green)
            elif self.slot == 'torch':
                message('You wield the ' + self.owner.name.lower() + ' in your off-hand.', libtcod.light_green)
            elif self.slot == 'belt':
                message('You lock the ' + self.owner.name + ' around your waist.', libtcod.light_green)
            elif self.slot == 'gloves':
                message('You slip the ' + self.owner.name + ' on.', libtcod.light_green)
            elif self.slot == 'helm':
                message('You place the ' + self.owner.name + ' on your head.', libtcod.light_green)

    def dequip(self, silence=False):
        #dequip object and show a message about it
        if not self.is_equipped: return
        self.is_equipped = False
        objects.append(self.owner)
        merged_items.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        if silence == False:
            if self.slot == 'weapon':
                message('You unwield the +' + str(self.enchant_level) + ' ' + self.owner.name + '.', libtcod.white)
            elif self.slot == 'ring':
                message('You slide the ' + self.owner.name + ' off of your right index finger.', libtcod.white)
            elif self.slot == 'chest':
                message('You stop wearing the ' + self.owner.name + '.', libtcod.white)
            elif self.slot == 'oil':
                message('You set the flask of ' + self.owner.name + ' down.', libtcod.white)
            elif self.slot == 'torch':
                message('You unwield the ' + self.owner.name.lower() + ' from your off-hand.', libtcod.light_green)
            elif self.slot == 'belt':
                message('You remove the ' + self.owner.name + ' from your waist.', libtcod.white)
            elif self.slot == 'gloves':
                message('You take the ' + self.owner.name + ' off.', libtcod.white)
            elif self.slot == 'helm':
                message('You remove the ' + self.owner.name + ' from your head.', libtcod.light_green)

def get_equipped_in_slot(slot):  #returns the equipment in a slot, or None if it's empty
    for obj in merged_items:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj):  #returns a list of equipped items
    if obj == player:
        equipped_list = []
        for item in merged_items:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []  #other objects have no equipment

def is_blocked(x, y):
    #first test the map tile
    if map[x][y].blocked:
        return True

    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

def create_room(room, flavor=None):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            if flavor == None:
                map[x][y] = Tile(False, False)
            elif flavor == 'grass' and libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                map[x][y] = Tile(False, True, flag='grass')
                
            if flavor == 'shop':
                if map[x-1][y].blocked:
                    map[x-1][y] = Tile(True, block_sight=True, flag='shop')

                if map[x+1][y].blocked:
                    map[x+1][y] = Tile(True, block_sight=True, flag='shop')

                if map[x][y-1].blocked:
                    map[x][y-1] = Tile(True, block_sight=True, flag='shop')

                if map[x][y+1].blocked:
                    map[x][y+1] = Tile(True, block_sight=True, flag='shop')

                if map[x-1][y-1].blocked:
                    map[x-1][y-1] = Tile(True, block_sight=True, flag='shop')

                if map[x+1][y-1].blocked:
                    map[x+1][y-1] = Tile(True, block_sight=True, flag='shop')

                if map[x-1][y+1].blocked:
                    map[x-1][y+1] = Tile(True, block_sight=True, flag='shop')

                if map[x+1][y+1].blocked:
                    map[x+1][y+1] = Tile(True, block_sight=True, flag='shop')

def create_circle_room(room, flavor=None):
    global map
    width = room.x2 - room.x1
    height = room.y2 - room.y1
    rx = (room.x1 + room.x2) / 2
    ry = (room.y1 + room.y2) / 2
    r = min(width, height) / 2
    for x in range(room.x1, room.x2 + 1):
            for y in range(room.y1, room.y2 + 1):
                    if math.sqrt((x - rx) ** 2 + (y - ry) ** 2) <= r:
                        if 0 <= x-1 < MAP_WIDTH and 1 <= y < MAP_HEIGHT:
                            if flavor == None:
                                map[x][y] = Tile(False, False)
                            elif flavor == 'grass' and libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                                map[x][y] = Tile(False, True, flag='grass')

                            if flavor == 'shop':
                                if map[x-1][y].blocked:
                                    map[x-1][y] = Tile(True, block_sight=True, flag='shop')

                                if map[x+1][y].blocked:
                                    map[x+1][y] = Tile(True, block_sight=True, flag='shop')

                                if map[x][y-1].blocked:
                                    map[x][y-1] = Tile(True, block_sight=True, flag='shop')

                                if map[x][y+1].blocked:
                                    map[x][y+1] = Tile(True, block_sight=True, flag='shop')

                                if map[x-1][y-1].blocked:
                                    map[x-1][y-1] = Tile(True, block_sight=True, flag='shop')

                                if map[x+1][y-1].blocked:
                                    map[x+1][y-1] = Tile(True, block_sight=True, flag='shop')

                                if map[x-1][y+1].blocked:
                                    map[x-1][y+1] = Tile(True, block_sight=True, flag='shop')

                                if map[x+1][y+1].blocked:
                                    map[x+1][y+1] = Tile(True, block_sight=True, flag='shop')


def create_h_tunnel(x1, x2, y, flavor=None):
    global map
    #horizontal tunnel. min() and max() are used in case x1>x2
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if 0 <= x-1 < MAP_WIDTH:
            if flavor == None:
                map[x][y] = Tile(False, False)
            elif flavor == 'grass' and libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                map[x][y] = Tile(False, True, flag='grass')

def create_v_tunnel(y1, y2, x, flavor=None):
    global map
    #vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if 1 <= y < 40:
            if flavor == None:
                map[x][y] = Tile(False, False)
            elif flavor == 'grass' and libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                map[x][y] = Tile(False, True, flag='grass')
                
def make_map(flavor=None):
    global map, objects, stairs, BOSS_COUNT, dungeon_level, MAP_HEIGHT, MAP_WIDTH, dungeon_seed, wallColor, wallColors, mobs_in_sight
    objects = [player]
    mobs_in_sight = []
    BOSS_COUNT = 0

    map_flavor = flavor

    shop_flip = 1
    circular_rooms = 0
    
    wallColor = random.choice(wallColors)

    if dungeon_level == 99:
        file = open('dat/maps/ranch.txt', 'r')
        map = [[Tile(True, block_sight=True)
                for y in range(MAP_HEIGHT)]
                   for x in range(MAP_WIDTH)]
        y = 0
        for line in file:
            x = 0
            for character in line:
##                if data.debug:
##                    print 'SEEDING MAP COORD: (' + str(x) + ',' + str(y) + ')'
                if character == ' ':
                    map[x][y] = Tile(False, False)
                if character == '@':
                    map[x][y] = Tile(False, False)
                    player.x, player.y = (x, y)
                if character == '>':
                    map[x][y] = Tile(False, False)
                    create_special('stairs', x, y)
                if character == '1':
                    map[x][y] = Tile(False, False)
                    create_special('temple', x, y)
                if character == '2':
                    map[x][y] = Tile(False, False)
                    create_special('blacksmith', x, y)
                if character == '3':
                    map[x][y] = Tile(False, False)
                    create_special('training grounds', x, y)
##                if character == 'T':
##                    map[x][y] = Tile(False, block_sight=True, flag='tree')
##                if character == '^':
##                    map[x][y] = Tile(True, block_sight=True, flag='mountain')
##                if character == '~':
##                    map[x][y] = Tile(True, block_sight=False, flag='deep water')
##                if character == '%':
##                    map[x][y] = Tile(False, block_sight=False, flag='sand')
##                if character == 'F':
##                    map[x][y] = Tile(False, block_sight=True, flag='deadwood')
##                if character == '1':
##                    map[x][y] = Tile(False, block_sight=False, flag='quest sand')
##                if character == '2':
##                    map[x][y] = Tile(False, block_sight=True, flag='quest deadwood')
##                if character == '3':
##                    map[x][y] = Tile(False, block_sight=False, flag='quest deep water')
##                if character == '4':
##                    map[x][y] = Tile(False, block_sight=True, flag='quest mountain')
                x += 1
            y += 1

        file.close()

    else:
        player.PC.alt_floor = False

        dungeon_zest = libtcod.random_get_int(dungeon_seed, 1, 8)

        #fill map with "blocked" tiles
        map = [[ Tile(True, True)
            for y in range(MAP_HEIGHT) ]
                for x in range(MAP_WIDTH) ]

        if dungeon_seed <= 4:
            for y in range(MAP_HEIGHT):
                for x in range(MAP_WIDTH):
                    check = False
                    if dungeon_seed == 1:
                        if (y-20 >= MAP_HEIGHT):
                            check = True
                    elif dungeon_seed == 2:
                        if (y//4 <= MAP_HEIGHT):
                            check = True
                    elif dungeon_seed == 3:
                        if (x-10 >= MAP_WIDTH):
                            check = True
                    elif dungeon_seed == 4:
                        if (x//5 <= MAP_WIDTH):
                            check = True
                    if check == True:
                        map[x][y] = Tile(False, False)
                    elif libtcod.random_get_int(dungeon_seed, 1, 3) == 3:
                        map[x][y] = Tile(False, False)

        crystal_jam = libtcod.random_get_int(dungeon_seed, 3, 7)

        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if not map[x][y].blocked:
                    if (1 < x < 58) and (1 < y < 38):
                        if (1.5/float(dungeon_level)) > libtcod.random_get_float(dungeon_seed, 0.0, 1.0):
                            map[x][y] = Tile(False, True, flag='grass')
                            if libtcod.random_get_int(dungeon_seed, 1, 256) == 256:
                                create_item(None, x, y)

                        if libtcod.random_get_int(dungeon_seed, 1, dungeon_level) > crystal_jam:
                            if map[x][y].flag is not 'grass':
                                if libtcod.random_get_int(dungeon_seed, 1, 3,) == 3:
                                    map[x][y] = Tile(True, False, flag='crystal')

                        if libtcod.random_get_int(dungeon_seed, 1, 512) == 512:
                            map[x][y] = Tile(False, False, flag='none')
                            create_item(None, x, y)
        rooms = []
        num_rooms = 0

        for r in range(MAX_ROOMS):
            w = 0
            h = 0
            room_flavor = None
            objects_flag = None
            if (libtcod.random_get_int(dungeon_seed, 1, dungeon_level+2) == 3):
                room_flavor = 'grass'
            special_dice = libtcod.random_get_int(dungeon_seed, 1, 40)
            if num_rooms == 0:
                w = libtcod.random_get_int(dungeon_seed, 3, 8)
                h = libtcod.random_get_int(dungeon_seed, 3, 8)
            elif num_rooms == 1:
                w = libtcod.random_get_int(dungeon_seed, 6, 9)
                h = libtcod.random_get_int(dungeon_seed, 6, 9)
                room_flavor = 'shop'
                objects_flag = 'pit'
            elif special_dice == 1:
                w = libtcod.random_get_int(dungeon_seed, 6, 14)
                h = libtcod.random_get_int(dungeon_seed, 6, 14)
                objects_flag = 'pit'
            elif special_dice == 2:
                w = libtcod.random_get_int(dungeon_seed, 3, 5)
                h = libtcod.random_get_int(dungeon_seed, 6, 14)
                objects_flag = 'pit'
            elif special_dice == 3:
                w = libtcod.random_get_int(dungeon_seed, 6, 14)
                h = libtcod.random_get_int(dungeon_seed, 3, 5)
                objects_flag = 'pit'
            else:
                w = libtcod.random_get_int(dungeon_seed, 3, 11)
                h = libtcod.random_get_int(dungeon_seed, 3, 11)

            if map_flavor != None:
                room_flavor = map_flavor

            #random position without going out of the boundaries of the map
            x = libtcod.random_get_int(dungeon_seed, 0, MAP_WIDTH - w - 6)
            y = libtcod.random_get_int(dungeon_seed, 0, MAP_HEIGHT - h - 6)

            #"Rect" class makes rectangles easier to work with
            new_room = Rect(x, y, w, h)

            #run through the other rooms and see if they intersect with this one
            failed = False
            try:
                for other_room in rooms:
                    if new_room.intersect(other_room):
                        failed = True
                        break
            except Exception as ex:
                logging.exception('Caught an error')

            if not failed:
                #this means there are no intersections, so this room is valid
                #"paint" it to the map's tiles
                if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
                    create_circle_room(new_room, room_flavor)
                    circular_rooms += 1
                else:
                    create_room(new_room, room_flavor)

                #center coordinates of new room, will be useful later
                (new_x, new_y) = new_room.center()
                if num_rooms > 0:
                    (prev_x, prev_y) = rooms[num_rooms-1].center()
                    place_objects(new_room, no_monsters=False, flag=objects_flag)
                    create_h_tunnel(prev_x, new_x, prev_y, map_flavor)
                    create_v_tunnel(prev_y, new_y, new_x, map_flavor)
                    if num_rooms == 1:
                        for y in range(new_y-1, new_y+1):
                            for x in range(new_x-1, new_x+1):
                                map[x][y] = Tile(False, False, flag=None)
                        create_special('orb', new_x, new_y)
                    if num_rooms == 2:
                        create_special('upstairs', new_x, new_y)
                    if num_rooms > 1:
                        if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
                            (prev_x2, prev_y2) = rooms[num_rooms-2].center()
                            create_h_tunnel(prev_x2, new_x, prev_y2, room_flavor)
                            create_v_tunnel(prev_y2, new_y, new_x, room_flavor)
                    if num_rooms > 2:
                        if libtcod.random_get_int(dungeon_seed, 1, 4) == 4:
                            (prev_x3, prev_y3) = rooms[num_rooms-3].center()
                            create_h_tunnel(prev_x3, new_x, prev_y3, room_flavor)
                            create_v_tunnel(prev_y3, new_y, new_x, room_flavor)
                    if num_rooms == 4:
                        for y in range(new_y-1, new_y+1):
                            for x in range(new_x-1, new_x+1):
                                map[x][y] = Tile(False, False, flag=None)
##                        stairs = Object(new_x, new_y, '>', 'stairs', libtcod.white, always_visible=True)
##                        objects.append(stairs)
##                        stairs.send_to_back()
                        create_special('stairs', new_x, new_y)
                        (prev_x4, prev_y4) = rooms[num_rooms-4].center()
                        create_h_tunnel(prev_x4, new_x, prev_y4, room_flavor)
                        create_v_tunnel(prev_y4, new_y, new_x, room_flavor)
                    if num_rooms > 4:
                        if libtcod.random_get_int(dungeon_seed, 1, 8) == 8:
                            (prev_x5, prev_y5) = rooms[num_rooms-5].center()
                            create_h_tunnel(prev_x5, new_x, prev_y5, room_flavor)
                            create_v_tunnel(prev_y5, new_y, new_x, room_flavor)
                else:
                    place_objects(new_room, no_monsters=True)
                    player.x = new_x
                    player.y = new_y
                    if dungeon_level == 1:
                        create_item('dagger', new_x, new_y, flavor='start')

                #finally, append the new room to the list
                rooms.append(new_room)
                num_rooms += 1             

        w = libtcod.random_get_int(dungeon_seed, 3, 8)
        h = libtcod.random_get_int(dungeon_seed, 3, 8)
        x = libtcod.random_get_int(dungeon_seed, 0, MAP_WIDTH - w - 6)
        y = libtcod.random_get_int(dungeon_seed, 0, MAP_HEIGHT - h - 6)

        new_room = Rect(x, y, w, h)

        create_room(new_room)
        place_objects(new_room, no_monsters=False)

def random_choice_index(chances):  #choose one option from list of chances, returning its index
    #the dice will land on some number between 1 and the sum of the chances
    global dungeon_seed
    dice = libtcod.random_get_int(dungeon_seed, 1, sum(chances))

    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        #see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1

def msgbox(header, options, width):
    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    height = 10

    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_set_default_background(window, libtcod.black)

    #print all the options
    y = header_height
    text = options
    libtcod.console_print_left_rect(window, 1, y, width, height, libtcod.BKGND_NONE, text)

    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    if header == '':
        header = None
    libtcod.console_print_frame(window, 0, 0, width, height, False, libtcod.BKGND_NONE, header)
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    #present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)
    libtcod.console_flush()

def random_choice(chances_dict):
    #choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()

    return strings[random_choice_index(chances)]

def from_dungeon_level(table):
    #returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

def place_objects(room, no_monsters, flag=None):
    global MONSTER_COUNT, BOSS_COUNT, dungeon_level, dungeon_seed, dukes

    #from_dungeon_level([[15, 3], [30, 5], [60, 7]]) example code
    #chance of each monster
    monster_chances = {}
    monster_chances['kiwi'] = from_dungeon_level([[100, 1], [50, 2], [25, 3], [0, 5]])
    monster_chances['goblin'] = from_dungeon_level([[50, 1], [25, 4], [0, 6]])
    monster_chances['hobgoblin'] = from_dungeon_level([[25, 1], [15, 5], [0, 7]])

    monster_chances['big bat'] = from_dungeon_level([[100, 2], [25, 3], [0, 9]])

    monster_chances['alchemical monstrosity'] = from_dungeon_level([[50, 3], [25, 4], [10, 5], [5, 10]])
    monster_chances['ogre'] = from_dungeon_level([[10, 3], [20, 4], [15, 6], [10, 8], [5, 12]])

    monster_chances['centaur'] = from_dungeon_level([[5, 5], [10, 6], [15, 7], [20, 8], [15, 9], [10, 10], [5, 13]])

    monster_chances['maiden of the lake'] = from_dungeon_level([[20, 6], [5, 12], [0, 16]])

    monster_chances['purple toad'] = from_dungeon_level([[20, 7], [10, 11], [5, 15]])
    monster_chances['will-o\'-the-wisp'] = from_dungeon_level([[20, 7], [10, 11], [5, 16]])

    monster_chances['jelly'] = from_dungeon_level([[20, 8], [10, 13], [5, 18]])

    monster_chances['vortex'] = from_dungeon_level([[9, 9]])

    monster_chances['zombie'] = from_dungeon_level([[20, 10], [25, 11], [50, 12], [25, 13], [10, 14], [5, 15]])

    monster_chances['quantum mechanic'] = from_dungeon_level([[10, 11], [5, 20]])

    monster_chances['nurse'] = from_dungeon_level([[5, 12]])
    monster_chances['troll'] = from_dungeon_level([[10, 12], [15, 13], [5, 18]])

    monster_chances['eldritch thing'] = from_dungeon_level([[10, 13], [25, 14], [5, 20]])

    monster_chances['shadow'] = from_dungeon_level([[10, 14], [5, 17]])

    monster_chances['ice beast'] = from_dungeon_level([[15, 15], [20, 16], [25, 17], [5, 18]])

    monster_chances['fiend'] = from_dungeon_level([[20, 16], [25, 17], [35, 18], [15, 19], [10, 20], [5, 21]])

    monster_chances['yacuruna'] = from_dungeon_level([[20, 17], [10, 20]])

    monster_chances['unicorn'] = from_dungeon_level([[10, 18]])

    monster_chances['xavite'] = from_dungeon_level([[20, 19], [10, 20]])

    monster_chances['redcap'] = from_dungeon_level([[50, 20], [25, 21], [10, 22], [5, 23]])

    monster_chances['lich'] = from_dungeon_level([[15, 21], [20, 22]])

    monster_chances['dragon'] = from_dungeon_level([[15, 22], [30, 23]])
                                            
    num_monsters = 0
    
    #choose random number of monsters
    if flag == 'pit':
        num_monsters = libtcod.random_get_int(dungeon_seed, 3, 4)
    else:
        if libtcod.random_get_int(dungeon_seed, 1, 10) != 1:
            num_monsters = 1
            if libtcod.random_get_int(dungeon_seed, 1, 3) == 10:
                num_monsters += 1

    if no_monsters == False:

        for i in range(num_monsters):
            #choose random spot for this monster
            x = libtcod.random_get_int(dungeon_seed, room.x1+1, room.x2-1)
            y = libtcod.random_get_int(dungeon_seed, room.y1+1, room.y2-1)

            #only place it if the tile is not blocked
            if not is_blocked(x, y):
                choice = random_choice(monster_chances)

                create_monster(choice, x, y)

def render_bar(x, y, total_width):
    global mobs_in_sight
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(1+1) / (float (1+1) * total_width))

    #render the background first
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_rect(panel, x, y, total_width, 1, False)

    #now render the bar on top
    libtcod.console_set_default_background(panel, libtcod.black)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False)

##    libtcod.console_set_default_foreground(panel, libtcod.dark_grey)
##    libtcod.console_vline(panel, PANEL_BUMP-1, 0, y+10)

    libtcod.console_set_default_foreground(msg_region, libtcod.dark_grey)
    libtcod.console_hline(msg_region, 0, 0, SCREEN_WIDTH-30)

    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x, y, libtcod.BKGND_NONE, libtcod.CENTER, 'HP')
    if (player.fighter.status.get('Damage Taken') > player.fighter.hp) or (player.fighter.hp == 1):
        libtcod.console_set_default_foreground(panel, libtcod.red)
    elif player.fighter.hp < player.fighter.max_hp:
        libtcod.console_set_default_foreground(panel, libtcod.yellow)
    else:
        libtcod.console_set_default_foreground(panel, libtcod.green)
    libtcod.console_print_ex(panel, x+3, y, libtcod.BKGND_NONE, libtcod.CENTER, str(player.fighter.hp))

    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x, y+1, libtcod.BKGND_NONE, libtcod.CENTER, 'MP')
    libtcod.console_set_default_foreground(panel, libtcod.green)
    libtcod.console_print_ex(panel, x+3, y+1, libtcod.BKGND_NONE, libtcod.CENTER, str(player.PC.pp))

    
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x, y+2, libtcod.BKGND_NONE, libtcod.CENTER, 'XP')
    libtcod.console_print_ex(panel, x+3, y+2, libtcod.BKGND_NONE, libtcod.CENTER, str(player.PC.experience))

    libtcod.console_print_ex(panel, x, y+4, libtcod.BKGND_NONE, libtcod.CENTER, 'AGI')
    libtcod.console_print_ex(panel, x+4, y+4, libtcod.BKGND_NONE, libtcod.CENTER, str(player.PC.agility) + '%')

    libtcod.console_print_ex(panel, x, y+5, libtcod.BKGND_NONE, libtcod.CENTER, 'DEX')
    libtcod.console_print_ex(panel, x+4, y+5, libtcod.BKGND_NONE, libtcod.CENTER, str(player.PC.dexterity) + '%')

    libtcod.console_print_ex(panel, x, y+6, libtcod.BKGND_NONE, libtcod.CENTER, 'STR')
    libtcod.console_print_ex(panel, x+4, y+6, libtcod.BKGND_NONE, libtcod.CENTER, str(player.PC.strength) + '%')

    if player.fighter.status.get('Acidic') > 0:
        libtcod.console_set_default_foreground(panel, libtcod.chartreuse)
        libtcod.console_print_ex(panel, x+4, y+10+len(mobs_in_sight), libtcod.BKGND_NONE, libtcod.CENTER, 'Acidic')

    if player.fighter.status.get('Confused') > 0:
        libtcod.console_set_default_foreground(panel, libtcod.yellow)
        libtcod.console_print_ex(panel, x+4, y+11+len(mobs_in_sight), libtcod.BKGND_NONE, libtcod.CENTER, 'Confused')

    if player.fighter.status.get('Stuck') > 0:
        libtcod.console_set_default_foreground(panel, libtcod.cyan)
        libtcod.console_print_ex(panel, x+4, y+12+len(mobs_in_sight), libtcod.BKGND_NONE, libtcod.CENTER, 'Stuck')

    monster_num = 0
    for monster in mobs_in_sight:
        libtcod.console_set_default_background(panel, monster.bg_color)
        libtcod.console_set_default_foreground(panel, monster.color)
        libtcod.console_print_ex(panel, x-1, y+8+monster_num, libtcod.BKGND_SET, libtcod.CENTER, str(monster.char))

        health_display = ''
        health_display = health_pips_counter(monster)

        libtcod.console_set_default_foreground(panel, libtcod.white)
        libtcod.console_print_ex(panel, x+4, y+8+monster_num, libtcod.BKGND_NONE, libtcod.CENTER, str(health_display))

        monster_num += 1

def health_pips_counter(monster):
    if monster in objects:
        if monster.fighter:
            if monster.fighter.hp > 0:
                monster_hp = float(monster.fighter.hp)
                monster_max_hp = float(monster.fighter.max_hp)
                if monster_hp == monster_max_hp:
                    return '[*****]'
                elif monster_hp >= monster_max_hp*0.8:
                    return '[****_]'
                elif monster_hp >= monster_max_hp*0.6:
                    return '[***__]'
                elif monster_hp >= monster_max_hp*0.4:
                    return '[**___]'
                else:
                    return '[*____]'

def render_all():
    global fov_map, color_dark_wall, color_light_wall, wallColor
    global color_dark_ground, color_light_ground
    global fov_recompute
    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, player.PC.brightness, FOV_LIGHT_WALLS, FOV_ALGO)

        #go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight and map[x][y].flag == None and map[x][y].blocked
                grass = map[x][y].flag == 'grass'
                crystal = map[x][y].flag == 'crystal'
                shop = map[x][y].flag == 'shop' and map[x][y].block_sight
                corpse_red = map[x][y].flag == 'corpse red'
                corpse_green = map[x][y].flag == 'corpse green'
                corpse_gold = map[x][y].flag == 'corpse gold'

                water = map[x][y].flag == 'water'

                if not visible:
                    #it's out of the player's FOV
                    if map[x][y].explored:
                        if shop:
                            libtcod.console_put_char_ex(con, x, y, '=', libtcod.Color(255, 215, 0)*libtcod.grey, libtcod.black)
                        elif wall:
                            if player.fighter.status.get('Acidic') > 0:
                                libtcod.console_put_char_ex(con, x, y, '=', libtcod.black, libtcod.black)
                            else:
                                libtcod.console_put_char_ex(con, x, y, '=', wallColor*libtcod.grey, libtcod.black)
                        elif grass:
                            libtcod.console_put_char_ex(con, x, y, '"', wallColor*libtcod.lightest_grey, libtcod.black)
                        elif crystal:
                            libtcod.console_put_char_ex(con, x, y, 30, wallColor*libtcod.dark_cyan, libtcod.black)
                        elif water:
                            libtcod.console_put_char_ex(con, x, y, '~', libtcod.Color(libtcod.random_get_int(0, 120, 180), libtcod.random_get_int(0, 120, 180), libtcod.random_get_int(0, 120, 180))*libtcod.grey, libtcod.blue*libtcod.random_get_float(0, 0.33, 0.67))
                        else:
                            libtcod.console_put_char_ex(con, x, y, '.', libtcod.Color(238, 238, 238)*libtcod.grey, libtcod.black)

                else:
                    #it's visible
                    if shop:
                        libtcod.console_put_char_ex(con, x, y, '=', libtcod.Color(libtcod.random_get_int(0, 230, 255), libtcod.random_get_int(0, 200, 215), 0), libtcod.black)
                    elif wall:
                        if player.fighter.status.get('Acidic') > 0:
                            libtcod.console_put_char_ex(con, x, y, '=', libtcod.black, libtcod.light_chartreuse*libtcod.random_get_float(0, 0.67, 1.33))
                        else:
                            libtcod.console_put_char_ex(con, x, y, '=', wallColor*libtcod.random_get_float(0, 1.0, 1.2)*libtcod.light_grey, libtcod.black)
                    elif corpse_red:
                        libtcod.console_put_char_ex(con, x, y, '%', libtcod.light_red, libtcod.black)
                    elif corpse_green:
                        libtcod.console_put_char_ex(con, x, y, ',', libtcod.light_red, libtcod.black)
                    elif corpse_gold:
                        libtcod.console_put_char_ex(con, x, y, '%', libtcod.gold, libtcod.black)
                    elif grass:
                        libtcod.console_put_char_ex(con, x, y, '"', wallColor*libtcod.random_get_float(0, 1.0, 1.5), libtcod.black)
                    elif crystal:
                        libtcod.console_put_char_ex(con, x, y, 30, wallColor*libtcod.random_get_float(0, 1.0, 1.5)*libtcod.light_cyan, libtcod.black)
                    elif water:
                        libtcod.console_put_char_ex(con, x, y, '~', libtcod.Color(libtcod.random_get_int(0, 120, 180), libtcod.random_get_int(0, 120, 180), libtcod.random_get_int(0, 120, 180)), libtcod.blue*libtcod.random_get_float(0, 0.67, 1.33))
                    else:
                        libtcod.console_put_char_ex(con, x, y, '.', libtcod.Color(238, 238, 238), libtcod.black)

                    if map[x][y].explored == False:
                        map[x][y].explored = True

    #draw all objects in the list, except the player. we want it to
    #always appear over all other objects! so it's drawn later.
    for object in objects:
        if object != player:
            object.draw()

        player.draw()


    #blit the contents of "con" to the root console

    #prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
    libtcod.console_set_default_background(msg_region, libtcod.black)
    libtcod.console_clear(msg_region)

    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(msg_region, color)
        libtcod.console_print_ex(msg_region, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1


    #create the UI
    render_bar(1, 1, BAR_WIDTH)

    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, PANEL_BUMP, SCREEN_HEIGHT, 0, 0, 0)
    libtcod.console_blit(msg_region, -1, 0, SCREEN_WIDTH-30, PANEL_HEIGHT, 0, 0, PANEL_Y)
    libtcod.console_blit(con, MAP_BUMP, 0, SCREEN_WIDTH, MAP_HEIGHT, 0, 0, 0)

def message(new_msg, color = libtcod.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, SCREEN_WIDTH-31)

    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == PANEL_HEIGHT-1:
            del game_msgs[0]

        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color) )

def player_move_or_attack(dx, dy, direction=None):
    global fov_recompute, turncount, dungeon_level
    check_x = player.x
    check_y = player.y
    libtcod.console_flush()

        #the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    x_attack = x + ((player.fighter.attack_range-1)*dx)
    y_attack = y + ((player.fighter.attack_range-1)*dy)
 
    #try to find an attackable object there
    target = None
    for object in objects:
        if (object.fighter or object.special_flag) and ((object.x == x_attack and object.y == y_attack) or (object.x == x and object.y == y)):
            target = object
            break

   #attack if target found, move otherwise

    if target is not None:
        if target.special_flag == False:
            player.fighter.attack(target)
        else:
            player.PC.interact(target)
    elif target is None:
        player.move(dx, dy)
        pick_me_up()
        if player.x == check_x and player.y == check_y:
            player.move(dx, 0)
            pick_me_up()
            if player.x == check_x and player.y == check_y:
                player.move(0, dy)
                pick_me_up()
        try:
            if map[x][y].blocked == False:
                fov_recompute = True
        except Exception as ex:
            logging.exception('Caught an error')

def pick_me_up():
    for object in objects:
        if player.x == object.x and player.y == object.y:
            if object.item:
                equipment = object.equipment
                if equipment:
                    object.item.pick_up()
                    break
                else:
                    object.item.pick_up()
                    break

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    height = len(options) + header_height + 1

    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_set_default_background(window, libtcod.black)

    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/3 - height/3
    if header == '':
        header = None
    libtcod.console_print_frame(window, 0, 0, width, height, False, libtcod.BKGND_NONE, header)
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    #present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    #convert the ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header, dip=False):
    #show a menu with each item of the inventory as an option
    inv_merged = inventory+merged_items
    if len(inv_merged) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        if dip == True:
            for item in inv_merged:
                if item.item.dippable == True:
                    text = item.name
                    if item.item.stacks > 1:
                        if item.item.plural_name != None:
                            if item.item.mana_cost == None:
                                text = str(item.item.stacks) + ' ' + item.item.plural_name
                            else:
                                if item.name != item.item.real_name:
                                    text = 'x' + str(item.item.stacks) + ' ' + item.name
                                else:
                                    text = str(item.item.stacks) + ' ' + item.item.plural_name + ' {' + str(item.item.mana_cost) + '}'
                        else:
                            text = 'x' + str(item.item.stacks) + ' ' + item.name
                    elif item.item.mana_cost != None and item.item.wand_chance == None:
                        if item.name != item.item.real_name: #check if identified
                            text = item.name
                        else:
                            text = item.name + ' {' + str(item.item.mana_cost) + '}'
                    elif item.item.mana_cost != None and item.item.wand_chance != None:
                        if item.name != item.item.real_name: #check if identified
                            text = item.name
                        else:
                            text = item.name + ' {' + str(item.item.mana_cost) + ', ' + str(item.item.wand_chance) + '%' + '>}'

                    if item.char != None:
                        if isinstance(item.char, int):
                            text = str(chr(item.char)) + ' ' + text
                        else:
                            text = item.char + ' ' + text
                            
                    options.append(text)
            if not options:
                options = ['No dippable items.']
                

        else:
            for item in inv_merged:
                text = item.name
                if item.item.stacks > 1:
                    if item.item.plural_name != None:
                        if item.item.mana_cost == None:
                            text = str(item.item.stacks) + ' ' + item.item.plural_name
                        else:
                            if item.name != item.item.real_name: #scrolls
                                text = 'x' + str(item.item.stacks) + ' ' + item.name
                            else:
                                text = str(item.item.stacks) + ' ' + item.item.plural_name + ' {' + str(item.item.mana_cost) + '}'
                    else:
                        text = 'x' + str(item.item.stacks) + ' ' + item.name
                elif item.item.mana_cost != None and item.item.wand_chance == None: #spellbooks
                    if item.name != item.item.real_name: #check if identified
                        text = item.name
                    else:
                        text = item.name + ' {' + str(item.item.mana_cost) + '}'
                elif item.item.mana_cost != None and item.item.wand_chance != None: #wands
                    if item.name != item.item.real_name: #check if identified
                        text = item.name
                    else:
                        text = item.name + ' {' + str(item.item.mana_cost) + ', ' + str(item.item.wand_chance) + '%' + '}'

                if item.item.stacks == 0 or item.item.stacks == None:
                    if item.equipment:
                        if item.equipment.slot == 'weapon':
                            text = '+' + str(item.equipment.enchant_level) + ' ' + text
                    vowels = ('a', 'e', 'i', 'o', 'u', 'y', 'A', 'E', 'I', 'O', 'U', 'Y')
                    if item.name.startswith(vowels):
                        text = 'An ' + text
                    else:
                        text = 'A ' + text

                if item in merged_items:
                    text = '<' + text + '>'

                if item.char != None:
##                    message("String with a %cblack%c word."%(libtcod.COLCTRL_1,libtcod.COLCTRL_STOP))
##                    text_test = ('%c<%ctext'%(libtcod.COLCTRL_1,libtcod.COLCTRL_STOP))
##                    text_test = (text_test + '%c>%c'%(libtcod.COLCTRL_1,libtcod.COLCTRL_STOP))
##                    message(text_test)
##                    message('%c<%c text %c>%c'%(libtcod.COLCTRL_1,libtcod.COLCTRL_STOP))
                    if isinstance(item.char, int):
##                        libtcod.console_set_color_control(libtcod.COLCTRL_1,libtcod.green,item.bg_color)
##                        setup = '%c%s%c'%(libtcod.COLCTRL_1, str(chr(item.char)), libtcod.COLCTRL_STOP)
                        setup = str(chr(item.char))
                        text = setup + ' ' + text
                    else:
##                        libtcod.console_set_color_control(libtcod.COLCTRL_1,item.color,item.bg_color)
##                        setup = '%c%s%c'%(libtcod.COLCTRL_1, item.char, libtcod.COLCTRL_STOP)
                        setup = item.char
                        text = setup + ' ' + text                  

                options.append(text)

    index = menu(header, options, INVENTORY_WIDTH)

    #if an item was chosen, return it
    if index is None or len(inv_merged) == 0: return None
    return inv_merged[index].item

def handle_keys():
    global turncount, WIZ_MODE, dungeon_level, fov_recompute, wallColor, sound_state
    try:
        key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)
    ##    fps = libtcod.sys_get_fps()
    ##    print fps

        if key.vk == libtcod.KEY_F1:
            message('You are on floor ' + str(dungeon_level) + '.', libtcod.cyan)
            message('Your quest has lasted for ' + str(turncount) + ' turns.', libtcod.cyan)

        elif key.vk == libtcod.KEY_F2:
            if player.PC.daily_check == True:
                day = int(datetime.datetime.now().strftime("%d"))
                month = int(datetime.datetime.now().strftime("%m"))
                year = int(datetime.datetime.now().strftime("%y"))
                message('The seed for today is ' + str(day*month*year) + '.', libtcod.gold)

        elif key.vk == libtcod.KEY_F9 and key.shift:
            if WIZ_MODE == False:
                message('Enabling wiz mode!', libtcod.gold)
                message('You can restore your hp to full by pressing <F11>.', libtcod.light_violet)
                message('You can build a level by pressing <Fx> where x is the level number.', libtcod.light_violet)
                message('You can become super buff by pressing <F12>.', libtcod.light_violet)
                WIZ_MODE = True
            else:
                message('Disabling wiz mode! :(', libtcod.gold)
                WIZ_MODE = False

        elif key.vk == libtcod.KEY_F1 and WIZ_MODE == True:
            message('Wiz mode: moving to level one.', libtcod.gold)
            player.PC.old_dungeon_level = dungeon_level
            dungeon_level = 0
            next_level()

        elif key.vk == libtcod.KEY_F2 and WIZ_MODE == True:
            message('Wiz mode: moving to level two.', libtcod.gold)
            player.PC.old_dungeon_level = dungeon_level
            dungeon_level = 1
            next_level()

        elif key.vk == libtcod.KEY_F3 and WIZ_MODE == True:
            message('Wiz mode: moving to level two.', libtcod.gold)
            player.PC.old_dungeon_level = dungeon_level
            dungeon_level = 1
            next_level()

        elif key.vk == libtcod.KEY_F4 and WIZ_MODE == True:
            message('Wiz mode: moving to level four.', libtcod.gold)
            dungeon_level = 3
            next_level()

        elif key.vk == libtcod.KEY_F5 and WIZ_MODE == True:
            message('Wiz mode: moving to level six.' ,libtcod.gold)
            dungeon_level = 5
            next_level()

        elif key.vk == libtcod.KEY_F6 and WIZ_MODE == True:
            message('Wiz mode: moving to level ten.', libtcod.gold)
            dungeon_level = 9
            next_level()

        elif key.vk == libtcod.KEY_F7 and WIZ_MODE == True:
            message('Wiz mode: moving to level seven.', libtcod.gold)
            dungeon_level = 22
            next_level()

        elif key.vk == libtcod.KEY_F11 and WIZ_MODE == True:
            player.fighter.hp = player.fighter.max_hp
            message('Wiz mode: hp set to full.', libtcod.gold)

        elif key.vk == libtcod.KEY_F12 and WIZ_MODE == True:
            message('Wiz mode: super buffing.', libtcod.gold)
            player.fighter.max_heal(50)
            player.fighter.heal(50)
            player.fighter.base_dmg_clumps += 1
            player.PC.experience += 1
            player.PC.total_experience += 1

        elif key.vk == libtcod.KEY_2:
            message('You are playing Lotus, a town for rogues.', libtcod.light_violet)
            message('Created by Andrew Wright (@roocey) for 7DRL 2016. Developed from 3/5/16 to 3/12/16.', libtcod.orange)

        elif key.c == ord('R'):
            if player.PC.daily_check == True:
                new_game(True)
                play_game()
            else:
                new_game()
                play_game()

        elif key.c == ord('e'):
            cast_examine()

        if game_state == 'playing':

            key_char = chr(key.c)

            #movement keys

            if key_char == 'w' or key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
                player_move_or_attack(0, -1)
                player.fighter.last_direction = 'up'

            elif key.vk == libtcod.KEY_KP7:
                player_move_or_attack(-1, -1)
                player.fighter.last_direction = 'up'

            elif key.vk == libtcod.KEY_KP9:
                player_move_or_attack(1, -1)
                player.fighter.last_direction = 'up'

            elif key_char == 's' or key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
                player_move_or_attack(0, 1)
                player.fighter.last_direction = 'down'

            elif key.vk == libtcod.KEY_KP1:
                player_move_or_attack(-1, 1)
                player.fighter.last_direction = 'down'

            elif key.vk == libtcod.KEY_KP3:
                player_move_or_attack(1, 1)
                player.fighter.last_direction = 'down'

            elif key_char == 'a' or key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
                player_move_or_attack(-1, 0)
                player.fighter.last_direction = 'left'

            elif key_char == 'd' or key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
                player_move_or_attack(1, 0)
                player.fighter.last_direction = 'right'

            elif key.vk == libtcod.KEY_ESCAPE:
                save_game()
                save_meta()
                sys.exit()

            elif key.vk == libtcod.KEY_SPACE or key.vk == libtcod.KEY_KP5:
                player.fighter.last_direction = None
                player.fighter.momentum = 0

            elif key_char == 't' or key_char == 'T':
                if player.fighter.status.get('Frozen') == 0:
                    weapon = get_equipped_in_slot('weapon')
                    if weapon != None:
                        weapon_throw()
                    else:
                        return 'didnt-take-turn'
                else:
                    message('You are frozen in place! You can\'t take any action, but you are immune to damage.', libtcod.cyan)

            elif key_char == 'i' or key_char == 'I':
                chosen_item = inventory_menu('Select an item to use:')
                if chosen_item is not None:
                    chosen_item.use()
            else:
                #test for other keys
                key_char = chr(key.c)

                if key_char == 'm' or key_char == 'M':
                    if sound_state:
                        sound_state = False
                        message('The game is muted.')
                    else:
                        sound_state = True
                        message('The game is unmuted.')

                if key_char == '?' or key_char == '/':
                    help_choice = None
                    while help_choice == None:
                        help_choice = menu('Select a topic:\n',
                                           ['Movement',
                                            'Inventory',
                                            'Winning',
                                            'Saving',
                                            'Website'], 45)

                        if help_choice == 0:
                            message('----', libtcod.cyan)
                            message('You can move by pressing <wasd>. You can wait a turn by pressing <SPACE>. Alternatively, you may use the arrow keys or the numpad.', libtcod.light_green)
                        elif help_choice == 1:
                            message('----', libtcod.cyan)
                            message('You can inspect your inventory by pressing <i>.', libtcod.light_green)
                        elif help_choice == 2:
                            message('----', libtcod.cyan)
                            message('You will automatically win when you collect your 27th orb of experience.', libtcod.light_green)
                        elif help_choice == 3:
                            message('----', libtcod.cyan)
                            message('The game automatically saves periodiocally. The game will attempt to load a savefile on launch.', libtcod.light_green)
                        elif help_choice == 4:
                            message('----', libtcod.cyan)
                            message('For regular updates and information visit the developer\'s website here: caffeineoverdose.me', libtcod.light_green)

                return 'didnt-take-turn'
            
    except Exception as ex:
        logging.exception('Caught an error')

def player_death(player):
    #the game ended!
    global game_state, dungeon_level, wincount
    player.fighter.hp = 0
    player.PC.pp = 0
    message('Congratulations! You have died.', libtcod.gold)
    message('You descended to floor ' +str(dungeon_level) + ' before meeting your untimely demise.', libtcod.white)
    if turncount == 42:
        message('You survived for 42 turns. Should have brought a towel.', libtcod.white)
    else:
        message('You survived for ' + str(turncount) + ' turns.', libtcod.white)
    message('You can restart by pressing <R> [capital <r>].', libtcod.light_blue)
    game_state = 'dead'
    save_game()
    save_meta()

    #for added effect, transform the player into a corpse!
    player.char = '%'
    player.color = libtcod.red

    if sound_state == True:
        lose_sound.play()

def monster_death(monster):
    global MONSTER_COUNT, game_state, dungeon_level, wincount, mobs_in_sight
    #transform it into a nasty corpse! it doesn't block, can't be
    #attacked and doesn't move
    if monster.boss == False:
        name = monster.name
        vowels = ('a', 'e', 'i', 'o', 'u', 'y', 'A', 'E', 'I', 'O', 'U', 'Y')
        if monster.fighter.hp == 0:
            map[monster.x][monster.y] = Tile(False, False, flag='corpse red')
            if monster.name.startswith(vowels):
                message('An ' + name + ' has been slain!', libtcod.orange)
            else:
                message('A ' + name + ' has been slain!', libtcod.orange)
        else:
            monster.fighter.hp = 0
            map[monster.x][monster.y] = Tile(False, False, flag='corpse red')
            if monster.name.startswith(vowels):
                message('An ' + name + ' has been slain!', libtcod.orange)
            else:
                message('A ' + name + ' has been slain!', libtcod.orange)
    else:
        boss_name = monster.name.upper()
        map[monster.x][monster.y] = Tile(False, False, flag='corpse gold')
        if monster.name == 'sand worm':
            message('You defeated the ' + boss_name + '!', libtcod.gold)
        else:
            message('You defeated ' + boss_name + '!', libtcod.gold)

    drop_loot(monster.name, monster.x, monster.y)

    if monster in mobs_in_sight:
        mobs_in_sight.remove(monster)

    objects.remove(monster)

def closest_monster(max_range, direction=None):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1#start with (slightly more than) maximum range

    if direction == None:

        for object in objects:
            if object.fighter and not object == player and object.effect_flag == False and libtcod.map_is_in_fov(fov_map, object.x, object.y) and object.fighter.hp > 0:
                #calculate distance between this object and the player
                dist = player.distance_to(object)
                if dist < closest_dist:  #it's closer, so remember it
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'up':
        for object in objects:
            if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x == object.x and player.y > object.y and object.effect_flag == False and object.fighter.hp > 0:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'down':
        for object in objects:
            if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x == object.x and player.y < object.y and object.effect_flag == False and object.fighter.hp > 0:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'left':
        for object in objects:
            if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x > object.x and player.y == object.y and object.effect_flag == False and object.fighter.hp > 0:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'right':
        for object in objects:
            if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x < object.x and player.y == object.y and object.effect_flag == False and object.fighter.hp > 0:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

def closest_object(max_range, direction=None):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1#start with (slightly more than) maximum range

    if direction == None:

        for object in objects:
            if not object == player and object.effect_flag == False and libtcod.map_is_in_fov(fov_map, object.x, object.y):
                #calculate distance between this object and the player
                dist = player.distance_to(object)
                if dist < closest_dist:  #it's closer, so remember it
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'up':
        for object in objects:
            if not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x == object.x and player.y > object.y and object.effect_flag == False:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'down':
        for object in objects:
            if not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x == object.x and player.y < object.y and object.effect_flag == False:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'left':
        for object in objects:
            if not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x > object.x and player.y == object.y and object.effect_flag == False:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

    elif direction == 'right':
        for object in objects:
            if not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y) and player.x < object.x and player.y == object.y and object.effect_flag == False:
                dist = player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
                    closest_dist = dist
        return closest_enemy

def cast_demolish(x, y):
    global fov_recompute
    for new_x in range(x-1, x+2):
        for new_y in range(y-1, y+2):
            try:
                map[new_x][new_y] = Tile(False, False, flag=None)
            except Exception as ex:
                logging.exception('Caught an error')

    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    fov_recompute = True

def cloud_manage(): #this function is weird as hell
    global fov_recompute
    for object in objects:

        if map[object.x][object.y].flag == 'water':
            object.bg_color = libtcod.blue*libtcod.random_get_float(0, 0.67, 1.33)          
        else:
            object.bg_color = object.original_bg_color

    try:
        for x in range(MAP_WIDTH):
            for y in range(MAP_HEIGHT):

                libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
                fov_recompute = True
    except Exception as ex:
        logging.exception('Caught an error')
                
def cast_examine():
    global fov_recompute
    examColor = libtcod.Color(209, 229, 240)
    thing = None
    if player.fighter.last_direction == 'up':
        thing = closest_object(70, 'up')
    if player.fighter.last_direction == 'down':
        thing = closest_object(70, 'down')
    if player.fighter.last_direction == 'left':
        thing = closest_object(70, 'left')
    if player.fighter.last_direction == 'right':
        thing = closest_object(70, 'right')

    if thing != None:
        if thing.examineMSG != None:
            if thing.item:
                if thing.item.item_type == 'wand' or thing.item.item_type == 'spellbook' or thing.item.item_type == 'scroll':
                    if thing.name != thing.item.real_name:
                        message('An unidentified ' + thing.name + '.', examColor)
                    else:
                        message(str(thing.examineMSG), examColor)
                else:
                    message(str(thing.examineMSG), examColor)
            else:
                message(str(thing.examineMSG), examColor)
        else:
            message('There seems to be nothing to learn about that object...', examColor)
    else:
        message('There are no viable objects to examine in that direction.', examColor)

def cast_money_printer():
    global dungeon_level
    player.PC.money += libtcod.random_get_int(dungeon_seed, 3, 6)
    random_message = libtcod.random_get_int(dungeon_seed, 1, 2)
    if random_message == 1:
        message('Ka-ching!', libtcod.gold)
    elif random_message == 2:
        message('Cha-ching!', libtcod.gold)

def drop_loot(loot, x, y):

    if loot == 'credits':
        item_component = Item(powerup=True, use_function=cast_money_printer)
        item = Object(x, y, '$', 'money', libtcod.gold, item=item_component, always_visible=True)
        objects.append(item)
        item.send_to_back()

def create_monster(name, x, y):
    if 0 <= x < MAP_WIDTH and 1 <= y < MAP_HEIGHT:

        monster = None

        if name == 'alchemical monstrosity':
            fighter_component = Fighter(hp=12, dmg_clumps=1, dmg=4, attack_range=1, describe_attack='changes')
            ai_component = BasicMonster(tags=['arbites'], special_chance=10)

            monster = Object(x, y, 'a', name, libtcod.fuchsia,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='An alchemical monstrosity: an alchemist that decided to experiment on itself.')

        elif name == 'big bat':
            fighter_component = Fighter(hp=6, dmg_clumps=1, dmg=2, attack_range=1, describe_attack='bites')
            ai_component = BasicMonster(tags=['flutters', 'wanders', 'sprints'], special_chance=10)

            monster = Object(x, y, 'b', name, libtcod.lightest_blue,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A big bat: an unusually large bat.')

        elif name == 'centaur':
            fighter_component = Fighter(hp=12, dmg_clumps=1, dmg=6, attack_range=8, describe_attack='shoots')
            ai_component = BasicMonster(tags=['sprints', 'shouts', 'wanders'], special_chance=10, attack_chance=75)

            monster = Object(x, y, 'c', name, libtcod.orange,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A centaur: a half-man, half-horse armed with a bow.')

        elif name == 'dragon':
            fighter_component = Fighter(hp=36, dmg_clumps=2, dmg=20, attack_range=1, describe_attack='tail swipes')
            ai_component = BasicMonster(tags=['sprints', 'cleaves', 'breathes fire'], special_chance=25)

            monster = Object(x, y, 'D', name, libtcod.red,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A dragon: a fearsome beast of legend that breathes fire and hoards treasure.')

            create_item(None, x, y)

        elif name == 'eldritch thing':
            fighter_component = Fighter(hp=8, dmg_clumps=1, dmg=8, attack_range=1, describe_attack='erases')
            ai_component = BasicMonster(tags=['flutters', 'shouts'], special_chance=10)

            monster = Object(x, y, 'e', name, libtcod.sea,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='An eldritch thing: a faceless humanoid that seems to exist in another dimension.')
            
        elif name == 'fiend':
            fighter_component = Fighter(hp=12, dmg_clumps=2, dmg=8, attack_range=1, describe_attack='slices')
            ai_component = BasicMonster(tags=['evades'], special_chance=10)

            monster = Object(x, y, 'f', name, libtcod.white,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A fiend: a cowardly demon with razor sharp claws.')

        elif name == 'goblin':
            fighter_component = Fighter(hp=8, dmg_clumps=1, dmg=4, attack_range=1, describe_attack='stabs')
            ai_component = BasicMonster(tags=['wanders'], special_chance=10)

            monster = Object(x, y, 'g', name, libtcod.darker_grey,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A goblin: a little green humanoid armed with a variety of digging tools.')

            monster.fighter.status['Acidic'] += 10000

        elif name == 'hobgoblin':
            fighter_component = Fighter(hp=14, dmg_clumps=1, dmg=8, attack_range=1, describe_attack='punches')
            ai_component = BasicMonster(tags=['wanders'], special_chance=20)

            monster = Object(x, y, 'h', name, libtcod.fuchsia,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A hobgoblin: a thick, brutish creature that packs a mean punch.')

        elif name == 'ice beast':
            fighter_component = Fighter(hp=16, dmg_clumps=4, dmg=4, attack_range=1, describe_attack='mauls')
            ai_component = BasicMonster(tags=['crawls'])

            monster = Object(x, y, 'i', name, libtcod.cyan,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='An ice beast: a slow-moving monster that annihilates its foes.')

        elif name == 'jelly':
            fighter_component = Fighter(hp=10, dmg_clumps=2, dmg=4, attack_range=1, describe_attack='slurps')
            ai_component = BasicMonster(tags=['slurps', 'wanders'], special_chance=5)

            monster = Object(x, y, 'j', name, libtcod.pink,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A jelly: a curious gelatinous critter that likes to eat.')

        elif name == 'kiwi':
            fighter_component = Fighter(hp=6, dmg_clumps=1, dmg=4, attack_range=1, describe_attack='kicks')
            ai_component = BasicMonster(tags=['wanders'], special_chance=5)

            monster = Object(x, y, 'k', name, libtcod.white,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A kiwi: a flightless bird from a faraway land.')

        elif name == 'lich':
            fighter_component = Fighter(hp=18, dmg_clumps=2, dmg=4, attack_range=1, describe_attack='slaps')
            ai_component = BasicMonster(tags=['zaps', 'evades'], special_chance=75)

            monster = Object(x, y, 'L', name, libtcod.light_cyan,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A lich: an undead mage that will zap you from afar.')

        elif name == 'maiden of the lake':
            fighter_component = Fighter(hp=12, dmg_clumps=3, dmg=3, attack_range=1, describe_attack='slashes')
            ai_component = BasicMonster(tags=['zaps', 'swims', 'wanders'], special_chance=40)

            monster = Object(x, y, 'm', name, libtcod.sea,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A maiden of the lake: a waterbound humanoid with sharp claws and the ability to zap from afar.')

            random_pool = libtcod.random_get_int(dungeon_seed, 4, 9)

            try: 
                map[monster.x][monster.y] = Tile(False, False, flag='water')

                while random_pool > 0:
                    random_pool -= 1
                    random_x = libtcod.random_get_int(dungeon_seed, -1, 1)
                    random_y = libtcod.random_get_int(dungeon_seed, -1, 1)
                    map[monster.x+random_x][monster.y+random_y] = Tile(False, False, flag='water')
            except Exception as ex:
                logging.exception('Caught an error')

        elif name == 'nurse':
            fighter_component = Fighter(hp=3, dmg_clumps=0, dmg=0, attack_range=1, describe_attack='slaps')
            ai_component = BasicMonster(tags=['nurse', 'wanders', 'evades'], special_chance=75)

            monster = Object(x, y, 'n', name, libtcod.white,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A nurse: an unexpected friend.')

        elif name == 'ogre':
            fighter_component = Fighter(hp=14, dmg_clumps=4, dmg=4, attack_range=1, describe_attack='crushes')
            ai_component = BasicMonster(tags=['wanders', 'knockbacks'], special_chance=15)

            monster = Object(x, y, 'O', name, libtcod.yellow,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='An ogre: a simple brute with great strength.')

        elif name == 'purple toad':
            fighter_component = Fighter(hp=8, dmg_clumps=1, dmg=6, attack_range=2, describe_attack='licks')
            ai_component = BasicMonster(tags=['wanders', 'confuses'], special_chance=15)

            monster = Object(x, y, 'p', name, libtcod.purple,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A purple toad: a giant amphibian that confuses anything that gets too close.')

        elif name == 'quantum mechanic':
            fighter_component = Fighter(hp=6, dmg_clumps=4, dmg=2, attack_range=1, describe_attack='displaces')
            ai_component = BasicMonster(tags=['wanders', 'displaces'], special_chance=5)

            monster = Object(x, y, 'Q', name, libtcod.azure,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A quantum mechanic: a strange creature from another dimension.')

        elif name == 'redcap':
            fighter_component = Fighter(hp=12, dmg_clumps=3, dmg=4, attack_range=2, describe_attack='pierces')
            ai_component = BasicMonster(tags=['wanders', 'sprints', 'shotus'], special_chance=5)

            monster = Object(x, y, 'r', name, libtcod.crimson,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A redcap: an impossibly quick humanoid armed with a sharp pike.')

        elif name == 'shadow':
            fighter_component = Fighter(hp=1, dmg_clumps=3, dmg=6, attack_range=1, describe_attack='consumes')
            ai_component = BasicMonster(tags=['wanders', 'flutters', 'cancelled'], special_chance=5)

            monster = Object(x, y, 's', name, libtcod.darker_grey,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A shadow: a fleeting spirit that only wants to consume so it can return to life.')

        elif name == 'troll':
            fighter_component = Fighter(hp=18, dmg_clumps=3, dmg=4, attack_range=1, describe_attack='claws')
            ai_component = BasicMonster(tags=['wanders', 'regenerates'], special_chance=5)

            monster = Object(x, y, 'T', name, libtcod.lime,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A troll: a big brute with long claws and the ability to rapidly regenerate.')

        elif name == 'unicorn':
            fighter_component = Fighter(hp=16, dmg_clumps=2, dmg=6, attack_range=1, describe_attack='tramples')
            ai_component = BasicMonster(tags=['wanders', 'regenerates', 'sprints', 'evades'], special_chance=5)

            monster = Object(x, y, 'U', name, libtcod.white,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='An unicorn: a fast, evasive horse that can regenerate rapidly thanks to its legendary horn.')

        elif name == 'vortex':
            fighter_component = Fighter(hp=6, dmg_clumps=2, dmg=4, attack_range=1, describe_attack='shocks')
            ai_component = BasicMonster(tags=['wanders', 'mana burns', 'crawls', 'flutters', 'cancelled'], special_chance=20)

            monster = Object(x, y, 'v', name, libtcod.light_violet,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A vortex: a whirling mass of energy that destroys magical power.')

        elif name == 'will-o\'-the-wisp':
            fighter_component = Fighter(hp=6, dmg_clumps=1, dmg=2, attack_range=1, describe_attack='burns')
            ai_component = BasicMonster(tags=['wanders', 'breathes fire', 'flutters', 'cancelled'], special_chance=15)

            monster = Object(x, y, 'w', name, libtcod.light_blue,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A will-o\'-the-wisp: a curious dancing flame rumored to breathe fire when in danger.')

        elif name == 'xavite':
            fighter_component = Fighter(hp=20, dmg_clumps=2, dmg=8, attack_range=1, describe_attack='roots')
            ai_component = BasicMonster(tags=['wanders', 'crawls', 'roots'])

            monster = Object(x, y, 'X', name, libtcod.copper,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A xavite: an elemental being composed of dirt and stone that will pin its prey in place.')

            monster.fighter.status['Acidic'] += 10000

        elif name == 'yacuruna':
            fighter_component = Fighter(hp=15, dmg_clumps=1, dmg=12, attack_range=1, describe_attack='jabs')
            ai_component = BasicMonster(tags=['swims', 'wanders', 'sprints', 'flutters'])

            monster = Object(x, y, 'y', name, libtcod.amber,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A yacuruna: a devious water spirit armed with a spear and a bad attitude.')

            random_pool = libtcod.random_get_int(dungeon_seed, 4, 9)

            try: 
                map[monster.x][monster.y] = Tile(False, False, flag='water')

                while random_pool > 0:
                    random_pool -= 1
                    random_x = libtcod.random_get_int(dungeon_seed, -1, 1)
                    random_y = libtcod.random_get_int(dungeon_seed, -1, 1)
                    map[monster.x+random_x][monster.y+random_y] = Tile(False, False, flag='water')
            except Exception as ex:
                logging.exception('Caught an error')

        elif name == 'zombie':
            fighter_component = Fighter(hp=15, dmg_clumps=3, dmg=4, attack_range=1, describe_attack='bites')
            ai_component = BasicMonster(tags=['wanders', 'returns'], special_chance=25)

            monster = Object(x, y, 'z', name, libtcod.green,
                blocks=True, fighter=fighter_component, ai=ai_component, examineMSG='A zombie: a shambling corpse that refuses to accept death.')

    if monster != None:
        objects.append(monster)
        monster.fighter.death_function=monster_death

        monster.fighter.max_hp = libtcod.random_get_int(dungeon_seed, monster.fighter.max_hp, int(monster.fighter.max_hp*1.5))
        monster.fighter.hp = monster.fighter.max_hp

def create_special(name, x, y): #creates special dungeon objects that are not items or fighters (e.g., fountains)
    special = None

##    if name == 'fountain':
##        special = Object(x, y, 225, name, libtcod.silver, blocks=True)

    if name == 'orb':
        special = Object(x, y, 15, name, libtcod.light_green, blocks=True)
        
    elif name == 'pit':
        special = Object(x, y, '^', name, libtcod.light_grey, blocks=True)
        libtcod.map_set_properties(fov_map, x, y, map[x][y].block_sight, map[x][y].blocked)

    elif name == 'upstairs':
        special = Object(x, y, '<', name, libtcod.white, blocks=True)

    elif name == 'stairs':
        special = Object(x, y, '>', name, libtcod.white, blocks=True)

    else:
        special_char = '1'
        special_color = libtcod.white
        if name == 'temple':
            special_char = '@'
            special_color = libtcod.white
        elif name == 'blacksmith':
            special_char = '@'
            special_color = libtcod.red
        elif name == 'training grounds':
            special_char = '@'
            special_color = libtcod.light_green

        special = Object(x, y, special_char, name, special_color, blocks=True)

    if special != None:
        special.special_flag = True
        special.always_visible = True
        objects.append(special)

def create_item(name, x, y, shop=False, flavor=None, brand=True):
    global unID_wands, identified_objects, unID_books, unID_scrolls, unID_colors
    equipment = None
    item = None

    random_weapons = ['dagger', 'sword', 'greatsword', 'spear', 'pike', 'hammer', 'war hammer']

    random_scrolls = ['scroll of striking', 'scroll of cancellation', 'scroll of digging', 'scroll of healing']

    random_wands = ['wand of striking', 'wand of cancellation', 'wand of digging', 'wand of healing']

    random_spellbooks = ['spellbook of striking', 'spellbook of cancellation', 'spellbook of digging', 'spellbook of healing']

    random_rings = ['ring of telepathy', 'ring of vampirism', 'ring of purity', 'ring of the mageblade', 'ring of the assassin']

    if name == 'rings':
        name = random.choice(random_rings)

    if name == None:
        name = ''
        random_choice = libtcod.random_get_int(dungeon_seed, 1, 2)
        if random_choice == 1:
            if libtcod.random_get_int(dungeon_seed, 1, 2) == 2:
                name = random.choice(random_weapons)
        elif random_choice == 2:
            if libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                name = random.choice(random_scrolls)
            elif libtcod.random_get_int(dungeon_seed, 1, 5) != 1:
                name = random.choice(random_wands)
            else:
                name = random.choice(random_spellbooks)

    enchant_random = 0
    if libtcod.random_get_int(dungeon_seed, 1, 3) == 3:
        enchant_random = libtcod.random_get_int(dungeon_seed, 1, 3)

    if name == 'dagger':
        equipment_component = Equipment('weapon', dmg_clumps=1, dmg=6, attack_range=1, cost=8)
        equipment = Object(x, y, '/', name, libtcod.lighter_cyan, examineMSG='A dagger: an elegant weapon from a simpler time.', equipment=equipment_component)

    if name == 'sword':
        equipment_component = Equipment('weapon', dmg_clumps=2, dmg=6, enchant_level=enchant_random, attack_range=1, cost=8)
        equipment = Object(x, y, '/', name, libtcod.cyan, examineMSG='A sword: similar to two daggers stuck together.', equipment=equipment_component)

    if name == 'greatsword':
        equipment_component = Equipment('weapon', dmg_clumps=3, dmg=6, enchant_level=enchant_random, attack_range=1, cost=8)
        equipment = Object(x, y, '/', name, libtcod.darker_cyan, examineMSG='A greatsword: similar to four daggers stuck together. Or two swords.', equipment=equipment_component)

    if name == 'spear':
        equipment_component = Equipment('weapon', dmg_clumps=1, dmg=8, enchant_level=enchant_random, attack_range=2, cost=8)
        equipment = Object(x, y, '/', name, libtcod.lighter_orange, examineMSG='A spear: put simply, a pointy stick. Can attack from up to two tiles away.', equipment=equipment_component)

    if name == 'pike':
        equipment_component = Equipment('weapon', dmg_clumps=1, dmg=12, enchant_level=enchant_random, attack_range=2, cost=8)
        equipment = Object(x, y, '/', name, libtcod.orange, examineMSG='A pike: the weapon of choice for the overly cautious fighter. Can attack from up to two tiles away.', equipment=equipment_component)

    if name == 'hammer':
        equipment_component = Equipment('weapon', dmg_clumps=4, dmg=3, enchant_level=enchant_random, attack_range=1, cost=8)
        equipment = Object(x, y, '/', name, libtcod.flame, examineMSG='A hammer: a mighty weapon if you want to bash some skulls in.', equipment=equipment_component)

    if name == 'war hammer':
        equipment_component = Equipment('weapon', dmg_clumps=4, dmg=4, enchant_level=enchant_random, attack_range=1, cost=8)
        equipment = Object(x, y, '/', name, libtcod.darker_flame, examineMSG='A war hammer: an even mightier weapon if you want to bash even more skulls in.', equipment=equipment_component)

    if name == 'ring of telepathy':
        equipment_component = Equipment('ring', cost=8)
        equipment = Object(x, y, '=', name, libtcod.cyan, examineMSG='A ring of telepathy: a glimpse of things to come.', equipment=equipment_component)

    if name == 'ring of vampirism':
        equipment_component = Equipment('ring', cost=8)
        equipment = Object(x, y, '=', name, libtcod.crimson, examineMSG='A ring of vampirism: a taste for blood.', equipment=equipment_component)

    if name == 'ring of purity':
        equipment_component = Equipment('ring', cost=8)
        equipment = Object(x, y, '=', name, libtcod.white, examineMSG='A ring of purity: a commitment to virtue.', equipment=equipment_component)

    if name == 'ring of the mageblade':
        equipment_component = Equipment('ring', cost=8)
        equipment = Object(x, y, '=', name, libtcod.han, examineMSG='A ring of the mageblade: a taste for mana.', equipment=equipment_component)

    if name == 'ring of the assassin':
        equipment_component = Equipment('ring', cost=8)
        equipment = Object(x, y, '=', name, libtcod.grey, examineMSG='A ring of the assassin: a commitment to shadow.', equipment=equipment_component)

    if 'spellbook' in name:
        type_check = 'spellbook'
        examine_start = 'A spellbook: '
        mp_multi = 2
        wand_check = None
        symbol = 14
        plural_check = None
        stack_check = None

    elif 'wand' in name:
        type_check = 'wand'
        examine_start = 'A wand: '
        mp_multi = 1
        wand_check = 0
        symbol = 22
        plural_check = None
        stack_check = None

    elif 'scroll' in name:
        type_check = 'scroll'
        examine_start = 'A scroll: '
        mp_multi = 1
        wand_check = None
        symbol = 13
        plural_check = 'scrolls of '
        stack_check = 1


    if 'healing' in name:
        item_component = Item(item_type=type_check, mana_cost=5*mp_multi, real_name=name, spell_type='healing', wand_chance=wand_check, plural_name=plural_check, stacks=stack_check)
        item = Object(x, y, symbol, name, unID_colors[0], examineMSG=examine_start + 'mend old wounds.', item=item_component)

        if item.name not in identified_objects:
            if type_check == 'spellbook':
                item.name = unID_books[0]
            elif type_check == 'wand':
                item.name = unID_wands[0]
            elif type_check == 'scroll':
                item.name = unID_scrolls[0]

    elif 'striking' in name:
        item_component = Item(item_type=type_check, mana_cost=6*mp_multi, real_name=name, spell_type='striking', wand_chance=wand_check, plural_name=plural_check, stacks=stack_check)
        item = Object(x, y, symbol, name, unID_colors[1], examineMSG=examine_start + 'lash out at a distant foe.', item=item_component)

        if item.name not in identified_objects:
            if type_check == 'spellbook':
                item.name = unID_books[1]
            elif type_check == 'wand':
                item.name = unID_wands[1]
            elif type_check == 'scroll':
                item.name = unID_scrolls[1]

    elif 'cancellation' in name:
        item_component = Item(item_type=type_check, mana_cost=4*mp_multi, real_name=name, spell_type='cancellation', wand_chance=wand_check, plural_name=plural_check, stacks=stack_check)
        item = Object(x, y, symbol, name, unID_colors[2], examineMSG=examine_start + 'make your foes uninteresting.', item=item_component)

        if item.name not in identified_objects:
            if type_check == 'spellbook':
                item.name = unID_books[2]
            elif type_check == 'wand':
                item.name = unID_wands[2]
            elif type_check == 'scroll':
                item.name = unID_scrolls[2]

    elif 'digging' in name:
        item_component = Item(item_type=type_check, mana_cost=3*mp_multi, real_name=name, spell_type='digging', wand_chance=wand_check, plural_name=plural_check, stacks=stack_check)
        item = Object(x, y, symbol, name, unID_colors[3], examineMSG=examine_start + 'find safe passage.', item=item_component)

        if item.name not in identified_objects:
            if type_check == 'spellbook':
                item.name = unID_books[3]
            elif type_check == 'wand':
                item.name = unID_wands[3]
            elif type_check == 'scroll':
                item.name = unID_scrolls[3]
            
    if item != None:
        objects.append(item)
        item.always_visible = True
        item.send_to_back()

        if item.item.plural_name != None and item.item.spell_type != None:
            item.item.plural_name = item.item.plural_name + item.item.spell_type

        if item.item.item_type == 'wand' or item.item.item_type == 'spellbook' or item.item.item_type == 'potion' or item.item.item_type == 'scroll':
            item.item.dippable = True

    if equipment != None:
        objects.append(equipment)
        equipment.always_visible = True
        equipment.send_to_back()

        if flavor == 'start':
            equipment.equipment.equip(silence=True)

#############################################
# Initialization & Main Loop
#############################################
def new_game(daily=False):
    global player, dungeon_level, merged_items, unID_colors, game_msgs, game_state, turncount, playcount, dungeon_seed, dukes, inventory, wallColors, unID_wands, identified_objects, unID_books, unID_scrolls, mobs_in_sight

    fighter_component = Fighter(hp=30, dmg=1, dmg_clumps=0, armor=0, attack_range=1, death_function=player_death)
    PC_component = PC(pp=30, experience=0, agility=0, dexterity=0, strength=0, brightness=16)
    player = Object(0, 0, '@', 'Ness', libtcod.Color(data.player_color_r, data.player_color_g, data.player_color_b), blocks=True, PC=PC_component, fighter=fighter_component)

    game_msgs = []

    dungeon_level = 1
    old_level = 0
    dungeon_seed = 0
    turncount = 0
    merged_items = []
    inventory = []
    mobs_in_sight = []
    unID_wands = ['oak wand', 'gold wand', 'silver wand', 'yew wand', 'sandalwood wand', 'ash wand', 'obsidian wand', 'pounamu wand']
    unID_books = ['odd spellbook', 'soft spellbook', 'firm spellbook', 'arcane spellbook', 'mysterious spellbook', 'ancient spellbook']
    unID_scrolls = ['dried gum scroll', 'papyrus scroll', 'vellum scroll', 'sandpaper scroll', 'leather scroll']
    unID_colors = [libtcod.yellow, libtcod.red, libtcod.pink, libtcod.blue, libtcod.copper, libtcod.orange, libtcod.cyan, libtcod.light_violet]
    identified_objects = []
    random.shuffle(unID_wands)
    random.shuffle(unID_books)
    random.shuffle(unID_scrolls)
    random.shuffle(unID_colors)
    wallColors = [libtcod.Color(136, 204, 238), libtcod.Color(221, 204, 119), libtcod.Color(204, 102, 119), libtcod.Color(170, 68, 153), libtcod.Color(221, 119, 204), libtcod.Color(68, 170, 153)]

    if daily == True:
        day = int(datetime.datetime.now().strftime("%d"))
        month = int(datetime.datetime.now().strftime("%m"))
        year = int(datetime.datetime.now().strftime("%y"))
        dungeon_seed = libtcod.random_new_from_seed(day*month*year*dungeon_level)
        make_map()
        player.PC.daily_check = True
    else:
        dungeon_seed = 0
        make_map()
        player.PC.daily_check = False

    initialize_fov()

    game_state = 'playing'

    message('You come across a small town called Lotus. The townspeople have asked you to collect all 27 of the orbs of experience hidden in the dungeon below the town.', libtcod.cyan)

    playcount = playcount + 1

    if sound_state == True:
        explosion_sound.play()

def initialize_fov():
    global fov_recompute, fov_map, MAP_WIDTH, MAP_HEIGHT
    fov_recompute = True

    #create the FOV map, according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    try:
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    except Exception as ex:
        logging.exception('Caught an error')
        
    libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
    libtcod.console_clear(0)

def confirmation_box(response=None):
    while response == None:
        yes_or_no = menu('Confirmation',
                         ['Yes',
                          'No'], 30)

        if yes_or_no == 0:
            response = True
            return True

        else:
            response = False
            return False

def play_game(challenge_flag=False):
    global wincount, turncount, dungeon_level, dungeon_seed, mobs_in_sight
    player_action = None

    #main loop
    try:
        while not libtcod.console_is_window_closed():

            render_all()

            libtcod.console_flush()

            for object in objects:
                object.clear()

            while 'temple' in player.PC.interaction_checker:
                level_choice = menu('May the Light be with you:',
                                    ['Receive blessing - 1 XP',
                                     'Leave'], 30)

                if level_choice == 0:
                    message('You\'ve asked to receive a blessing. Your HP and MP will be increased by 1d6.')
                    render_all()
                    confirm_choice = confirmation_box()
                    if confirm_choice == True:
                        value = libtcod.random_get_int(dungeon_seed, 1, 6)
                        value2 = libtcod.random_get_int(dungeon_seed, 1, 6)
                        player.fighter.base_max_hp += value
                        player.fighter.hp = player.fighter.max_hp
                        player.PC.base_max_pp += value2
                        player.PC.pp = player.PC.max_pp
                        player.PC.interaction_checker.remove('temple')
                        render_all()
                        message('You spend some time at the temple. You gained ' + str(value) + ' HP and ' + str(value2) + ' MP.', libtcod.cyan)
                        player.PC.experience -= 1
                    else:
                        player.PC.interaction_checker.remove('temple')
                        render_all()
                elif level_choice == 1:                
                    player.PC.interaction_checker.remove('temple')
                    render_all()

            while 'blacksmith' in player.PC.interaction_checker:
                level_choice = menu('It\'s hammer time:',
                                    ['Improve weapon - 1 XP',
                                     'Craft ring - 1 XP',
                                     'Leave'], 30)

                if level_choice == 0:
                    weapon = get_equipped_in_slot('weapon')
                    if weapon != None:
                        message('You\'ve asked the smith to upgrade your weapon. Your +' + str(weapon.enchant_level) + ' ' + weapon.owner.name + ' will gain 1 to 3 levels.')
                        render_all()
                        confirm_choice = confirmation_box()
                        if confirm_choice == True:
                            value = 1
                            if libtcod.random_get_int(dungeon_seed, 1, 3) != 3:
                                value = 1
                            elif libtcod.random_get_int(dungeon_seed, 1, 9) != 9:
                                value = 2
                            else:
                                value = 3
                            player.PC.interaction_checker.remove('blacksmith')
                            render_all()
                            player.PC.experience -= 1
                            weapon.enchant_level += value
                            message('You spend some time at the blacksmith. Your +' + str(weapon.enchant_level-value) + ' ' + weapon.owner.name + ' is now +' + str(weapon.enchant_level) + '.') 
                        else:
                            player.PC.interaction_checker.remove('blacksmith')
                            render_all()
                    else:
                        player.PC.interaction_checker.remove('blacksmith')
                        render_all()
                        message('You need a weapon to improve...', libtcod.orange)
                elif level_choice == 1:
                    message('You\'ve asked the smith to forge a ring. The ring she will craft is entirely random and not dependent on any other factors.')
                    render_all()
                    confirm_choice = confirmation_box()
                    if confirm_choice == True:
                        create_item('rings', player.x, player.y-1)
                        player.PC.interaction_checker.remove('blacksmith')
                        render_all()
                        player.PC.experience -= 1
                        message('You spend some time at the blacksmith. She crafts a ring and sets it down next to you.')
                    else:
                        player.PC.interaction_checker.remove('blacksmith')
                        render_all()
                elif level_choice == 2:                
                    player.PC.interaction_checker.remove('blacksmith')
                    render_all()

            while 'training grounds' in player.PC.interaction_checker:
                level_choice = menu('Don\'t skip leg day:',
                                    ['Exercise Agility - 1 XP',
                                     'Exercise Dexterity - 1 XP',
                                     'Exercise Strength - 1 XP',
                                     'Leave'], 30)

                if level_choice == 0:
                    message('You\'ve asked your fitness coach to practice agility training with you. This exercise will raise your agility from ' + str(player.PC.agility) + '% to ' + str(player.PC.agility+10-(player.PC.agility//9)) + '%.')
                    render_all()
                    confirm_choice = confirmation_box()
                    if confirm_choice == True:
                        value = 10 - (player.PC.agility//9)
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                        player.PC.experience -= 1
                        player.PC.agility += value
                        message('You spend some time with your fitness coach. Your agility is now ' + str(player.PC.agility) + '%.')
                    else:
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                elif level_choice == 1:
                    message('You\'ve asked your fitness coach to practice dexterity training with you. This exercise will raise your dexterity from ' + str(player.PC.dexterity) + '% to ' + str(player.PC.dexterity+10-(player.PC.dexterity//9)) + '%.')
                    render_all()
                    confirm_choice = confirmation_box()
                    if confirm_choice == True:
                        value = 10 - (player.PC.dexterity//9)
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                        player.PC.experience -= 1
                        player.PC.dexterity += value
                        message('You spend some time with your fitness coach. Your dexterity is now ' + str(player.PC.dexterity) + '%.')
                    else:
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                elif level_choice == 2:
                    message('You\'ve asked your fitness coach to practice strength training with you. This exercise will raise your strength from ' + str(player.PC.strength) + '% to ' + str(player.PC.strength+10-(player.PC.strength//9)) + '%.')
                    render_all()
                    confirm_choice = confirmation_box()
                    if confirm_choice == True:
                        value = 10 - (player.PC.strength//9)
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                        player.PC.experience -= 1
                        player.PC.strength += value
                        message('You spend some time with your fitness coach. Your strength is now ' + str(player.PC.strength) + '%.')
                    else:
                        player.PC.interaction_checker.remove('training grounds')
                        render_all()
                elif level_choice == 3:                
                    player.PC.interaction_checker.remove('training grounds')
                    render_all()
                    
            #handle keys and exit game if needed
            player_action = handle_keys()
            if player_action == 'exit':
                save_game()
                save_meta()
                main_menu()

            #let monsters take their turn

            if game_state == 'playing' and player_action != 'didnt-take-turn':

                player.PC.player_turn()

                for object in objects:
                    if object.ai and object.took_turn == False:
                        object.took_turn = True
                        object.ai.take_turn()
                    if object.fighter:
                        object.fighter.dot_tick()
                        if object.ai:
                            if libtcod.map_is_in_fov(fov_map, object.x, object.y):
                                if object not in mobs_in_sight:
                                    mobs_in_sight.append(object)
                            else:
                                if object in mobs_in_sight:
                                    mobs_in_sight.remove(object)

                    if object.item or object.equipment:
                        object.send_to_back()

    except Exception as ex:
        logging.exception('Caught an error')

def next_level(flavor=None):
    global dungeon_level, dungeon_seed
    #advance to the next level
    day = int(datetime.datetime.now().strftime("%d"))
    month = int(datetime.datetime.now().strftime("%m"))
    year = int(datetime.datetime.now().strftime("%y"))

    random_darkness = libtcod.random_get_int(dungeon_seed, 300, 600)

    dungeon_level += 1

    player.PC.floor_turncount = 0

    if player.PC.daily_check == True:
        dungeon_seed = libtcod.random_new_from_seed(day*month*year*dungeon_level)

    make_map()  #create a fresh new level!
    initialize_fov()
    
    render_all()

    player.fighter.heal(999)
    player.PC.heal_pp(999)

def main_menu():
    global wincount, sound_state
    while not libtcod.console_is_window_closed():
        libtcod.console_flush()

        #show the game's title, and some credits!
        libtcod.console_set_default_foreground(0, libtcod.light_violet)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-37, libtcod.BKGND_NONE, libtcod.CENTER, 'Lotus, a town for rogues')
        libtcod.console_set_default_foreground(0, libtcod.white)
        libtcod.console_print_ex(0, SCREEN_WIDTH-78, SCREEN_HEIGHT-1, libtcod.BKGND_NONE, libtcod.CENTER, '7DRL')
        libtcod.console_set_default_foreground(0, libtcod.gold)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-1, libtcod.BKGND_NONE, libtcod.CENTER, 'By Andrew Wright')

        #show options and wait for the player's choice
        if sound_state == True:
            choice = menu('', ['Play a new game', 'Continue last game', 'Play the daily dungeon', 'Mute', 'Quit'], 30)

            if choice == 0:
                new_game()
                play_game()
            elif choice == 1:
                try:
                    load_game()
                except:
                    continue
                play_game()
            elif choice == 2:
                new_game(True)
                play_game()
            elif choice == 3:
                sound_state = False
            elif choice == 4:
                sys.exit()
        else:
            choice = menu('', ['Play a new game', 'Continue last game', 'Play the daily dungeon', 'Unmute', 'Quit'], 30)

            if choice == 0:
                new_game()
                play_game()
            elif choice == 1:
                try:
                    load_game()
                except:
                    continue
                play_game()
            elif choice == 2:
                new_game(True)
                play_game()
            elif choice == 3:
                sound_state = True
            elif choice == 4:
                sys.exit()

def save_game():
    file = shelve.open('savegame', 'c')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['merged_items'] = merged_items
    file['game_msgs'] = game_msgs
    file['inventory'] = inventory
    file['game_state'] = game_state
    file['dungeon_level'] = dungeon_level
    file['dungeon_seed'] = dungeon_seed
    file['turncount'] = turncount
    file['MAP_HEIGHT'] = MAP_HEIGHT
    file['MAP_WIDTH'] = MAP_WIDTH
    file['mobs_in_sight'] = mobs_in_sight
    file['wallColors'] = wallColors
    file['unID_scrolls'] = unID_scrolls
    file['unID_wands'] = unID_wands
    file['unID_books'] = unID_books
    file['unID_colors'] = unID_colors
    file['identified_objects'] = identified_objects
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, merged_items, game_msgs, game_state, dungeon_level, dungeon_seed, turncount, inventory, MAP_HEIGHT, MAP_WIDTH, mobs_in_sight, wallColors, unID_wands, unID_scrolls, unID_books, unID_colors, identified_objects, wallColor

    file = shelve.open('savegame', 'c')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    merged_items = file['merged_items']
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    dungeon_level = file['dungeon_level']
    dungeon_seed = file['dungeon_seed']
    turncount = file['turncount']
    MAP_HEIGHT = file['MAP_HEIGHT']
    MAP_WIDTH = file['MAP_WIDTH']
    mobs_in_sight = file['mobs_in_sight']
    wallColors = file['wallColors']
    unID_scrolls = file['unID_scrolls']
    unID_wands = file['unID_wands']
    unID_books = file['unID_books']
    unID_colors = file['unID_colors']
    identified_objects = file['identified_objects']
    wallColor = random.choice(wallColors)
    file.close()

    initialize_fov()

def save_meta():
    file = shelve.open('meta', 'c')
    file['playcount'] = playcount
    file['wincount'] = wincount
    file['sound_state'] = sound_state
    file.close()

def load_meta():
    global playcount, wincount, sound_state

    file = shelve.open('meta', 'c')
    playcount = file['playcount']
    wincount = file['wincount']
    sound_state = file['sound_state']
    file.close()

libtcod.sys_set_fps(data.fps_limit)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(20, SCREEN_HEIGHT)
msg_region = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.console_set_custom_font('dat/fonts/' + data.font, libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW, 16, 16)

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Lotus, a town for rogues', False, libtcod.RENDERER_SDL)

try:
    load_meta()
except KeyError:
    print 'No meta data available'
try:
    load_game()
    play_game()
except KeyError:
    new_game()
    play_game()
