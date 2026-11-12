"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from Engine.damage_calc import calculate_damage, calculate_ai_logic_damage
from Engine.engine_helper import move_blocked, imprisoned
from Engine.ability_helper import effective_weather, slot_move_type
from Engine.status_calc import last_move_slot
from Utils.jit import njit
from Utils.helper import (
    get_type_effectiveness, batch_independent_score_from_rand
)
from DataBase.MoveDB import MoveName, FIRE_WATER_ELECTRIC
from DataBase.PkDB import POKEMON_ABILITY_POOL
from Models.idx_const import (
    POK_LEN, MOVE_STRIDE, AB_LEN
)
from Models.constants import (
    _POK_MOVE1_ID, _POK_ITEM_ID, _POK_ID, _POK_AB_ID, _POK_CURRENT_HP, _POK_TYPE1,
    _POK_TYPE2, _ENEMY_AI_KNOWS_ABILITY, _POK_AB_KNOWN, _MOVE_ID, _MOVE_PP, _MOVE_CATEGORY,
    _MOVECATEGORY_STATUS, _MOVE_TYPE, _ABILITYNAMES_WONDER_GUARD, _POK_STATUS, _MOVENAME_WEATHER_BALL,
    _STATUS_SLEEP, _ABILITYNAMES_NATURAL_CURE, _POK_MAX_HP, _POK_ATTACK_STAT_STAGE,
    _POK_EVASION_STAT_STAGE,_FIELD_OPP_POK, _FIELD_MY_POK, _FIELD_TURN, _FIELD_WEATHER,
    _FIELD_GRAVITY_TURNS, _FIELD_TRICKROOM,
    _FIELD_AI_KNOWS, _FIELD_MY_LAST_MOVE, _FIELD_AI_TOOK_DMG_LAST_TURN, _FIELD_AI_ITEM1,
    _FIELD_AI_ITEM4, _POTIONS_POTION, _POTIONS_SUPER_POTION, _POTIONS_HYPER_POTION,
    _POTIONS_FULL_RESTORE, _POTIONS_FULL_HEAL, _POK_LOCKED_MOVE, _MOVE_DAMAGE,
    _MOVENAME_MAGNITUDE, _DAMAGESOURCES_LEVEL, _DAMAGESOURCES_PSYWAVE, _POK_LEVEL,
    _POK_VOL_STATUS, _VOLSTATUS_INGRAIN, _VOLSTATUS_PARTIALLY_TRAPPED, _FIELD_MY_SIDE_COND,
    _FIELD_OPP_SIDE_COND, _FIELD_MY_TOXIC_SPIKES, _FIELD_MY_SPIKES, _VOLSTATUS_PERISH_SONG, _POK_PERISH_TURNS,
    _MOVENAME_COPYCAT, _ABILITYNAMES_SHADOW_TAG, _ABILITYNAMES_ARENA_TRAP, _ABILITYNAMES_MAGNET_PULL,
    _TYPES_STEEL, _MOVE_POWER, _MOVENAME_HIDDEN_POWER, _MOVENAME_HEALING_WISH, _POK_VOL_STATUS2,
    _MOVENAME_U_TURN,
    _VOLSTATUS2_EMBARGO, _POK_HIDDEN_POWER_TYPE, _POK_HIDDEN_POWER_POWER, _VOLSTATUS2_MEAN_LOOK
)
from Models.trainer_ai_helper import (
    trainer_ai_effectiveness,
    POKEMON_HAS_RELEVANT_ABILITY,
    basic_flag,
    evaluate_attack_flag,
    expert_flag,
    check_super_ef_move_pty,
    check_any_damaging_move_pty,
    ABSORB_ABI,
    check_absorb_abi_pty,
    check_immunity_pty, check_resistance_pty,
    ai_move_view, quick_claw_guess, party_super_effective, on_damaging_turn
)
from Models.helper import count_party
from Models.item import embargoed

# mov_excep = ['Solar Blade', 'Spit Up', 'Eruption',
#             'Water Spout']
MOVE_EXCEP = (
    0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER,
    MoveName.FOCUS_PUNCH, MoveName.SUCKER_PUNCH, MoveName.HYPER_BEAM,
    # Recharge moves, Superpower and Head Smash (pokeplatinum sNoDamageCalcMoveEffects, Pokemow)
    MoveName.GIGA_IMPACT, MoveName.BLAST_BURN, MoveName.HYDRO_CANNON, MoveName.FRENZY_PLANT,
    MoveName.ROAR_OF_TIME, MoveName.ROCK_WRECKER, MoveName.SUPERPOWER, MoveName.HEAD_SMASH,
    # Charge turn moves (pokeplatinum sNoDamageCalcMoveEffects, Pokemow)
    MoveName.RAZOR_WIND, MoveName.SKY_ATTACK, MoveName.SKULL_BASH, MoveName.SOLAR_BEAM,
    # Power 1 in pokeplatinum and not an alt power move: never compared
    MoveName.COUNTER, MoveName.BIDE, MoveName.MIRROR_COAT, MoveName.FLAIL, MoveName.MAGNITUDE,
    MoveName.SUPER_FANG, MoveName.ENDEAVOR, MoveName.METAL_BURST,
    # OHKO moves: Basic_Main skips Fissure's damage scoring, Guillotine and Sheer Cold are power 1
    MoveName.FISSURE, MoveName.GUILLOTINE, MoveName.SHEER_COLD,
    # Pokemow's excluded moves
    MoveName.FLING,
    # Variable power (pokeplatinum sNoDamageCalcMoveEffects or power 1, Pokemow's excluded moves)
    MoveName.ERUPTION, MoveName.WATER_SPOUT, MoveName.REVERSAL, MoveName.WRING_OUT,
    MoveName.CRUSH_GRIP, MoveName.PUNISHMENT, MoveName.TRUMP_CARD, MoveName.PRESENT,
    MoveName.SPIT_UP,
)


@njit
def sub_after_death(
        ai_party, user_pok, deadmon, user_side=0, weather=0, exclude=-1, gravity=False
):
    """
    Implements the switch-in logic. user_side is user_pok's Field.SIDE_COND, its screens and the
    weather count in the damage (pokeplatinum BattleAI_PostKOSwitchIn). exclude is a slot that
    can't be picked, the active that's still in after Baton Pass. gravity counts in the move
    checks and the damage, not in the type-vs-type score

    Phase 1:
    --------
        * Consider only non-fainted teammates.
        * Select teammates that have at least one move that is supereffective (>1) vs user_pok.
        * If any such teammates exist, score each teammate by summing the effectiveness
        of each of their TYPE(S) versus user_pok (single-typed counted twice).
        Higher sum wins; ties broken by party order (lower index wins).

    Phase 2:
    ---------
        * If no Phase 1 candidate, for each non-fainted teammate compute the max damage any
        of its moves would do to user_pok (use calculate_damage). Apply the "255 overflow"
        rule: if damage > 255 -> damage = damage - 255.
        * Choose teammate with highest such max move damage. Ties broken by party order.

    Returns:
    -------
            index of chosen teammate in ai_party (int) or None if no valid candidate.

    """
    off = POK_LEN
    candidates = np.where(ai_party[_POK_CURRENT_HP::off] > 0)[0]
    candidates = candidates[candidates != exclude]
    if len(candidates) == 1:
        return candidates[0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]

    # Phase 1: collect indices of mons with at least one SE move
    phase1_indices = []
    for idx in candidates:
        pok = ai_party[off * idx: off * (idx + 1)]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            if mv[_MOVE_TYPE] == 0:
                break
            if party_super_effective(
                slot_move_type(pok, mv, weather), pok, user_pok, gravity, on_damaging_turn(mv)
            ):
                phase1_indices.append(idx)
                break

    if len(phase1_indices) > 0:
        # TODO: Check bugged list of Pokemon in document:
        # https://drive.google.com/file/d/1MpWJWc4wNTz2oA6QiPMmstLpSwHBlpRk/view
        # Score each mon by summing the effectiveness of each of its types vs user_pok
        if len(phase1_indices) == 1:
            return phase1_indices[0]

        # Score by type effectiveness, manual max (no key= in njit)
        best_idx = phase1_indices[0]
        best_score = -1.0
        for idx in phase1_indices:
            mon = ai_party[off * idx: off * (idx + 1)]
            t1 = mon[_POK_TYPE1]
            # single-typed counted twice
            t2 = mon[_POK_TYPE2] if mon[_POK_TYPE2] != 0 else mon[_POK_TYPE1]
            e1, d1 = get_type_effectiveness(t1, user_t1, user_t2)
            e2, d2 = get_type_effectiveness(t2, user_t1, user_t2)
            total = e1 / d1 + e2 / d2
            if total == 8.0:
                total = 1.75
            # Higher score wins; tie-break: lower index wins (idx < best_idx)
            if total > best_score or (total == best_score and idx < best_idx):
                best_score = total
                best_idx = idx
        return best_idx

    # Phase 2: pick mon with highest single-move damage
    user_hp = user_pok[_POK_CURRENT_HP]
    best_idx2 = candidates[0]
    best_dmg = -1
    for idx in candidates:
        mon = ai_party[off * idx: off * (idx + 1)]
        moves = mon[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        max_move_dmg = 0
        for mv in moves:
            if mv[_MOVE_ID] == 0:
                break
            # pokeplatinum skips the moves with data power 1 (variable power, fixed damage, OHKO
            # and Hidden Power), MoveDB keeps those at 0 but Hidden Power. Status moves still score
            # their power 0 chip
            if (
                (mv[_MOVE_POWER] == 0 and mv[_MOVE_CATEGORY] != _MOVECATEGORY_STATUS)
                or mv[_MOVE_ID] == _MOVENAME_HIDDEN_POWER
            ):
                continue
            # Weather Ball keeps its data power, the type chart sees the weather type
            # (pokeplatinum BattleAI_PostKOSwitchIn, Move_CalcVariableType)
            dmg_mv = mv
            if mv[_MOVE_ID] == _MOVENAME_WEATHER_BALL:
                dmg_mv = mv.copy()
                dmg_mv[_MOVE_TYPE] = slot_move_type(mon, mv, weather)
            raw_dmg = calculate_damage(
                deadmon, user_pok, dmg_mv, weather, False, 100, user_side, gravity
            )
            #overflow bug:
            dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
            dmg = min(dmg, user_hp)
            if dmg > max_move_dmg:
                max_move_dmg = dmg
        if max_move_dmg > best_dmg or (max_move_dmg == best_dmg and idx < best_idx2):
            best_dmg = max_move_dmg
            best_idx2 = idx
    return best_idx2


@njit
def ai_move_damage(move, effectiveness, ai_pok, user_pok, weather, user_side, gravity=False):
    """Damage the AI sees for a damaging move (pokeplatinum TrainerAI_CalcDamage)"""
    if move[_MOVE_ID] == _MOVENAME_MAGNITUDE:
        return 0
    if not move[_MOVE_DAMAGE]:
        return calculate_ai_logic_damage(
            effectiveness, ai_pok, user_pok, move, weather, user_side, gravity
        )
    if move[_MOVE_DAMAGE] == _DAMAGESOURCES_LEVEL:
        return ai_pok[_POK_LEVEL] if effectiveness != 0 else 0
    if move[_MOVE_DAMAGE] == _DAMAGESOURCES_PSYWAVE:
        damage = ai_pok[_POK_LEVEL] * (random.randint(0, 10) + 5) // 10
        return damage if effectiveness != 0 else 0
    if move[_MOVE_DAMAGE] < 0:
        return 0
    return move[_MOVE_DAMAGE] if effectiveness != 0 else 0


@njit
def copycat_beats(ai_pok, user_pok, weather, user_side, gravity=False, ai_side=0):
    """
    pokeplatinum IfBattlerDealsMoreDamage for Expert_Copycat: the target's last move, used by the
    target on itself, does more than every damaging move of the AI. user_side / ai_side are both
    Field.SIDE_COND
    """
    slot = last_move_slot(user_pok)
    if slot < 0:
        return False
    last = user_pok[_POK_MOVE1_ID + slot * MOVE_STRIDE:_POK_MOVE1_ID + (slot + 1) * MOVE_STRIDE]
    if last[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
        return False
    view = ai_move_view(last, user_pok, user_pok, weather)
    eff, _ = trainer_ai_effectiveness(view, user_pok, user_pok, gravity)
    copied = ai_move_damage(view, eff, user_pok, user_pok, weather, user_side, gravity)
    for i in range(4):
        mv = ai_pok[_POK_MOVE1_ID + i * MOVE_STRIDE:_POK_MOVE1_ID + (i + 1) * MOVE_STRIDE]
        if mv[_MOVE_ID] == 0 or mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
            continue
        view = ai_move_view(mv, ai_pok, user_pok, weather, ai_side, user_side)
        eff, _ = trainer_ai_effectiveness(view, ai_pok, user_pok, gravity)
        if ai_move_damage(view, eff, ai_pok, user_pok, weather, user_side, gravity) >= copied:
            return False
    return True


@njit
def _max_ai_damage(pok, user_pok, weather, ai_side, user_side, gravity):
    """pokeplatinum TrainerAI_CalcAllDamage at the top roll: the best damage of pok's moves, PP or not"""
    best = 0
    for i in range(4):
        mv = pok[_POK_MOVE1_ID + i * MOVE_STRIDE:_POK_MOVE1_ID + (i + 1) * MOVE_STRIDE]
        if mv[_MOVE_ID] in MOVE_EXCEP or mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
            continue
        view = ai_move_view(mv, pok, user_pok, weather, ai_side, user_side)
        eff, _ = trainer_ai_effectiveness(view, pok, user_pok, gravity)
        dmg = ai_move_damage(view, eff, pok, user_pok, weather, user_side, gravity)
        if dmg > best:
            best = dmg
    return best


@njit
def bench_deals_more(battle_array, ai_pok, user_pok, weather, ai_side, user_side, gravity):
    """
    pokeplatinum IfPartyMemberDealsMoreDamage (USE_MAX_DAMAGE) for Expert Healing Wish: a living
    bench Pokemon's best damage beats the active's. Copied quirk: the bench's moves are worked out
    on the active's battler (stats, level, types, stages, status), only the bench Pokemon's item,
    ability and Hidden Power are its own, never under Embargo
    """
    active_dmg = _max_ai_damage(ai_pok, user_pok, weather, ai_side, user_side, gravity)
    opp_active = battle_array[_FIELD_OPP_POK]
    tmp = ai_pok.copy()
    tmp[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_EMBARGO
    for j in range(6):
        base = (6 + j) * POK_LEN
        if j == opp_active or battle_array[base + _POK_CURRENT_HP] <= 0:
            continue
        bench = battle_array[base:base + POK_LEN]
        tmp[_POK_MOVE1_ID:POK_LEN] = bench[_POK_MOVE1_ID:POK_LEN]
        tmp[_POK_AB_ID:_POK_AB_ID + AB_LEN] = bench[_POK_AB_ID:_POK_AB_ID + AB_LEN]
        tmp[_POK_HIDDEN_POWER_TYPE] = bench[_POK_HIDDEN_POWER_TYPE]
        tmp[_POK_HIDDEN_POWER_POWER] = bench[_POK_HIDDEN_POWER_POWER]
        if _max_ai_damage(tmp, user_pok, weather, ai_side, user_side, gravity) > active_dmg:
            return True
    return False


@njit
def ai_has_se_move(ai_pok, user_pok, weather, ai_side, user_side, gravity):
    """pokeplatinum IfHasSuperEffectiveMove: any of the AI's moves, status ones too, is super effective"""
    for i in range(4):
        mv = ai_pok[_POK_MOVE1_ID + i * MOVE_STRIDE:_POK_MOVE1_ID + (i + 1) * MOVE_STRIDE]
        if mv[_MOVE_ID] == 0:
            continue
        view = ai_move_view(mv, ai_pok, user_pok, weather, ai_side, user_side)
        _, s_e = trainer_ai_effectiveness(view, ai_pok, user_pok, gravity)
        if s_e:
            return True
    return False


@njit
def choose_move(battle_array):
    """
    Calculates the score of the moves and sees what has the highest score
    search is used for me to get the raw values of score and rand,
    so i can see what percentage of chance each move has
    """
    """The AI always knows what item you're holding. It cheats to see it.

    The AI always knows your exact current HP and max HP.

    The AI does not know your moves until it sees you use them. Other methods that expose moves,
    such as Sleep Talk or the Forewarn ability, do not count.

    The AI does not know your ability until it sees a text box with the ability name, such as:
    "... makes ground moves miss using LEVITATE", or "... FLASH FIRE made Flamethrower useless".
    If the AI does not know your ability, then most times it tries to check what your ability
    is, it will randomly guess one of the possible abilities your Pokémon's species can
    normally have. Abilities that modify damage but do not generate text, like Heatproof or
    Solid Rock, are not known to the AI even after damage is dealt. However, the AI is aware of
    the reduced damage that will be inflicted (e.g., for a Heatproof Bronzong, it will assume
    Levitate 50% of the time, but also will know that the Bronzong may survive a high-damage
    Fire attack that would KO if it had Levitate).

    Rarely, the AI must specifically see your ability, or your species must not have any other
    possible ability, in order for a check to succeed;
    these cases are worded as "If the target's ability is certainly...".

    There is one exception to this: the AI knows if your ability is Shadow Tag, Magnet Pull,
    or Arena Trap preventing it from switching.

    The AI always knows the attack order of all Pokémon on the field, barring speed ties or
    Quick Claws. It knows if there will be a speed tie, but does not know who will win it.
    If the AI is checking if it will attack before or after another target, and there is a
    speed tie, it will randomly guess the outcome of the tie. For any Pokémon on the field
    with a Quick Claw, it will randomly guess the Quick Claw will activate 20% of the time,
    independent of if the Quick Claw will actually activate.

    If you switch out, the AI will forget its knowledge of your moves and abilities.
    """
    opp_active = battle_array[_FIELD_OPP_POK]
    my_active = battle_array[_FIELD_MY_POK]
    ai_pok = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    user_pok = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    turn = battle_array[_FIELD_TURN]
    # The AI script reads the field's weather, its damage and speed checks the effective one
    weather = battle_array[_FIELD_WEATHER]
    eff_weather = effective_weather(battle_array)
    gravity = battle_array[_FIELD_GRAVITY_TURNS] > 0
    trick_room = battle_array[_FIELD_TRICKROOM] > 0
    ai_know = battle_array[_FIELD_AI_KNOWS]
    my_last_move = battle_array[_FIELD_MY_LAST_MOVE]
    took_dmg = battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN]
    ai_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    ai_items= battle_array[_FIELD_AI_ITEM1:(_FIELD_AI_ITEM4+1)]
    ai_side = battle_array[_FIELD_OPP_SIDE_COND]
    user_side = battle_array[_FIELD_MY_SIDE_COND]
    user_tspikes = battle_array[_FIELD_MY_TOXIC_SPIKES]
    # The target's living party besides the active (pokeplatinum CountAlivePartyBattlers)
    user_bench = count_party(battle_array[0:(6 * POK_LEN)]) - 1
    ai_bench = count_party(battle_array[(6 * POK_LEN):(12 * POK_LEN)]) - 1
    # A living bench Pokemon with a status, for Expert Heal Bell (pokeplatinum IfPartyMemberStatus)
    ai_bench_status = False
    # One below its max HP, fainted included, for Basic Healing Wish (IfAnyPartyMemberIsWounded)
    ai_bench_hurt = False
    for j in range(6):
        base = j * POK_LEN
        if j != opp_active and ai_pty[base + _POK_CURRENT_HP] > 0 and ai_pty[base + _POK_STATUS]:
            ai_bench_status = True
        if j != opp_active and ai_pty[base + _POK_CURRENT_HP] != ai_pty[base + _POK_MAX_HP]:
            ai_bench_hurt = True

    _evaluated_moves = np.full((4,4),10,dtype=np.int16)
    # pokeplatinum TrainerAI_ShouldSwitch skips every withdraw check when Ingrain roots the active
    # or a bind or Mean Look traps it, or my side has Shadow Tag, Arena Trap, or Magnet Pull against
    # a Steel type. Naive on purpose: its own Shadow Tag, Flying type or Shed Shell don't free it
    user_ab = user_pok[_POK_AB_ID]
    can_switch = not (
        ai_pok[_POK_VOL_STATUS] & (_VOLSTATUS_INGRAIN | _VOLSTATUS_PARTIALLY_TRAPPED)
        or ai_pok[_POK_VOL_STATUS2] & _VOLSTATUS2_MEAN_LOOK
        or user_ab == _ABILITYNAMES_SHADOW_TAG
        or user_ab == _ABILITYNAMES_ARENA_TRAP
        or (
            user_ab == _ABILITYNAMES_MAGNET_PULL
            and (ai_pok[_POK_TYPE1] == _TYPES_STEEL or ai_pok[_POK_TYPE2] == _TYPES_STEEL)
        )
    )
    # Withdraw 1 - The active faints to Perish Song at the end of this turn (count 0), it always
    # switches to the post-KO pick (Pokemow; pret says AI_PerishSongKO never fires, the countdown
    # code says it does)
    if (
        can_switch
        and ai_bench > 0
        and ai_pok[_POK_VOL_STATUS] & _VOLSTATUS_PERISH_SONG
        and ai_pok[_POK_PERISH_TURNS] == 0
    ):
        sub = sub_after_death(ai_pty, user_pok, ai_pok, user_side, eff_weather, opp_active, gravity)
        _evaluated_moves[0] = [sub-6,0,0,False]
        return _evaluated_moves
    # Withdraw 5 - The active Pokémon is asleep and has the ability Natural Cure. Like every
    # withdraw it needs a living bench, and the pick skips the active (pokeplatinum)
    if (
        can_switch
        and ai_bench > 0
        and ai_pok[_POK_AB_ID] == _ABILITYNAMES_NATURAL_CURE
        and ai_pok[_POK_STATUS] == _STATUS_SLEEP
        and ai_pok[_POK_CURRENT_HP]/ai_pok[_POK_MAX_HP] >= 0.50
    ):
        if not took_dmg and random.getrandbits(1):
            sub = sub_after_death(ai_pty, user_pok, ai_pok, user_side, eff_weather, opp_active, gravity)
            if sub == opp_active:
                pass
            else:
                _evaluated_moves[0] = [sub-6,0,0,False]
                return _evaluated_moves
        if took_dmg:
            im = check_immunity_pty(ai_pty, user_pok, took_dmg, opp_active, gravity, eff_weather)
            if im.size > 0:
                _evaluated_moves[0] = [im[0]-6,0,0,False]
                return _evaluated_moves
            res = check_resistance_pty(ai_pty, user_pok, took_dmg, opp_active, gravity, eff_weather)
            if res.size > 0:
                _evaluated_moves[0] = [res[0]-6,0,0,False]
                return _evaluated_moves
            if random.getrandbits(1):
                sub = sub_after_death(ai_pty, user_pok, ai_pok, user_side, eff_weather, opp_active, gravity)
                _evaluated_moves[0] = [sub-6,0,0,False]
                return _evaluated_moves


    moves = ai_pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
    # One guess per turn for every move's speed check
    claw_guess = quick_claw_guess(ai_pok, user_pok)

    ab=user_pok[_POK_AB_ID]
    # A battle message named it (Pok.AB_KNOWN) or Worry Seed gave it (Field.AI_KNOWS)
    if (
        not POKEMON_HAS_RELEVANT_ABILITY[user_pok[_POK_ID]]
        or (ai_know & _ENEMY_AI_KNOWS_ABILITY)
        or user_pok[_POK_AB_KNOWN]
    ):
        ability = ab
    else:
        pool_row = POKEMON_ABILITY_POOL[user_pok[_POK_ID]]
        ability = pool_row[random.getrandbits(1)]

    max_damage = 0
    # Expert Healing Wish's and U-turn's two checks, only worked out when the active has one
    has_se = False
    bench_more = False
    for i in range(4):
        if moves[i][_MOVE_ID] == _MOVENAME_HEALING_WISH or moves[i][_MOVE_ID] == _MOVENAME_U_TURN:
            has_se = ai_has_se_move(ai_pok, user_pok, eff_weather, ai_side, user_side, gravity)
            bench_more = bench_deals_more(
                battle_array, ai_pok, user_pok, eff_weather, ai_side, user_side, gravity
            )

    _rand = np.zeros((4, 6, 2), dtype=np.int16)
    _eff4x = np.zeros(4, dtype=np.bool_)
    s_e = False
    can_hit = False
    not_status_counter = 0

    for i, move in enumerate(moves):
        # Cache NumPy scalar extractions locally to prevent repeated C-API calls
        move_id = move[_MOVE_ID]
        if move_id == 0:
            break

        move_category = move[_MOVE_CATEGORY]
        move_is_status = move_category == _MOVECATEGORY_STATUS
        is_damaging = move_id not in MOVE_EXCEP and not move_is_status

        # Disable, Encore, Taunt, Torment and my Imprison make the move invalid, scored like a move
        # without PP. Its damage still counts as the one to beat (pokeplatinum TrainerAI_CalcAllDamage)
        if move[_MOVE_PP] < 1 or move_blocked(ai_pok, i, gravity) or imprisoned(user_pok, move_id):
            if is_damaging:
                view = ai_move_view(move, ai_pok, user_pok, eff_weather, ai_side, user_side)
                eff, _ = trainer_ai_effectiveness(view, ai_pok, user_pok, gravity)
                dmg = ai_move_damage(view, eff, ai_pok, user_pok, eff_weather, user_side, gravity)
                if dmg > max_damage:
                    max_damage = dmg
            continue
        move = ai_move_view(move, ai_pok, user_pok, eff_weather, ai_side, user_side)

        effectiveness, s_e_check = trainer_ai_effectiveness(move, ai_pok, user_pok, gravity)

        if not move_is_status:
            final_damage = ai_move_damage(
                move, effectiveness, ai_pok, user_pok, eff_weather, user_side, gravity
            )
            not_status_counter +=1
            if s_e_check:
                s_e = True
            if effectiveness != 0:
                can_hit = True
        else:
            final_damage = 0

        _eff4x[i] = is_damaging and effectiveness == 4.0
        eval_atk = evaluate_attack_flag(
            final_damage, effectiveness, user_pok, move, i, _rand, is_damaging
        )
        score = eval_atk + basic_flag(
            move, ability, ai_pok, user_pok, effectiveness, weather, ai_side, user_side,
            user_tspikes, user_bench, ai_bench, ai_know, turn, gravity, claw_guess, eff_weather,
            trick_room, battle_array[_FIELD_MY_SPIKES], ai_bench_status, ai_bench_hurt
        )

        expert = expert_flag(
            ai_pok, user_pok, move, turn, i, _rand, weather, my_last_move, effectiveness, took_dmg,
            ai_know, user_side,
            move_id == _MOVENAME_COPYCAT
            and copycat_beats(ai_pok, user_pok, eff_weather, user_side, gravity, ai_side),
            claw_guess, eff_weather, ai_side, ability, ai_bench_status, ai_bench, trick_room,
            has_se, bench_more
        )
        score += expert

        if is_damaging and final_damage > max_damage:
            max_damage = final_damage

        score += batch_independent_score_from_rand(_rand, i)

        # Append only what is necessary for the next step
        _evaluated_moves[i] = [i, score, final_damage, is_damaging]

    # Withdraw 2 - The active Pokémon is facing a foe with Wonder Guard and cannot hit it supereffectively
    if can_switch and ab == _ABILITYNAMES_WONDER_GUARD and not s_e:
        cand = check_super_ef_move_pty(ai_pty, user_pok, opp_active, gravity, False, eff_weather)
        if cand.size > 0:
            for i in cand:
                if random.random() < 0.66666:
                    _evaluated_moves.fill(10)
                    _evaluated_moves[0] = [i-6,0,0,False]
                    return _evaluated_moves

    # Withdraw 3 - More than 2 damaging moves and All of them do not affect the target
    if can_switch and not_status_counter>1 and not can_hit:
        # Only damaging moves count here, unlike the Wonder Guard check (Pokemow)
        cand = check_super_ef_move_pty(ai_pty, user_pok, opp_active, gravity, True, eff_weather)
        if cand.size> 0:
            for i in cand:
                if random.random() < 0.888:
                    _evaluated_moves.fill(10)
                    _evaluated_moves[0] = [i-6,0,0,False]
                    return _evaluated_moves
        cand_normal = check_any_damaging_move_pty(ai_pty, user_pok, opp_active, gravity, eff_weather)
        if cand_normal.size > 0:
            for i in cand_normal:
                if random.random() < 0.75:
                    _evaluated_moves.fill(10)
                    _evaluated_moves[0] = [i-6,0,0,False]
                    return _evaluated_moves

    # Withdraw 4 - The last move the active Pokémon was hit by in the last turn was Fire, Water,
    # or Electric-type, and a party Pokémon has the ability Flash Fire, Water Absorb, or Volt Absorb
    if can_switch and my_last_move in FIRE_WATER_ELECTRIC and ai_pok[_POK_AB_ID] not in ABSORB_ABI:
        if s_e and random.random()<0.6666 and not took_dmg:
            pass
        else:
            cand_abi = check_absorb_abi_pty(ai_pty, my_last_move, opp_active)
            if cand_abi.size > 0:
                for i in cand_abi:
                    if random.random() < 0.50:
                        _evaluated_moves.fill(10)
                        _evaluated_moves[0] = [i-6,0,0,False]
                        return _evaluated_moves


    # Before checking the final two situations to switch, check if:
    # - The current active Pokémon is able to damage at least one foe supereffectively.
    # This is checked by the move selection effectiveness check, with variable-type moves using
    # their correct types. Only damaging moves count.
    # - The total number of positive stat boosts that the active Pokémon has is greater than or equal to 4.
    if s_e or ai_pok[_POK_ATTACK_STAT_STAGE:(_POK_EVASION_STAT_STAGE + 1)].sum()>= 4:
        pass
    else:
        if can_switch and took_dmg:
            # 6. A party member is immune to the previous attack and can hit the foe supereffectively
            if random.getrandbits(1):
                im = check_immunity_pty(ai_pty, user_pok, took_dmg, opp_active, gravity, eff_weather)
                if im.size > 0:
                    _evaluated_moves.fill(10)
                    _evaluated_moves[0] = [im[0]-6,0,0,False]
                    return _evaluated_moves
            # 7. A party member resists the previous attack and can hit the foe supereffectively
            if random.random() < 0.3333:
                res = check_resistance_pty(ai_pty, user_pok, took_dmg, opp_active, gravity, eff_weather)
                if res.size > 0:
                    _evaluated_moves.fill(10)
                    _evaluated_moves[0] = [res[0]-6,0,0,False]
                    return _evaluated_moves

    # --- Item check ---
    # Count non-zero item slots upfront (max 4 iterations, cheap)
    ai_items = battle_array[_FIELD_AI_ITEM1:_FIELD_AI_ITEM1 + 4]
    item_count = 0
    for _ii in range(4):
        if ai_items[_ii] != 0:
            item_count += 1

    # No items on an Embargoed Pokemon (pokeplatinum TrainerAI_ShouldUseItem)
    if item_count > 0 and ai_pok[_POK_CURRENT_HP] > 0 and not embargoed(ai_pok):
        ai_cur_hp  = ai_pok[_POK_CURRENT_HP]
        ai_max_hp  = ai_pok[_POK_MAX_HP]
        hp_quarter = ai_max_hp >> 2          # ai_max_hp // 4
        hp_missing = ai_max_hp - ai_cur_hp
        ai_status  = ai_pok[_POK_STATUS]
        alive_mons = count_party(ai_pty)

        for idx in range(4):
            item = ai_items[idx]
            if item == 0:
                continue

            # "Save items for remaining mons":
            # item slot idx > 0 is skipped when the party still has more alive
            # mons than the remaining item slots from this point onward.
            if idx > 0 and alive_mons > (item_count - idx + 1):
                continue

            use_item = False

            if item == _POTIONS_FULL_RESTORE:
                use_item = ai_cur_hp < hp_quarter

            elif item == _POTIONS_FULL_HEAL:
                use_item = ai_status != 0

            elif item == _POTIONS_POTION:
                use_item = ai_cur_hp < hp_quarter or hp_missing >= 20

            elif item == _POTIONS_SUPER_POTION:
                use_item = ai_cur_hp < hp_quarter or hp_missing >= 50

            elif item == _POTIONS_HYPER_POTION:
                use_item = ai_cur_hp < hp_quarter or hp_missing >= 200

            elif turn > 1:     # stat boosters: X_SPECIAL, X_DEFEND, X_SPEED
                use_item = True

            if use_item:
                _evaluated_moves.fill(10)
                _evaluated_moves[0, 0] = np.int16(-(idx + 1) * 10)
                return _evaluated_moves

    # Apply penalty only to the already-filtered valid moves
    current_hp = user_pok[_POK_CURRENT_HP]
    for k in range(4):
        info = _evaluated_moves[k]
        # info[3] is is_damaging, info[2] is dmg. A kill already ended the check
        if info[0] != 10 and info[3] and info[2] < current_hp:
            if info[2] < max_damage:
                info[1] -= 1 # info[1] is score
            elif _eff4x[k] and random.getrandbits(8) < 176:
                info[1] += 2

    return _evaluated_moves


@njit
def return_idx(battle_array):
    """
    It transform the highest moving score to the index of the move
    """
    idx = battle_array[_FIELD_OPP_POK]
    pok = battle_array[
        ((idx+6) * POK_LEN):((idx+7) * POK_LEN)
    ]
    if pok[_POK_LOCKED_MOVE] != -1:
        return pok[_POK_LOCKED_MOVE]
    move_scores = choose_move(battle_array)

    max_score = -999999
    _best_moves = np.empty(4, dtype=np.int16)
    n_best = 0


    for info in move_scores:
        if info[0] == 10:
            continue
        score = info[1]
        if score > max_score:
            max_score = score
            _best_moves[0] = info[0]
            n_best = 1
        elif score == max_score:
            _best_moves[n_best] = info[0]
            n_best += 1

    if n_best == 0:
        return 10  #Struggle
    if n_best == 1:
        return _best_moves[0]

    return _best_moves[random.randint(0, n_best - 1)]
