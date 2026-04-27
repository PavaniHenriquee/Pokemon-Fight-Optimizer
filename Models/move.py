"""Normalize moves into numpy Arrays"""
import numpy as np
from Models.idx_const import BASE_MOVE_LEN, SEC_LEN, FLAGS_LEN, Move as MoveA, Flags as MoveFlags, Sec as SecondaryArray, OFFSET_SEC
from Models.helper import Types, Target, Stat, SideCondition, Status, VolStatus, MoveCategory
from DataBase.MoveDB import MoveName


class Move():
    """Move class"""
    def __init__(self, move: dict):
        self.move = move

    def base_move(self):
        """Populating the array for the base move"""
        base_move_array = np.zeros(BASE_MOVE_LEN, dtype=np.int16)
        if self.move is None:
            return base_move_array

        dmg_val = self.move.get('damage')
        if isinstance(dmg_val, int):
            dmg_result = dmg_val
        elif dmg_val == 'level':
            dmg_result = -2
        else:
            dmg_result = -1

        base_move_array[MoveA.ID]       = getattr(MoveName, self.move['name'].upper())
        base_move_array[MoveA.CATEGORY] = getattr(MoveCategory, self.move['category'].upper())
        base_move_array[MoveA.TYPE]     = getattr(Types,self.move['type'].upper())
        base_move_array[MoveA.TARGET]   = getattr(Target,self.move['target'].upper())
        base_move_array[MoveA.POWER]    = (
            self.move.get('power', 0) if self.move.get('power', 0) is not None
            else 0
        )
        base_move_array[MoveA.ACCURACY] = (
            -1 if self.move.get('accuracy', True) is True
            else self.move.get('accuracy', 0) if self.move.get('accuracy', 0) is not None
            else 0
        )
        base_move_array[MoveA.CRIT_RATIO]  = self.move.get('crit_ratio', 1)
        base_move_array[MoveA.WILL_CRIT]   = int(self.move.get('will_crit', False))
        base_move_array[MoveA.OH_KO]       = int(self.move.get('oh_ko', False))
        base_move_array[MoveA.SHEER_FORCE] = int(self.move.get('sheer_force', False))
        base_move_array[MoveA.PRIORITY]    = self.move.get('priority', 0)
        base_move_array[MoveA.OVERRIDE_OFF_POK] = (
            1 if self.move.get('override_off_pok', None) == 'target'
            else 0
        )
        base_move_array[MoveA.OVERRIDE_OFF_STAT] = (
            getattr(Stat, self.move.get('override_off_stat', 'Attack').upper())
            if self.move.get('override_off_stat', None)
            else -1
        )
        base_move_array[MoveA.OVERRIDE_DEF_STAT] = (
            getattr(Stat, self.move.get('override_def_stat', 'Defense').upper())
            if self.move.get('override_def_stat', None)
            else -1
        )
        base_move_array[MoveA.IGNORE_DEF]      = int(self.move.get('ignore_def', False))
        base_move_array[MoveA.IGNORE_IMMUNITY] = int(self.move.get('ignore_immunity', False))
        base_move_array[MoveA.PP]              = self.move.get('pp', 5)
        base_move_array[MoveA.PP_UP]           = 0  # Move wont tell pp up, need to manually tell
        base_move_array[MoveA.MULTI_HIT_MIN]   = (
            self.move.get('multi_hit', 1) if isinstance(self.move.get('multi_hit', 1), int)
            else self.move.get('multi_hit', [1, 1])[0]
        )
        base_move_array[MoveA.MULTI_HIT_MAX] = (
            self.move.get('multi_hit', 1) if isinstance(self.move.get('multi_hit', 1), int)
            else self.move.get('multi_hit', [1, 1])[1]
        )
        base_move_array[MoveA.SELF_SWITCH]  = int(self.move.get('self_switch', False))
        base_move_array[MoveA.FORCE_SWITCH] = int(self.move.get('self_switch', False))
        base_move_array[MoveA.NON_GHOST]    = 1 if self.move.get('non_ghost', None) == 'self' else 0
        base_move_array[MoveA.IGNORE_AB]    = int(self.move.get('ignore_ab', False))
        base_move_array[MoveA.DAMAGE]       = dmg_result
        base_move_array[MoveA.SPREAD_HIT]   = int(self.move.get('spread_hit', False))
        base_move_array[MoveA.SPREAD_MOD]   = self.move.get('spread_mod', 100)
        base_move_array[MoveA.FORCE_STAB]   = 1 if self.move.get('force_stab', False) else 0
        base_move_array[MoveA.STATUS]       = (
            getattr(Status, self.move.get('status', 'None').upper()) if self.move.get('status', None)
            else 0
        )
        base_move_array[MoveA.VOL_STATUS] = (
            self.move.get('vol_status', 0) if self.move.get('vol_status', 0) is not None
            else 0
        )
        base_move_array[MoveA.HAS_CRASH_DAMAGE] = int(self.move.get('has_crash_damage', False))
        base_move_array[MoveA.SLEEP_USABLE]     = int(self.move.get('sleep_usable', False))
        base_move_array[MoveA.SMART_TARGET]     = int(self.move.get('smart_target', False))
        base_move_array[MoveA.BOOST_ATK]        = self.move.get('boost_atk', 0)
        base_move_array[MoveA.BOOST_DEF]        = self.move.get('boost_def', 0)
        base_move_array[MoveA.BOOST_SPATK]      = self.move.get('boost_spatk', 0)
        base_move_array[MoveA.BOOST_SPDEF]      = self.move.get('boost_sp def', 0)
        base_move_array[MoveA.BOOST_SPEED]      = self.move.get('boost_speed', 0)
        base_move_array[MoveA.BOOST_ACC]        = self.move.get('boost_acc', 0)
        base_move_array[MoveA.BOOST_EV]         = self.move.get('boost_ev', 0)
        base_move_array[MoveA.SIDE_CONDITION]   = (
            getattr(SideCondition, self.move.get('side_condition', 'None').upper())
            if self.move.get('side_condition', None)
            else -1
        )
        base_move_array[MoveA.RECOIL] = self.move.get('recoil', 0)
        base_move_array[MoveA.DRAIN]  = self.move.get('drain', 0)
        return base_move_array

    def move_flags(self):
        """Array for move flags"""
        move_flags_array = np.zeros(FLAGS_LEN, dtype=np.bool_)
        if self.move is None:
            return move_flags_array
        flags = self.move.get('flags', {})
        off = BASE_MOVE_LEN
        move_flags_array[MoveFlags.BYPASS_SUB - off]       = int(flags.get('bypasssub', False))
        move_flags_array[MoveFlags.BULLET - off]           = int(flags.get('bullet', False))
        move_flags_array[MoveFlags.BITE - off]             = int(flags.get('bite', False))
        move_flags_array[MoveFlags.CANT_USE_TWICE - off]   = int(flags.get('cant_use_twice', False))
        move_flags_array[MoveFlags.CHARGE - off]           = int(flags.get('charge', False))
        move_flags_array[MoveFlags.CONTACT - off]          = int(flags.get('contact', False))
        move_flags_array[MoveFlags.DANCE - off]            = int(flags.get('dance', False))
        move_flags_array[MoveFlags.DEFROST - off]          = int(flags.get('defrost', False))
        move_flags_array[MoveFlags.DISTANCE - off]         = int(flags.get('distance', False))
        move_flags_array[MoveFlags.FAIL_COPYCAT - off]     = int(flags.get('fail_copycat', False))
        move_flags_array[MoveFlags.FAIL_ENCORE - off]      = int(flags.get('fail_encore', False))
        move_flags_array[MoveFlags.FAIL_INSTRUCT - off]    = int(flags.get('fail_instruct', False))
        move_flags_array[MoveFlags.FAIL_ME_FIRST - off]    = int(flags.get('fail_me_first', False))
        move_flags_array[MoveFlags.FAIL_MIMIC - off]       = int(flags.get('fail_mimic', False))
        move_flags_array[MoveFlags.FUTURE_MOVE - off]      = int(flags.get('future_move', False))
        move_flags_array[MoveFlags.GRAVITY - off]          = int(flags.get('gravity', False))
        move_flags_array[MoveFlags.HEAL - off]             = int(flags.get('heal', False))
        move_flags_array[MoveFlags.METRONOME - off]        = int(flags.get('metronome', False))
        move_flags_array[MoveFlags.MIRROR - off]           = int(flags.get('mirror', False))
        move_flags_array[MoveFlags.MUST_PRESSURE - off]    = int(flags.get('must_pressure', False))
        move_flags_array[MoveFlags.NO_ASSIST - off]        = int(flags.get('no_assist', False))
        move_flags_array[MoveFlags.NO_PARENTAL_BOND - off] = int(flags.get('no_parental_bond', False))
        move_flags_array[MoveFlags.NO_SKETCH - off]        = int(flags.get('no_sketch', False))
        move_flags_array[MoveFlags.NO_SLEEP_TALK - off]    = int(flags.get('no_sleep_talk', False))
        move_flags_array[MoveFlags.PLEDGE_COMBO - off]     = int(flags.get('pledge_combo', False))
        move_flags_array[MoveFlags.POWDER - off]           = int(flags.get('powder', False))
        move_flags_array[MoveFlags.PROTECT - off]          = int(flags.get('protect', False))
        move_flags_array[MoveFlags.PULSE - off]            = int(flags.get('pulse', False))
        move_flags_array[MoveFlags.PUNCH - off]            = int(flags.get('punch', False))
        move_flags_array[MoveFlags.RECHARGE - off]         = int(flags.get('recharge', False))
        move_flags_array[MoveFlags.REFLECTABLE - off]      = int(flags.get('reflectable', False))
        move_flags_array[MoveFlags.SLICING - off]          = int(flags.get('slicing', False))
        move_flags_array[MoveFlags.SNATCHING - off]        = int(flags.get('snatching', False))
        move_flags_array[MoveFlags.SOUND - off]            = int(flags.get('sound', False))
        move_flags_array[MoveFlags.WIND - off]             = int(flags.get('wind', False))
        return move_flags_array

    def sec_effect(self):
        """Array for secondary effects"""
        sec_array = np.zeros(SEC_LEN, dtype=np.int16)
        if self.move is None:
            return sec_array
        secondary2 = {}
        if not self.move.get('secondary', None):
            return sec_array
        if isinstance(self.move.get('secondary', None), list):
            secondary = self.move.get('secondary', [])[0]
            secondary2 = (
                self.move.get('secondary', [None, None])[1]
                if len(self.move.get('secondary', [])) > 1
                else {}
            )
        else:
            secondary = self.move.get('secondary', None)

        off = OFFSET_SEC
        boosts = secondary.get('boost', {}) if secondary else {}

        sec_array[SecondaryArray.CHANCE - off] = secondary.get('chance', 0) if secondary else 0
        sec_array[SecondaryArray.TARGET - off] = (
            Target[secondary.get('target', 'any').upper()]
            if secondary and secondary.get('target', None)
            else -1
        )
        sec_array[SecondaryArray.BOOST_ATK - off]   = boosts.get('atk', 0)
        sec_array[SecondaryArray.BOOST_DEF - off]   = boosts.get('def', 0)
        sec_array[SecondaryArray.BOOST_SPATK - off] = boosts.get('spa', 0)
        sec_array[SecondaryArray.BOOST_SPDEF - off] = boosts.get('spd', 0)
        sec_array[SecondaryArray.BOOST_SPEED - off] = boosts.get('spe', 0)
        sec_array[SecondaryArray.BOOST_ACC - off]   = boosts.get('accuracy', 0)
        sec_array[SecondaryArray.BOOST_EV - off]    = boosts.get('evasion', 0)
        sec_array[SecondaryArray.STATUS - off] = (
            getattr(Status,secondary.get('status', 'None').upper())
            if secondary and secondary.get('status', None)
            else 0
        )
        sec_array[SecondaryArray.VOL_STATUS - off] = (
            getattr(VolStatus, secondary.get('vol_status', 'None').upper())
            if secondary and secondary.get('volatileStatus', None)
            else 0
        )

        # Second secondary effect(for the fangs moves)
        sec_array[SecondaryArray.CHANCE2 - off] = (
            secondary2.get('chance', 0)
            if secondary2
            else 0
        )
        sec_array[SecondaryArray.VOL_STATUS2 - off] = (
            getattr(VolStatus, secondary2.get('vol_status', 'None').upper())
            if secondary2 and secondary2.get('volatileStatus', None)
            else 0
        )

        return sec_array

    def to_array(self):
        """Convert move to numpy array"""
        return np.concatenate((self.base_move(), self.move_flags(), self.sec_effect()))
