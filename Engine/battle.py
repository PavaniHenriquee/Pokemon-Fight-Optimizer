"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
from Utils.jit import njit
from Engine.engine_helper import (
    check_speed, move_order, calculate_hit_miss, calculate_crit, reset_switch_out,
    flinch_checker, thaw, early_returns, switch_in, SIDE_OR_FIELD_TARGETS,
    contact_ability, heal_weather, on_residual, trainer_ai_items, drain,
    item_on_rdmg, eat_berry_bug_bite, struggle, switch_items,
    RECORD_DAMAGE, weather_dmg, WEATHER_NOT_END_OF_TURN,
    mark_hurt, unlock_move, apply_recoil, move_recoil, struggle_recoil, natural_gift,
    try_protect, endure_damage, side_base
)
from Engine.status_calc import (
    sec_effects, calculate_effects, TURNS_2_5, sleep_blocked, SLOT_MASK, SLOT_STEP
)
from Engine.damage_calc import calculate_damage, ROLLOUT_MOVES
from Models.trainer_ai import sub_after_death
from Models.idx_const import (
    POK_LEN, MOVE_STRIDE, OFFSET_MOVE, SIDE_REFLECT_TURNS, SIDE_LIGHT_SCREEN_TURNS,
    SIDE_MIST_TURNS, SIDE_SAFEGUARD_TURNS, SIDE_LUCKY_CHANT_TURNS, SIDE_TOXIC_SPIKES
)
from Models.helper import (
    count_party, PHYSICAL_SPECIAL, Target, TARGET_SELF_SIDE
)
from Models.constants import (
    _FIELD_OPP_POK, _FIELD_MY_POK, _FIELD_AI_TOOK_DMG_LAST_TURN, _FIELD_AI_ITEM1, _FIELD_WEATHER,
    _FIELD_AI_KNOWS, _FIELD_MY_LAST_MOVE, _FIELD_MY_ENTER_FIELD, _FIELD_OPP_ENTER_FIELD, _FIELD_TURN,
    _POK_AB_WHEN, _POK_CURRENT_HP, _POK_AB_ID, _POK_MAX_HP, _POK_STATUS, _POK_TURNS, _MOVECATEGORY_SPECIAL,
    _ABILITYACTIVATION_ON_CONTACT, _ABILITYACTIVATION_ON_RESIDUAL, _DAMAGESOURCES_COUNTER, _POK_TURNS_ACTIVE,
    _ABILITYNAMES_AFTERMATH, _ABILITYNAMES_DAMP, _FLAGS_CONTACT, _MOVE_ID, _MOVE_PP, _MOVENAME_COVET,
    _MOVE_CATEGORY, _MOVE_TYPE, _SEC_CHANCE, _SEC_VOL_STATUS, _MOVENAME_STRUGGLE, _MOVEOUTCOME_HIT,
    _SEC_VOL_STATUS2,
    _VOLSTATUS_FLINCH, _STATUS_FREEZE, _ACTIONTYPE_MOVE, _BATTLEPHASE_TURN_START, _MOVECATEGORY_PHYSICAL,
    _BATTLEPHASE_DEATH_END_OF_TURN, _FIELD_PHASE, _MOVE_DRAIN, _MOVE_MULTI_HIT_MIN, _MOVE_MULTI_HIT_MAX,
    _POK_VOL_STATUS, _VOLSTATUS_BIDE, _POK_DMG_TAKEN, _MOVE_CHARGE_RECHARGE, _POK_CHARGE_RECHARGE,
    _POK_LOCKED_MOVE, _ITEM_WHEN, _ITEMACTIVATION_ON_RECEIVE_DAMAGE, _MOVE_DAMAGE, _MOVE_VOL_STATUS,
    _MOVENAME_BUG_BITE, _ITEM_ITEM_TYPE, _ITEMTYPE_BERRY, _DAMAGESOURCES_BIDE, _DAMAGESOURCES_MAGIC_COAT,
    _STATUS_POISON, _STATUS_TOXIC, _STATUS_BURN, _VOLSTATUS_CURSE, _ABILITYNAMES_MAGIC_GUARD,
    _POK_BADLY_POISON, _DAMAGESOURCES_LEVEL, _DAMAGESOURCES_PSYWAVE, _POK_LEVEL, _MOVE_RECOIL,
    _MOVENAME_FURY_CUTTER, _MOVENAME_NATURAL_GIFT, _MOVENAME_BOUNCE, _POK_CONSEC_COUNT,
    _VOLSTATUS_SEMI_INVULNERABLE, _VOLSTATUS_HURT_THIS_TURN, _VOLSTATUS_PROTECT, _VOLSTATUS_ENDURE,
    _VOLSTATUS_RAGE, _VOLSTATUS_DESTINY_BOND, _VOLSTATUS_CHARGE, _VOLSTATUS_INGRAIN,
    _VOLSTATUS_AQUA_RING, _VOLSTATUS_LEECH_SEED, _VOLSTATUS_YAWN, _VOLSTATUS_ATTRACT,
    _VOLSTATUS_CONFUSION, _VOLSTATUS_UPROAR, _VOLSTATUS_PARTIALLY_TRAPPED,
    _VOLSTATUS_FOCUS_ENERGY, _VOLSTATUS_NIGHTMARE, _VOLSTATUS_FORESIGHT, _VOLSTATUS_DEFENSE_CURL,
    _MOVENAME_PROTECT, _MOVENAME_ENDURE, _MOVENAME_FEINT, _MOVENAME_RAGE, _MOVENAME_CHARGE,
    _POK_PROTECT_COUNT, _POK_ATTACK_STAT_STAGE, _POK_YAWN_TURNS, _POK_SLEEP_COUNTER, _STATUS_SLEEP,
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
    _POK_LAST_MOVE_ID, _MOVENAME_UPROAR, _POK_UPROAR_TURNS, _POK_TRAP_TURNS, _POK_TAUNT_TURNS,
    _POK_ENCORE_TURNS, _POK_DISABLE_TURNS, _VOLSTATUS_TAUNT, _VOLSTATUS_ENCORE, _VOLSTATUS_DISABLE,
    _MOVEOUTCOME_MISS, _MOVEOUTCOME_SEMI_INVULNERABLE, _MOVEOUTCOME_PROTECTED,
    _ABILITYNAMES_SOUNDPROOF, _FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND, _FIELD_WEATHER_DURATION,
    _MOVE_SIDE_CONDITION, _MOVE_TARGET, _SIDECONDITION_REFLECT, _SIDECONDITION_LIGHT_SCREEN,
    _SIDECONDITION_MIST, _SIDECONDITION_SAFEGUARD, _SIDECONDITION_LUCKY_CHANT,
    _SIDECONDITION_TOXIC_SPIKES, _SIDECONDITION_STEALTH_ROCK, _SIDECONDITION_SPIKES,
    _MOVENAME_BRICK_BREAK, _MOVENAME_RAPID_SPIN, _MOVENAME_RAIN_DANCE, _MOVENAME_SANDSTORM,
    _WEATHER_RAIN, _WEATHER_SANDSTORM, _MOVE_FORCE_SWITCH, _MOVE_SELF_SWITCH, _MOVE_POWER,
    _ABILITYNAMES_SUCTION_CUPS, _ABILITYNAMES_MOLD_BREAKER, _MOVENAME_PURSUIT, _POK_CONFUSION_COUNTER,
    _POK_EVASION_STAT_STAGE, _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT, _VOLSTATUS_HEAL_BLOCK,
    _BATTLEPHASE_BATON_PASS, _FIELD_PENDING_OPP_MOVE
)
from Models.move import STRUGGLE


MULTIHIT_PROB=(2,2,2,3,3,3,4,5)
SEMI_INVULNERABLE_MOVES = (_MOVENAME_BOUNCE,)
ROLLOUT_MAX_USES = 5
FURY_CUTTER_MAX_COUNT = 5
STALL_MOVES = (_MOVENAME_PROTECT, _MOVENAME_ENDURE)
# Volatiles that only last for the turn they were set in
TURN_VOLATILES = _VOLSTATUS_HURT_THIS_TURN | _VOLSTATUS_PROTECT | _VOLSTATUS_ENDURE
# Bits of pokeplatinum's statusVolatile that the Gen IV Rage glitch wipes. Bide is left out so
# its lock (CHARGE_RECHARGE) stays consistent
RAGE_GLITCH_CLEARS = (
    _VOLSTATUS_FLINCH | _VOLSTATUS_CONFUSION | _VOLSTATUS_UPROAR | _VOLSTATUS_PARTIALLY_TRAPPED
    | _VOLSTATUS_ATTRACT | _VOLSTATUS_FOCUS_ENERGY | _VOLSTATUS_DESTINY_BOND | _VOLSTATUS_NIGHTMARE
    | _VOLSTATUS_CURSE | _VOLSTATUS_FORESIGHT | _VOLSTATUS_DEFENSE_CURL
)
# Bit in Field.AI_KNOWS for each of my move slots, set once the AI sees the move used
AI_KNOWS_MOVES = (
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4
)
# An uproar keeps going through these, only a blocked turn or an immune target ends it early
UPROAR_KEEPS_ON = (_MOVEOUTCOME_MISS, _MOVEOUTCOME_SEMI_INVULNERABLE, _MOVEOUTCOME_PROTECTED)
SIDES = (_FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND)
# Timed side conditions and their turn counter, in the order the end of turn counts them down
TIMED_SIDE_CONDITIONS = (
    (_SIDECONDITION_REFLECT, SIDE_REFLECT_TURNS),
    (_SIDECONDITION_LIGHT_SCREEN, SIDE_LIGHT_SCREEN_TURNS),
    (_SIDECONDITION_MIST, SIDE_MIST_TURNS),
    (_SIDECONDITION_SAFEGUARD, SIDE_SAFEGUARD_TURNS),
    (_SIDECONDITION_LUCKY_CHANT, SIDE_LUCKY_CHANT_TURNS),
)
SCREENS = _SIDECONDITION_REFLECT | _SIDECONDITION_LIGHT_SCREEN
TIMED_SIDE_MASK = (
    _SIDECONDITION_REFLECT | _SIDECONDITION_LIGHT_SCREEN | _SIDECONDITION_MIST
    | _SIDECONDITION_SAFEGUARD | _SIDECONDITION_LUCKY_CHANT
)
RAPID_SPIN_CLEARS = _SIDECONDITION_STEALTH_ROCK | _SIDECONDITION_SPIKES | _SIDECONDITION_TOXIC_SPIKES
# Screens, Mist, Safeguard, Lucky Chant and move weather
FIELD_EFFECT_TURNS = 5
TOXIC_SPIKES_MAX = 2
WEATHER_MOVES = ((_MOVENAME_RAIN_DANCE, _WEATHER_RAIN), (_MOVENAME_SANDSTORM, _WEATHER_SANDSTORM))
# Stealth Rock and Toxic Spikes go on the foe's side, the other side conditions on the user's
FOE_SIDE_TARGET = Target.FOE_SIDE
# Self, side and field moves still work against a fainted foe
NO_FOE_TARGETS = TARGET_SELF_SIDE + SIDE_OR_FIELD_TARGETS
# What Baton Pass hands over besides the stat stages (pokeplatinum VOLATILE_CONDITION_BATON_PASSED
# and MOVE_EFFECT_BATON_PASSED, the ones the engine has)
BATON_PASS_VOLS = (
    _VOLSTATUS_CONFUSION | _VOLSTATUS_FOCUS_ENERGY | _VOLSTATUS_CURSE | _VOLSTATUS_LEECH_SEED
    | _VOLSTATUS_INGRAIN | _VOLSTATUS_AQUA_RING | _VOLSTATUS_MUD_SPORT | _VOLSTATUS_WATER_SPORT
    | _VOLSTATUS_HEAL_BLOCK
)
# A move or switch already resolved before action (Pursuit on a switching Pokemon)
NO_ACTION = -50

@njit
def _pass_baton(old, new):
    """Baton Pass: the stat stages and the passable volatiles go to the Pokemon coming in"""
    new[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1] = (
        old[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1]
    )
    new[_POK_VOL_STATUS] = old[_POK_VOL_STATUS] & BATON_PASS_VOLS
    new[_POK_CONFUSION_COUNTER] = old[_POK_CONFUSION_COUNTER]


@njit
def _bench_alive(battle_array, is_mine):
    """How many of that side's Pokemon besides the active are still alive"""
    base = 0 if is_mine else 6
    active = battle_array[_FIELD_MY_POK] if is_mine else battle_array[_FIELD_OPP_POK]
    n = 0
    for i in range(6):
        if i != active and battle_array[(base + i) * POK_LEN + _POK_CURRENT_HP] > 0:
            n += 1
    return n


@njit
def _random_bench(battle_array, is_mine, n):
    """Uniform pick among the n alive Pokemon on that side's bench, like pokeplatinum's reroll"""
    base = 0 if is_mine else 6
    active = battle_array[_FIELD_MY_POK] if is_mine else battle_array[_FIELD_OPP_POK]
    pick = random.randrange(n)
    for i in range(6):
        if i != active and battle_array[(base + i) * POK_LEN + _POK_CURRENT_HP] > 0:
            if pick == 0:
                return i
            pick -= 1
    return -1


@njit
def _force_switch(atk, defn, battle_array, target_is_mine):
    """
    Roar and Whirlwind: Suction Cups (unless Mold Breaker), Ingrain or an empty bench make them
    fail, and so does the level roll when the user is lower level (pokeplatinum
    BattleSystem_CanWhirlwind, also in trainer battles). The target is replaced by a random
    Pokemon from its bench. Returns True if it was dragged out
    """
    if defn[_POK_AB_ID] == _ABILITYNAMES_SUCTION_CUPS and atk[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER:
        return False
    if defn[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN:
        return False
    n = _bench_alive(battle_array, target_is_mine)
    if n == 0:
        return False
    atk_lv = atk[_POK_LEVEL]
    def_lv = defn[_POK_LEVEL]
    if atk_lv < def_lv and ((random.randrange(256) * (atk_lv + def_lv)) >> 8) + 1 <= def_lv // 4:
        return False
    slot = _random_bench(battle_array, target_is_mine, n)
    if target_is_mine:
        _switch_my_side(battle_array, defn, atk, slot)
    else:
        _switch_opp_side(battle_array, defn, atk, slot)
    return True


@njit
def _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx, baton=False):
    """Perform my-side switch-in bookkeeping, return the new active slice"""
    if baton:
        _pass_baton(current_pokemon, battle_array[(switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)])
    reset_switch_out(current_pokemon)
    battle_array[_FIELD_MY_POK] = switch_idx
    battle_array[_FIELD_AI_KNOWS] = 0
    battle_array[_FIELD_MY_LAST_MOVE] = 0
    battle_array[_FIELD_MY_ENTER_FIELD] = 1
    new_pokemon = battle_array[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    switch_in(new_pokemon, current_opp, battle_array, True)
    return new_pokemon


@njit
def _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch, baton=False):
    """Perform opp-side switch-in bookkeeping, return the new active slice"""
    if baton:
        _pass_baton(
            current_opp, battle_array[((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)]
        )
    reset_switch_out(current_opp)
    battle_array[_FIELD_OPP_POK] = opp_switch
    battle_array[_FIELD_OPP_ENTER_FIELD] = 1
    new_opp = battle_array[
        ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
    ]
    switch_in(new_opp, current_pokemon, battle_array, False)
    return new_opp


@njit
def start_of_turn(opp_move, switch_idx, battle_array, current_move=-1):
    """
    What happens before everything in the turn order, so switches and trainer items.
    Pursuit hits a Pokemon switching out before it leaves and uses up the pursuer's turn.
    Returns (current_move, opp_move) for action, NO_ACTION for a move already used
    """
    # TODO: Opponent Items
    opp_switch = -1
    opp_active = battle_array[_FIELD_OPP_POK]
    my_active = battle_array[_FIELD_MY_POK]
    current_pokemon = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
    if opp_move < 0:
        if opp_move <= -10:  #Item
            item_list = battle_array[_FIELD_AI_ITEM1:(_FIELD_AI_ITEM1+4)]
            slot = -(opp_move // 10) - 1  #Items are -10, -20, -30, -40
            trainer_ai_items(current_opp, item_list[slot])
            item_list[slot] = 0  # Item used, so goes to 0
        else:
            opp_switch = opp_move + 6 #Before I subtracted -6 from idx that's why +6 so it's 0..5

    if switch_idx >= 0 and opp_switch >= 0:
        my_s, opp_s = check_speed(
            current_pokemon, current_opp, battle_array[_FIELD_WEATHER]
        )
        speed_tie = my_s == opp_s and random.getrandbits(1)
        if my_s > opp_s or speed_tie:
            current_pokemon = _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
            _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)
        else:
            current_opp = _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)
            _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
        return current_move, opp_move

    if opp_switch >= 0:
        if _pursuit(current_pokemon, current_opp, current_move, True, battle_array):
            current_move = NO_ACTION
        _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)

    if switch_idx >= 0:
        if opp_move >= 0 and _pursuit(current_opp, current_pokemon, opp_move, False, battle_array):
            opp_move = NO_ACTION
        _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
    return current_move, opp_move


@njit
def _pursuit(atk, defn, slot, is_mine, battle_array):
    """
    pokeplatinum BtlCmd_TryPursuit: the pursuer hasn't moved, is alive and not asleep or frozen,
    its move (the encored one if Encore holds) is Pursuit with PP left. It hits at double power
    before the switch, the other checks of a normal turn (paralysis, confusion) don't happen.
    Returns True if Pursuit was used
    """
    if slot < 0 or atk[_POK_CURRENT_HP] <= 0:
        return False
    slot = _encore_slot(atk, slot)
    if slot >= 4 or atk[_POK_STATUS] == _STATUS_SLEEP or atk[_POK_STATUS] == _STATUS_FREEZE:
        return False
    mv = atk[OFFSET_MOVE + slot * MOVE_STRIDE : OFFSET_MOVE + (slot + 1) * MOVE_STRIDE]
    if mv[_MOVE_ID] != _MOVENAME_PURSUIT or mv[_MOVE_PP] <= 0:
        return False
    mv[_MOVE_PP] -= 1
    atk[_POK_LAST_MOVE_ID] = mv[_MOVE_ID]
    if is_mine:
        battle_array[_FIELD_MY_LAST_MOVE] = mv[_MOVE_ID]
        battle_array[_FIELD_AI_KNOWS] |= AI_KNOWS_MOVES[slot]
    doubled = mv.copy()
    doubled[_MOVE_POWER] *= 2
    weather = battle_array[_FIELD_WEATHER]
    if calculate_hit_miss(doubled, atk, defn, weather) == _MOVEOUTCOME_HIT:
        ps_moves(atk, defn, doubled, weather, False, False, battle_array[side_base(not is_mine)])
        if is_mine:
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = mv[_MOVE_TYPE]
        if defn[_POK_CURRENT_HP] <= 0 and defn[_POK_VOL_STATUS] & _VOLSTATUS_DESTINY_BOND:
            mark_hurt(atk)
            atk[_POK_CURRENT_HP] = 0
    return True


@njit
def _resolve_move_damage(attacker, defender, move, weather, def_side=0):
    """Figure out how much damage this hit does, independent of applying it.
    def_side is the defender's Field.SIDE_COND"""
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE:
        return struggle(attacker, defender, False, def_side)
    move_damage = move[_MOVE_DAMAGE]
    if not move_damage:
        crit = calculate_crit(attacker, defender, move, def_side)
        return calculate_damage(attacker, defender, move, weather, crit, None, def_side)
    if move_damage == _DAMAGESOURCES_LEVEL:
        return attacker[_POK_LEVEL]
    if move_damage == _DAMAGESOURCES_PSYWAVE:
        return max(1, attacker[_POK_LEVEL] * (random.randint(0, 10) + 5) // 10)
    if move_damage == _DAMAGESOURCES_BIDE:
        # Bide damage
        dmg = attacker[_POK_DMG_TAKEN]*2
        attacker[_POK_DMG_TAKEN] = 0
        # I think this if is not needed, but just to be safe its here
        if attacker[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
            attacker[_POK_VOL_STATUS] -= _VOLSTATUS_BIDE
        return dmg
    if move_damage in RECORD_DAMAGE:
        dmg = attacker[_POK_DMG_TAKEN]*2
        attacker[_POK_DMG_TAKEN] = 0
        return dmg
    # if move damage is a positive int, it means that is a fixed damage so just return it
    return move_damage


@njit
def _apply_move_damage(attacker, defender, move, damage):
    """Subtracts HP, checks contact abilities, flinch, item-on-damage, and Aftermath on kill.
    Returns (flinch, both_dead)"""
    if damage > 0:
        mark_hurt(defender)
    if damage < defender[_POK_CURRENT_HP]:
        defender[_POK_CURRENT_HP] -= damage
        # Rage builds on every damaging hit the user survives
        if defender[_POK_VOL_STATUS] & _VOLSTATUS_RAGE and damage > 0:
            defender[_POK_ATTACK_STAT_STAGE] = min(6, defender[_POK_ATTACK_STAT_STAGE] + 1)
        flinch = False
        if (
            move[_FLAGS_CONTACT]
            and (
                attacker[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_CONTACT
                or defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_CONTACT
            )
        ):
            contact_ability(attacker, defender)
        if move[_SEC_VOL_STATUS] & _VOLSTATUS_FLINCH:
            flinch = flinch_checker(move, defender)
        elif move[_SEC_VOL_STATUS2] & _VOLSTATUS_FLINCH:
            flinch = flinch_checker(move, defender, True)
        if defender[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
            item_on_rdmg(defender)
        return flinch

    defender[_POK_CURRENT_HP] = 0
    # Aftermath damage after kill
    if (
        defender[_POK_AB_ID] == _ABILITYNAMES_AFTERMATH
        and move[_FLAGS_CONTACT]
        and move[_MOVE_DAMAGE] != 0  # For some reason they don't trigger it
        and attacker[_POK_AB_ID] != _ABILITYNAMES_DAMP
    ):
        dmg = attacker[_POK_MAX_HP] // 4
        mark_hurt(attacker)
        if dmg < attacker[_POK_CURRENT_HP]:
            attacker[_POK_CURRENT_HP] -= dmg
            if attacker[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
                item_on_rdmg(attacker)
        else:
            attacker[_POK_CURRENT_HP] = 0
    return False


@njit
def _ps_moves_core(attacker, defender, move, weather, def_side=0):
    """
    Checks for damage and for flinch. Also returns the HP the defender actually lost
    """
    damage = endure_damage(
        defender, _resolve_move_damage(attacker, defender, move, weather, def_side)
    )
    dealt = min(damage, defender[_POK_CURRENT_HP])
    flinch= _apply_move_damage(attacker, defender, move, damage)
    return flinch, damage, dealt


@njit
def _recoil(attacker, move, dealt):
    """Recoil after the hit, Struggle's comes from max HP and the rest from the damage dealt"""
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE:
        apply_recoil(attacker, struggle_recoil(attacker))
    elif move[_MOVE_RECOIL]:
        apply_recoil(attacker, move_recoil(move, dealt))


@njit
def ps_moves_multihit(attacker, defender, move, weather, rec_p, rec_s, def_side=0):
    """Physical or Special multihit moves, where I need to calculate damage and secondary effects"""
    mult_hit_min = move[_MOVE_MULTI_HIT_MIN]
    mult_hit_max = move[_MOVE_MULTI_HIT_MAX]
    dmg = 0
    dealt_total = 0
    flinch = False
    if mult_hit_min == 2 and mult_hit_max == 5:
        multhit = MULTIHIT_PROB[random.getrandbits(3)]
    elif mult_hit_min == mult_hit_max:
        multhit = mult_hit_min
    else:
        raise ValueError("Moves that are variable and not 2-5 shouldn't exit, check DB")
    for i in range(multhit):
        if i and defender[_POK_CURRENT_HP]<=0:
            break
        flinch_c, damage, dealt = _ps_moves_core(attacker, defender, move, weather, def_side)
        if flinch_c:
            flinch = True
        dmg += damage
        dealt_total += dealt
        # Check for secondary effects and apply them
        if move[_SEC_CHANCE]:
            sec_effects(move, attacker, defender, weather, def_side)

    _recoil(attacker, move, dealt_total)
    if move[_MOVE_DRAIN]:
        drain(attacker, move, dealt_total)

    if defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        #Only last damage counts i think, needs check TODO
        defender[_POK_DMG_TAKEN] += damage
    if (
        (rec_p and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL)
        or (rec_s and move[_MOVE_CATEGORY] == _MOVECATEGORY_SPECIAL)
    ):
        #Only last damage counts i think, needs check TODO
        defender[_POK_DMG_TAKEN] = damage

    return flinch


@njit
def ps_moves(attacker, defender, move, weather, rec_p, rec_s, def_side=0):
    """Physical or Special moves, where I need to calculate damage and secondary effects.
    def_side is the defender's Field.SIDE_COND"""
    flinch, damage, dealt = _ps_moves_core(attacker, defender, move, weather, def_side)

    _recoil(attacker, move, dealt)
    if move[_MOVE_DRAIN]:
        drain(attacker, move, dealt)

    # Check for secondary effects and apply them
    if move[_SEC_CHANCE]:
        sec_effects(move, attacker, defender, weather, def_side)

    if defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        defender[_POK_DMG_TAKEN] += damage
    if (
        (rec_p and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL)
        or (rec_s and move[_MOVE_CATEGORY] == _MOVECATEGORY_SPECIAL)
    ):
        defender[_POK_DMG_TAKEN] = damage

    if move[_MOVE_ID] == _MOVENAME_BUG_BITE and defender[_ITEM_ITEM_TYPE] == _ITEMTYPE_BERRY:
        eat_berry_bug_bite(attacker, defender)
    elif (
        move[_MOVE_ID] == _MOVENAME_COVET
        and defender[_ITEM_ITEM_TYPE]
        and not attacker[_ITEM_ITEM_TYPE]
    ):
        switch_items(attacker, defender)

    return flinch


@njit
def _consec_before_move(atk, mv, slot):
    """Rollout/Ice Ball lock in on their first use, any other move resets Fury Cutter's count"""
    move_id = mv[_MOVE_ID]
    if move_id in ROLLOUT_MOVES:
        if atk[_POK_LOCKED_MOVE] == -1:
            atk[_POK_LOCKED_MOVE] = slot
            atk[_POK_CONSEC_COUNT] = 0
    elif move_id != _MOVENAME_FURY_CUTTER:
        atk[_POK_CONSEC_COUNT] = 0


@njit
def _consec_on_hit(atk, mv):
    """Fury Cutter, Rollout and Ice Ball count their consecutive hits, the power reads it"""
    move_id = mv[_MOVE_ID]
    if move_id == _MOVENAME_FURY_CUTTER or move_id in ROLLOUT_MOVES:
        atk[_POK_CONSEC_COUNT] = min(atk[_POK_CONSEC_COUNT] + 1, FURY_CUTTER_MAX_COUNT)


@njit
def _clear_charge(atk, mv):
    """Charge lasts until the user's next move attempt that isn't Charge"""
    if mv[_MOVE_ID] != _MOVENAME_CHARGE:
        atk[_POK_VOL_STATUS] &= ~_VOLSTATUS_CHARGE


@njit
def _set_side_condition(cond, battle_array, side):
    """
    Screens, Mist, Safeguard and Lucky Chant last 5 turns and fail while up, Stealth Rock fails if
    already set and Toxic Spikes stacks up to 2 layers. side is that side's Field.SIDE_COND
    """
    if cond == _SIDECONDITION_TOXIC_SPIKES:
        layers = battle_array[side + SIDE_TOXIC_SPIKES]
        if layers < TOXIC_SPIKES_MAX:
            battle_array[side + SIDE_TOXIC_SPIKES] = layers + 1
            battle_array[side] |= cond
        return
    if battle_array[side] & cond:
        return
    battle_array[side] |= cond
    for bit, turns in TIMED_SIDE_CONDITIONS:
        if bit == cond:
            battle_array[side + turns] = FIELD_EFFECT_TURNS


@njit
def _move_weather(move_id):
    """Weather the move sets, 0 if it isn't a weather move"""
    for weather_move, weather in WEATHER_MOVES:
        if move_id == weather_move:
            return weather
    return 0


@njit
def _set_weather(battle_array, weather):
    """Rain Dance and Sandstorm fail under the same weather, else it lasts 5 turns.
    TODO: Damp Rock, Smooth Rock"""
    if battle_array[_FIELD_WEATHER] == weather:
        return
    battle_array[_FIELD_WEATHER] = weather
    battle_array[_FIELD_WEATHER_DURATION] = FIELD_EFFECT_TURNS


@njit
def _clear_side(battle_array, side, conds):
    """Removes these side conditions with their turn counters and Toxic Spikes layers"""
    battle_array[side] &= ~conds
    for bit, turns in TIMED_SIDE_CONDITIONS:
        if bit & conds:
            battle_array[side + turns] = 0
    if conds & _SIDECONDITION_TOXIC_SPIKES:
        battle_array[side + SIDE_TOXIC_SPIKES] = 0


@njit
def _after_hit_field(atk, mv, battle_array, atk_side, def_side):
    """
    Brick Break shatters the target side's screens, Rapid Spin frees the user from a bind and Leech
    Seed and clears the hazards on its own side. Both only once the move hit
    """
    move_id = mv[_MOVE_ID]
    if move_id == _MOVENAME_BRICK_BREAK:
        _clear_side(battle_array, def_side, SCREENS)
    elif move_id == _MOVENAME_RAPID_SPIN:
        atk[_POK_VOL_STATUS] &= ~(_VOLSTATUS_LEECH_SEED | _VOLSTATUS_PARTIALLY_TRAPPED)
        atk[_POK_TRAP_TURNS] = 0
        _clear_side(battle_array, atk_side, RAPID_SPIN_CLEARS)


@njit
def _execute_move_slot(
        atk, defn, mv, is_mine, current_move, opp_move,
        flinch_in, slot_num, is_last, battle_array, weather,
        rec_p=False, rec_s=False
):
    """
    Run one move-slot (whichever attacker acts in this position) end to end:
    early-return checks, PP, last-move bookkeeping, charge/lock, hit check,
    damage/effects, trainer-ai bookkeeping.
    is_last: nothing acts after this slot (Protect and Endure fail).
    Returns the flinch this slot produced (False if it didn't attack/hit).
    """
    if atk[_POK_CURRENT_HP] <= 0:
        return False
    if early_returns(atk, defn, slot_num, flinch_in, mv):
        # A turn without the move resets Protect's consecutive count and the last move
        atk[_POK_PROTECT_COUNT] = 0
        atk[_POK_LAST_MOVE_ID] = 0
        return False
    atk[_POK_LAST_MOVE_ID] = mv[_MOVE_ID]
    if mv[_MOVE_ID] not in STALL_MOVES:
        atk[_POK_PROTECT_COUNT] = 0

    if mv[_MOVE_ID] != _MOVENAME_STRUGGLE:
        if atk[_POK_LOCKED_MOVE] == -1:
            mv[_MOVE_PP] -= 1
        if is_mine:
            battle_array[_FIELD_MY_LAST_MOVE] = mv[_MOVE_ID]
            battle_array[_FIELD_AI_KNOWS] |= AI_KNOWS_MOVES[current_move]
    elif is_mine:
        battle_array[_FIELD_MY_LAST_MOVE] = -1  #-1 Means Struggle

    # Charge moves are positive so they don't do anything first turn
    if mv[_MOVE_CHARGE_RECHARGE] > 0 and atk[_POK_LOCKED_MOVE] == -1:
        atk[_POK_CHARGE_RECHARGE] = mv[_MOVE_CHARGE_RECHARGE]
        atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
        if mv[_MOVE_VOL_STATUS] & _VOLSTATUS_BIDE:
            atk[_POK_VOL_STATUS] += _VOLSTATUS_BIDE
        if mv[_MOVE_ID] in SEMI_INVULNERABLE_MOVES:
            atk[_POK_VOL_STATUS] |= _VOLSTATUS_SEMI_INVULNERABLE
        return False

    # Reset locked Move
    if mv[_MOVE_CHARGE_RECHARGE] > 0:
        atk[_POK_LOCKED_MOVE] = -1
        atk[_POK_VOL_STATUS] &= ~_VOLSTATUS_SEMI_INVULNERABLE
    # The foe fainted (recoil, Explosion...): PP is spent, a move aimed at it fails.
    # TODO: Some moves still go through, like future sight
    if defn[_POK_CURRENT_HP] <= 0 and mv[_MOVE_TARGET] not in NO_FOE_TARGETS:
        return False

    _consec_before_move(atk, mv, current_move if is_mine else opp_move)
    if mv[_MOVE_ID] == _MOVENAME_NATURAL_GIFT and not natural_gift(atk, mv):
        return False
    if mv[_MOVE_ID] in STALL_MOVES:
        try_protect(atk, mv[_MOVE_ID], is_last)
        return False
    # Gen IV Feint fails unless the target is protecting, then it lifts the protection
    if mv[_MOVE_ID] == _MOVENAME_FEINT:
        if not defn[_POK_VOL_STATUS] & _VOLSTATUS_PROTECT:
            return False
        defn[_POK_VOL_STATUS] &= ~_VOLSTATUS_PROTECT

    move_hit = calculate_hit_miss(mv, atk, defn, weather)
    if move_hit != _MOVEOUTCOME_HIT:
        if not (atk[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR and move_hit in UPROAR_KEEPS_ON):
            unlock_move(atk)
        return False

    atk_side = side_base(is_mine)
    def_side = side_base(not is_mine)
    if mv[_MOVE_CATEGORY] in PHYSICAL_SPECIAL:
        _consec_on_hit(atk, mv)
        if mv[_MOVE_MULTI_HIT_MIN]:
            flinch = ps_moves_multihit(atk, defn, mv, weather, rec_p, rec_s, battle_array[def_side])
        else:
            flinch = ps_moves(atk, defn, mv, weather, rec_p, rec_s, battle_array[def_side])
        _after_hit_field(atk, mv, battle_array, atk_side, def_side)
        if mv[_MOVE_ID] in ROLLOUT_MOVES and atk[_POK_CONSEC_COUNT] >= ROLLOUT_MAX_USES:
            unlock_move(atk)
        if mv[_MOVE_ID] == _MOVENAME_RAGE:
            atk[_POK_VOL_STATUS] |= _VOLSTATUS_RAGE
        # Uproar locks in on its first hit for 3-6 turns, this one included
        if mv[_MOVE_ID] == _MOVENAME_UPROAR and not atk[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR:
            atk[_POK_VOL_STATUS] |= _VOLSTATUS_UPROAR
            atk[_POK_UPROAR_TURNS] = random.randint(3, 6)
            atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
        # Wrap and co. trap a target that survived for 3-6 turns, it isn't refreshed
        if (
            mv[_MOVE_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED
            and defn[_POK_CURRENT_HP] > 0
            and not defn[_POK_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED
        ):
            defn[_POK_VOL_STATUS] |= _VOLSTATUS_PARTIALLY_TRAPPED
            defn[_POK_TRAP_TURNS] = random.randint(3, 6)
        # Destiny Bond, after drain and recoil like the Gen IV faint check
        if defn[_POK_CURRENT_HP] <= 0 and defn[_POK_VOL_STATUS] & _VOLSTATUS_DESTINY_BOND:
            mark_hurt(atk)
            atk[_POK_CURRENT_HP] = 0
        # Information for trainer ai logic
        if is_mine:
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = mv[_MOVE_TYPE]
        # Check to see if the move from the attacker thawed the defender
        if defn[_POK_STATUS] == _STATUS_FREEZE:
            thaw(mv, defn)
        return flinch

    if mv[_MOVE_FORCE_SWITCH]:
        _force_switch(atk, defn, battle_array, not is_mine)
        return False
    if mv[_MOVE_SELF_SWITCH]:
        _baton_pass(atk, defn, battle_array, is_mine)
        return False
    if mv[_MOVE_SIDE_CONDITION]:
        _set_side_condition(
            mv[_MOVE_SIDE_CONDITION], battle_array,
            def_side if mv[_MOVE_TARGET] == FOE_SIDE_TARGET else atk_side
        )
        return False
    move_weather = _move_weather(mv[_MOVE_ID])
    if move_weather:
        _set_weather(battle_array, move_weather)
        return False
    calculate_effects(atk, defn, mv, weather, battle_array[def_side])
    return False


@njit
def _baton_pass(atk, defn, battle_array, is_mine):
    """
    Fails with nobody left to switch in. Mine stops the turn in the Baton Pass phase so I pick
    the replacement, the AI picks its own right away with its post-KO logic (pokeplatinum
    Task_TrainerShowPartyMenu → BattleAI_PostKOSwitchIn)
    """
    if _bench_alive(battle_array, is_mine) == 0:
        return
    if is_mine:
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_BATON_PASS
        return
    opp_idx = battle_array[_FIELD_OPP_POK]
    i = sub_after_death(
        battle_array[(6 * POK_LEN):(12 * POK_LEN)], defn, atk, battle_array[_FIELD_MY_SIDE_COND],
        battle_array[_FIELD_WEATHER], opp_idx
    )
    _switch_opp_side(battle_array, atk, defn, i, True)


@njit
def _encore_slot(pok, slot):
    """Encore forces the encored move when the Pokemon acts, also on the turn Encore lands"""
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_ENCORE and 0 <= slot < 4:
        return pok[_POK_ENCORE_TURNS] & SLOT_MASK
    return slot


@njit
def action(current_move, opp_move, battle_array):
    """Where the moves are calculated"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[_FIELD_WEATHER]
    p1_switch = False
    p2_switch = False
    flinch = False
    if current_move < 0 and opp_move < 0:
        return  # Check if neither used an action, if so early return
    if current_move < 0:
        p1_switch = True
    if opp_move < 0:  # Switches mid battle are (-6..-1) and potions are -10..-40
        # TODO: Check everything if opponent switches, specially if they die on entering
        p2_switch = True

    mv1_slot, mv2_slot, count, first_is_mine = move_order(
        current_pokemon,
        current_move,
        current_opp,
        opp_move,
        p1_switch,
        p2_switch,
        weather
    )
    if count == 0:
        return
    atk1 = current_pokemon if first_is_mine else current_opp
    def1 = current_opp     if first_is_mine else current_pokemon
    atk2 = current_opp     if first_is_mine else current_pokemon
    def2 = current_pokemon if first_is_mine else current_opp

    mv1 = (atk1[OFFSET_MOVE + mv1_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv1_slot + 1) * MOVE_STRIDE]
        if mv1_slot != 10 else STRUGGLE.copy())

    mv2 = (atk2[OFFSET_MOVE + mv2_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv2_slot + 1) * MOVE_STRIDE]
        if mv2_slot != 10 else STRUGGLE.copy())

    if mv2_slot == -1:
        record_phy = False
        record_sp  = False
    else:
        record_phy = mv2[_MOVE_DAMAGE] == _DAMAGESOURCES_COUNTER
        record_sp  = mv2[_MOVE_DAMAGE] == _DAMAGESOURCES_MAGIC_COAT

    my_before = battle_array[_FIELD_MY_POK]
    opp_before = battle_array[_FIELD_OPP_POK]
    if count >= 1:
        flinch = _execute_move_slot(
            atk1, def1, mv1, first_is_mine, current_move, opp_move,
            flinch, 1, count == 1, battle_array, weather, record_phy, record_sp
        )
        _clear_charge(atk1, mv1)

    # My Baton Pass: the turn waits for my pick, the slower opponent's move runs after it
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
        if count >= 2:
            battle_array[_FIELD_PENDING_OPP_MOVE] = mv2_slot + 1
        return
    if count >= 2:
        # Roar or Whirlwind dragged the slower Pokemon out, the one coming in doesn't move
        if battle_array[_FIELD_OPP_POK if first_is_mine else _FIELD_MY_POK] != (
            opp_before if first_is_mine else my_before
        ):
            return
        # The AI Baton Passed first, my move goes into the one it sent
        if not first_is_mine and battle_array[_FIELD_OPP_POK] != opp_before:
            def2 = battle_array[
                ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
            ]

    if count >= 2:
        # Encore landed before the slower Pokemon moved
        enc_slot = _encore_slot(atk2, mv2_slot)
        if enc_slot != mv2_slot:
            mv2_slot = enc_slot
            mv2 = atk2[OFFSET_MOVE + mv2_slot * MOVE_STRIDE : OFFSET_MOVE + (mv2_slot + 1) * MOVE_STRIDE]
            if first_is_mine:
                opp_move = mv2_slot
            else:
                current_move = mv2_slot
        _execute_move_slot(
            atk2, def2, mv2, not first_is_mine, current_move, opp_move,
            flinch, 2, True, battle_array, battle_array[_FIELD_WEATHER]
        )
        _clear_charge(atk2, mv2)


@njit
def _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field) -> bool:
    """Applies residual damage, checks faint, and triggers items. Returns True if fainted."""
    if dmg <= 0:
        return False
    hp = pok[_POK_CURRENT_HP]
    pok[_POK_CURRENT_HP] = 0 if dmg > hp else hp - dmg
    if pok[_POK_CURRENT_HP] <= 0:
        if enter_field:
            battle_array[enter_field_flag_idx] = 0
        return True
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)
    return False


@njit
def _residual_heal(pok):
    """Ingrain and Aqua Ring heal 1/16 of max HP"""
    max_hp = pok[_POK_MAX_HP]
    if pok[_POK_CURRENT_HP] < max_hp:
        pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + max(1, max_hp // 16))


@njit
def _yawn(pok, foe):
    """
    Yawn counts down at the end of the turn, at 0 the target falls asleep if it has no status
    and there's no uproar
    """
    pok[_POK_YAWN_TURNS] -= 1
    if pok[_POK_YAWN_TURNS] > 0:
        return
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_YAWN
    if pok[_POK_STATUS] == 0 and not sleep_blocked(pok, foe):
        pok[_POK_STATUS] = _STATUS_SLEEP
        pok[_POK_SLEEP_COUNTER] = TURNS_2_5[random.getrandbits(2)]


@njit
def _uproar_wake(pok):
    """The uproar wakes up a sleeping Pokemon that isn't Soundproof"""
    if (
        pok[_POK_STATUS] == _STATUS_SLEEP
        and pok[_POK_CURRENT_HP] > 0
        and pok[_POK_AB_ID] != _ABILITYNAMES_SOUNDPROOF
    ):
        pok[_POK_STATUS] = 0
        pok[_POK_SLEEP_COUNTER] = 0


@njit
def _count_down_slot_lock(pok, counter_idx, vol):
    """Encore/Disable counter (turns * SLOT_STEP + slot): one less turn, ends a turn after reaching 0"""
    if pok[counter_idx] >= SLOT_STEP:
        pok[counter_idx] -= SLOT_STEP
    else:
        pok[_POK_VOL_STATUS] &= ~vol
        pok[counter_idx] = 0


@njit
def _residual_weather(pok, weather, enter_field_flag_idx, battle_array):
    """Weather heal and damage for one side, Gen IV runs it for everyone before any other residual"""
    if pok[_POK_CURRENT_HP] <= 0:
        return
    heal_weather(pok, weather)
    if pok[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD and weather not in WEATHER_NOT_END_OF_TURN:
        w_dmg = weather_dmg(pok, weather, pok[_POK_MAX_HP])
        _apply_residual_damage(
            pok, w_dmg, enter_field_flag_idx, battle_array, battle_array[enter_field_flag_idx]
        )


@njit
def _apply_residual(pok, foe, enter_field_flag_idx, battle_array):
    """
    Per-Pokemon residuals after the weather, on-residual ability, enter-field clear — one side.
    foe is the opposing active, which Leech Seed heals
    """
    """
    Gen IV order (pokeplatinum CheckMonConditions, Showdown gen4 residual suborders):
    Ingrain, Aqua Ring, Speed Boost, Leech Seed, Psn/Tox, Burn, Curse, Bind, Uproar, Disable,
    Encore, Taunt, Yawn
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return
    enter_field = battle_array[enter_field_flag_idx]
    is_magic_guard = pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD

    # 1. Ingrain and Aqua Ring
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN:
        _residual_heal(pok)
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_AQUA_RING:
        _residual_heal(pok)

    # 2. Speed Boost
    if pok[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_RESIDUAL:
        on_residual(pok, enter_field)

    # 3. Leech Seed
    if (
        pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED
        and not is_magic_guard
        and foe[_POK_CURRENT_HP] > 0
    ):
        dmg = max(1, pok[_POK_MAX_HP] // 8)
        dealt = min(dmg, pok[_POK_CURRENT_HP])
        fainted = _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field)
        foe[_POK_CURRENT_HP] = min(foe[_POK_MAX_HP], foe[_POK_CURRENT_HP] + dealt)
        if fainted:
            return

    # 4. Psn/Tox
    status = pok[_POK_STATUS]
    if status == _STATUS_POISON or status == _STATUS_TOXIC:
        if status == _STATUS_TOXIC:
            badly_psn = pok[_POK_BADLY_POISON]
            if badly_psn < 1:
                badly_psn = 1
            dmg = pok[_POK_MAX_HP] * badly_psn // 16
            pok[_POK_BADLY_POISON] = badly_psn + 1
        else:
            dmg = pok[_POK_MAX_HP] // 8
        if not is_magic_guard:
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 5. Burn
    if pok[_POK_STATUS] == _STATUS_BURN:
        if not is_magic_guard:
            dmg = pok[_POK_MAX_HP] // 8
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 6. Curse
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
        if not is_magic_guard:
            dmg = pok[_POK_MAX_HP] // 4
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 7. Bind, freed once the binder has fainted
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED:
        if foe[_POK_CURRENT_HP] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
        else:
            pok[_POK_TRAP_TURNS] -= 1
            if pok[_POK_TRAP_TURNS] <= 0:
                pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
            elif not is_magic_guard:
                dmg = max(1, pok[_POK_MAX_HP] // 16)
                if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                    return

    # 8. Uproar, wakes everyone up then counts down
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR:
        _uproar_wake(pok)
        _uproar_wake(foe)
        pok[_POK_UPROAR_TURNS] -= 1
        if pok[_POK_UPROAR_TURNS] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_UPROAR
            pok[_POK_LOCKED_MOVE] = -1

    # 9. Disable
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_DISABLE:
        _count_down_slot_lock(pok, _POK_DISABLE_TURNS, _VOLSTATUS_DISABLE)

    # 10. Encore, also ends when the encored move is out of PP
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_ENCORE:
        slot = pok[_POK_ENCORE_TURNS] & SLOT_MASK
        if pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP] == 0:
            pok[_POK_ENCORE_TURNS] = slot
        _count_down_slot_lock(pok, _POK_ENCORE_TURNS, _VOLSTATUS_ENCORE)

    # 11. Taunt
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT:
        pok[_POK_TAUNT_TURNS] -= 1
        if pok[_POK_TAUNT_TURNS] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_TAUNT

    # 12. Yawn
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_YAWN:
        _yawn(pok, foe)

    if enter_field:
        battle_array[enter_field_flag_idx] = 0


@njit
def _count_down_field(battle_array):
    """
    pokeplatinum CheckFieldConditions, before any Pokemon's residual: Reflect, Light Screen, Mist,
    Safeguard and Lucky Chant of both sides, then the weather. Each one counts the turn it was set
    in, and a weather that ends does nothing this turn. A weather with no turns left set is
    permanent. Returns the weather for the rest of the turn
    """
    if (battle_array[_FIELD_MY_SIDE_COND] | battle_array[_FIELD_OPP_SIDE_COND]) & TIMED_SIDE_MASK:
        for bit, turns in TIMED_SIDE_CONDITIONS:
            for side in SIDES:
                if battle_array[side] & bit:
                    battle_array[side + turns] -= 1
                    if battle_array[side + turns] <= 0:
                        battle_array[side] &= ~bit
                        battle_array[side + turns] = 0
    if battle_array[_FIELD_WEATHER_DURATION] > 0:
        battle_array[_FIELD_WEATHER_DURATION] -= 1
        if battle_array[_FIELD_WEATHER_DURATION] == 0:
            battle_array[_FIELD_WEATHER] = 0
    return battle_array[_FIELD_WEATHER]


@njit
def _replace_fainted_opp(battle_array, current_pokemon, current_opp):
    """
    The AI sends in a replacement for its fainted active, and keeps doing it while the one it sent
    faints to the hazards on entry. Returns the slot sent last, -1 if it had nobody left
    """
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    i = -1
    for _ in range(6):
        if count_party(opp_pty) == 0:
            break
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp, battle_array[_FIELD_MY_SIDE_COND],
            battle_array[_FIELD_WEATHER]
        )
        battle_array[_FIELD_OPP_POK] = i
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
        current_opp = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        switch_in(current_opp, current_pokemon, battle_array, False)
        if current_opp[_POK_CURRENT_HP] > 0:
            break
    return i


@njit
def end_of_turn(battle_array):
    """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
    items like leftovers\n
    Weather damage like hail, sandstorm"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[_FIELD_WEATHER]

    # TODO: Items
    weather = _count_down_field(battle_array)

    # Gen IV re-sorts by speed before the end of the turn, then weather hits everyone before the
    # per-Pokemon residuals
    my_s, opp_s = check_speed(current_pokemon, current_opp, weather)
    if my_s > opp_s or (my_s == opp_s and random.getrandbits(1)):
        first, second = current_pokemon, current_opp
        first_flag, second_flag = _FIELD_MY_ENTER_FIELD, _FIELD_OPP_ENTER_FIELD
    else:
        first, second = current_opp, current_pokemon
        first_flag, second_flag = _FIELD_OPP_ENTER_FIELD, _FIELD_MY_ENTER_FIELD
    _residual_weather(first, weather, first_flag, battle_array)
    _residual_weather(second, weather, second_flag, battle_array)
    _apply_residual(first, second, first_flag, battle_array)
    _apply_residual(second, first, second_flag, battle_array)

    # If Opponent is dead
    if current_opp[_POK_CURRENT_HP] == 0 and current_pokemon[_POK_CURRENT_HP] != 0:
        return _replace_fainted_opp(battle_array, current_pokemon, current_opp)
    return -1


@njit
def _selected_move_id(pok, move_idx):
    """Id of the move picked this turn, 0 for a switch or an item (Battler_SelectedMove)"""
    if move_idx == 10:
        return _MOVENAME_STRUGGLE
    if move_idx < 0:
        return 0
    return pok[OFFSET_MOVE + move_idx * MOVE_STRIDE + _MOVE_ID]


@njit
def _rage_glitch(pok, move_id):
    """
    Gen IV Rage glitch (pokeplatinum PRE_MOVE_ACTION_STATE_CHECK_RAGE_FLAG): a raging Pokemon
    that picks anything but Rage keeps Rage and loses its other volatiles instead
    """
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_RAGE and move_id != _MOVENAME_RAGE:
        pok[_POK_VOL_STATUS] &= ~RAGE_GLITCH_CLEARS


@njit
def turn_sim(opp_move, current_action, battle_array):
    """One turn"""
    if current_action[0] == _ACTIONTYPE_MOVE:
        switch_idx = -1
        current_move = current_action[1]
    else:
        current_move = -1
        switch_idx = current_action[1]
    my_pok = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    opp_pok = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    _rage_glitch(my_pok, _selected_move_id(my_pok, current_move))
    _rage_glitch(opp_pok, _selected_move_id(opp_pok, opp_move))
    current_move, opp_move = start_of_turn(opp_move, switch_idx, battle_array, current_move)
    action(current_move, opp_move, battle_array)
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
        return _BATTLEPHASE_BATON_PASS, battle_array[_FIELD_OPP_POK]
    return _finish_turn(battle_array)


@njit
def _finish_turn(battle_array):
    """End of turn and the turn counters, returns (phase, opp_idx) like turn_sim"""
    opp_idx = end_of_turn(battle_array)
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]

    current_pokemon[_POK_VOL_STATUS] &= ~TURN_VOLATILES
    current_opp[_POK_VOL_STATUS] &= ~TURN_VOLATILES

    if opp_idx == -1:
        opp_idx = battle_array[_FIELD_OPP_POK]
    if current_pokemon[_POK_CURRENT_HP] <= 0:
        return _BATTLEPHASE_DEATH_END_OF_TURN, opp_idx

    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    current_opp[_POK_TURNS_ACTIVE] += 1
    current_pokemon[_POK_TURNS_ACTIVE] += 1
    return _BATTLEPHASE_TURN_START, opp_idx


@njit
def switch_in_action(battle_array, switch_idx: int):
    """Grab the switch idx from MCTS and progress it"""
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    my_pty = battle_array[0:(6 * POK_LEN)]
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    if current_opp[_POK_CURRENT_HP] <= 0:
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp, battle_array[_FIELD_MY_SIDE_COND],
            battle_array[_FIELD_WEATHER]
        )
        opp_switch = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        my_switch = my_pty[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]

        # I actually don't know if when both are switching in the order matters, but its better be safe
        # than sorry
        my_s, opp_s = check_speed(
            my_switch, opp_switch, battle_array[_FIELD_WEATHER]
        )
        speed_tie= False
        if my_s == opp_s:
            if random.getrandbits(1):
                speed_tie = True

        if my_s > opp_s or speed_tie:
            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Opponent Pokemon
            current_opp = opp_switch
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0

            # Switch in effects after they are already switched
            switch_in(current_pokemon, current_opp, battle_array, True)
            switch_in(current_opp, current_pokemon, battle_array, False)
        else:
            # Opponent Pokemon
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
            current_opp = opp_switch

            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Switch in effects after they are already switched
            switch_in(current_opp, current_pokemon, battle_array, False)
            switch_in(current_pokemon, current_opp, battle_array, True)

        # Mine fainted to the hazards: I pick again, having seen who the AI sent
        if current_pokemon[_POK_CURRENT_HP] <= 0:
            battle_array[_FIELD_PHASE] = _BATTLEPHASE_DEATH_END_OF_TURN
            return
        if current_opp[_POK_CURRENT_HP] <= 0:
            _replace_fainted_opp(battle_array, current_pokemon, current_opp)
            current_opp = opp_pty[
                (battle_array[_FIELD_OPP_POK] * POK_LEN):((battle_array[_FIELD_OPP_POK]+1) * POK_LEN)
            ]

        battle_array[_FIELD_TURN] += 1
        current_opp[_POK_TURNS] += 1
        current_pokemon[_POK_TURNS] += 1
        current_opp[_POK_TURNS_ACTIVE] += 1
        current_pokemon[_POK_TURNS_ACTIVE] += 1
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
        return
    battle_array[_FIELD_MY_POK] = switch_idx
    current_pokemon = my_pty[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    switch_in(current_pokemon, current_opp, battle_array, True)
    # Fainted to the hazards, I pick again
    if current_pokemon[_POK_CURRENT_HP] <= 0:
        battle_array[_FIELD_AI_KNOWS] = 0
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_DEATH_END_OF_TURN
        return
    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    current_opp[_POK_TURNS_ACTIVE] += 1
    current_pokemon[_POK_TURNS_ACTIVE] += 1
    battle_array[_FIELD_AI_KNOWS] = 0
    battle_array[_FIELD_MY_LAST_MOVE] = 0
    battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START


@njit
def baton_pass_action(battle_array, switch_idx: int):
    """
    My pick for Baton Pass: switch with the stages and volatiles, run the opponent's move if it
    was slower, then the rest of the turn. Returns the phase, also stored in Field.PHASE
    """
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    current_pokemon = _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx, True)
    pending = battle_array[_FIELD_PENDING_OPP_MOVE] - 1
    battle_array[_FIELD_PENDING_OPP_MOVE] = 0
    battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
    if pending >= 0:
        slot = _encore_slot(current_opp, pending)
        mv = (current_opp[OFFSET_MOVE + slot * MOVE_STRIDE : OFFSET_MOVE + (slot + 1) * MOVE_STRIDE]
              if slot != 10 else STRUGGLE.copy())
        _execute_move_slot(
            current_opp, current_pokemon, mv, False, -1, slot, False, 2, True, battle_array,
            battle_array[_FIELD_WEATHER]
        )
        _clear_charge(current_opp, mv)
    phase, _opp_idx = _finish_turn(battle_array)
    battle_array[_FIELD_PHASE] = phase
    return phase
