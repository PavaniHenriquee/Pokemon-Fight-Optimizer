"""Damage calculations"""
import random
import numpy as np
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Models.idx_nparray import PokArray, MoveArray
from Models.helper import MoveCategory, Status, Types, AbilityActivation
from Models.pokemon import Pokemon
from Models.move import Move
from DataBase.AbilitiesDB import AbilityNames


def damaging_ability(attacker, defender, move) -> float:  # pylint: disable=W0613
    """Calculate what the ability does in relation to damage
    Returns:
        1 if nothing happens\n
        0 if gives immunity\n
        multiplier if it does something, like Blaze"""
    mult = 1
    if (
        attacker[PokArray.AB_ID] in (
            AbilityNames.BLAZE,
            AbilityNames.TORRENT,
            AbilityNames.OVERGROW
        )
        and attacker[PokArray.CURRENT_HP] / attacker[PokArray.MAX_HP] <= 1 / 3
    ):
        if attacker[PokArray.AB_ID] == AbilityNames.BLAZE and move[MoveArray.TYPE] == Types.FIRE:
            mult = 1.5
        if attacker[PokArray.AB_ID] == AbilityNames.TORRENT and move[MoveArray.TYPE] == Types.WATER:
            mult = 1.5
        if attacker[PokArray.AB_ID] == AbilityNames.OVERGROW and move[MoveArray.TYPE] == Types.GRASS:
            mult = 1.5

    return mult


def multipliers(move: np.float32, attacker: np.float32, defender: np.float32, crit: bool, roll_mult: int, damage):
    """Calc Multiplers for bas formula damage"""

    # Burn
    if attacker[PokArray.STATUS] == Status.BURN:
        if move[MoveArray.CATEGORY] == MoveCategory.PHYSICAL:
            damage = np.floor(0.5 * damage)

    # TODO: Screen

    # TODO: Targets

    # TODO: Weather

    # TODO: Flash Fire

    # Adding 2 after the above
    damage += 2

    # Crit
    if crit is True:
        damage *= 2

    # TODO: Item

    # TODO: Me First

    # Roll Multiplier
    if roll_mult is None:
        roll_mult = random.randint(85, 100) / 100
    damage = np.floor(roll_mult * damage)

    # STAB
    if move[MoveArray.TYPE] in [attacker[PokArray.TYPE1], attacker[PokArray.TYPE2]]:
        damage = np.floor(1.5 * damage)

    # Effectiveness type 1
    effectiveness = get_type_effectiveness(move[MoveArray.TYPE], defender[PokArray.TYPE1], 0)
    if effectiveness != 1:
        damage = np.floor(effectiveness * damage)

    # Effectiveness type 2
    if defender[PokArray.TYPE2]:
        effectiveness2 = get_type_effectiveness(move[MoveArray.TYPE], defender[PokArray.TYPE2], 0)
        if effectiveness2 != 1:
            damage = np.floor(effectiveness2 * damage)
    else:
        effectiveness2 = 1

    # TODO: Solid Rock and Filter

    # TODO: Expert belt

    # TODO: Tinted Lens

    # TODO: Berry

    return damage, effectiveness*effectiveness2


def calculate_damage(attacker: Pokemon, defender: Pokemon, move: Move, crit: bool=False, roll_multiplier: float=None):
    """Calculate damage based on current stats of the attacker and the defender, giving back the damage and its effectiveness"""
    if move[MoveArray.CATEGORY] == MoveCategory.STATUS or move[MoveArray.CATEGORY] == 0:
        # Status moves don't deal damage(Trainer AI will fall here)
        return 0, 0
    if move[MoveArray.CATEGORY] == MoveCategory.STATUS:
        raw_attack = attacker[PokArray.ATTACK]
        raw_defense = defender[PokArray.DEFENSE]
        atk_stage = attacker[PokArray.ATTACK_STAT_STAGE]
        def_stage = defender[PokArray.DEFENSE_STAT_STAGE]
    else:
        raw_attack = attacker[PokArray.SPECIAL_ATTACK]
        raw_defense = defender[PokArray.SPECIAL_DEFENSE]
        atk_stage = attacker[PokArray.SPECIAL_ATTACK_STAT_STAGE]
        def_stage = defender[PokArray.SPECIAL_DEFENSE_STAT_STAGE]

    if crit is True:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    # apply stage multipliers
    attack = np.floor(raw_attack * stage_to_multiplier(atk_stage))
    defense = np.floor(raw_defense * stage_to_multiplier(def_stage))

    # Ability
    power = move[MoveArray.POWER]
    if attacker[PokArray.AB_WHEN] == AbilityActivation.ON_DAMAGE:
        power = power * damaging_ability(attacker, defender, move)

    # Base damage formula
    damage = np.floor((((2 * attacker[PokArray.LEVEL] / 5) + 2) * move[MoveArray.POWER] * (attack / defense)) / 50)

    damage, effectiveness = multipliers(move, attacker, defender, crit, roll_multiplier, damage)
    return damage, effectiveness


def calculate_damage_confusion(pok):
    """Calculate the damage for Confusion self hit"""
    raw_attack = pok[PokArray.ATTACK]
    raw_defense = pok[PokArray.DEFENSE]
    atk_stage = pok[PokArray.ATTACK_STAT_STAGE]
    def_stage = pok[PokArray.DEFENSE_STAT_STAGE]
    # apply stage multipliers
    attack = np.floor(raw_attack * stage_to_multiplier(atk_stage))
    defense = np.floor(raw_defense * stage_to_multiplier(def_stage))
    # Base damage formula, confusion counts as a 40 power move
    damage = np.floor(np.floor(((2 * pok[PokArray.LEVEL] / 5) + 2) * 40 * (attack / defense)) / 50 + 2)
    if pok[PokArray.STATUS] == Status.BURN:
        damage *= 0.5
    return damage
