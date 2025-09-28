"""Normalize moves into numpy Arrays"""
import numpy as np
from Models.idx_nparray import MoveArray, MoveFlags, SecondaryArray
from Models.helper import Types, Target, Stat, SideCondition, Status, VolStatus, MoveCategory
from DataBase.MoveDB import MoveName


class Move():
    """Move class"""
    def __init__(self, move: dict):
        self.move = move

    def base_move(self):
        """Populating the array for the base move"""
        base_move_array = np.zeros(len(MoveArray), dtype=np.int16)
        if self.move is None:
            return base_move_array
        base_move_array[MoveArray.ID] = MoveName[self.move['name'].upper()]
        base_move_array[MoveArray.CATEGORY] = MoveCategory[self.move['category'].upper()]
        base_move_array[MoveArray.TYPE] = Types[self.move['type'].upper()]
        base_move_array[MoveArray.TARGET] = Target[self.move['target'].upper()]
        base_move_array[MoveArray.POWER] = self.move.get('power', 0) if self.move.get('power', 0) is not None else 0
        base_move_array[MoveArray.ACCURACY] = -1 if self.move.get('accuracy', True) is True else self.move.get('accuracy', 0) if self.move.get('accuracy', 0) is not None else 0
        base_move_array[MoveArray.CRIT_RATIO] = self.move.get('crit_ratio', 1)
        base_move_array[MoveArray.WILL_CRIT] = int(self.move.get('will_crit', False))
        base_move_array[MoveArray.OH_KO] = int(self.move.get('oh_ko', False))
        base_move_array[MoveArray.SHEER_FORCE] = int(self.move.get('sheer_force', False))
        base_move_array[MoveArray.PRIORITY] = self.move.get('priority', 0)
        base_move_array[MoveArray.OVERRIDE_OFF_POK] = 1 if self.move.get('override_off_pok', None) == 'target' else 0
        base_move_array[MoveArray.OVERRIDE_OFF_STAT] = Stat[self.move.get('override_off_stat', 'Attack').upper()] if self.move.get('override_off_stat', None) else -1
        base_move_array[MoveArray.OVERRIDE_DEF_STAT] = Stat[self.move.get('override_def_stat', 'Defense').upper()] if self.move.get('override_def_stat', None) else -1
        base_move_array[MoveArray.IGNORE_DEF] = int(self.move.get('ignore_def', False))
        base_move_array[MoveArray.IGNORE_IMMUNITY] = int(self.move.get('ignore_immunity', False))
        base_move_array[MoveArray.PP] = self.move.get('pp', 5)
        base_move_array[MoveArray.PP_UP] = 0  # Move wont tell pp up, need to manually tell
        base_move_array[MoveArray.MULTI_HIT_MIN] = self.move.get('multi_hit', 1) if isinstance(self.move.get('multi_hit', 1), int) else self.move.get('multi_hit', [1, 1])[0]
        base_move_array[MoveArray.MULTI_HIT_MAX] = self.move.get('multi_hit', 1) if isinstance(self.move.get('multi_hit', 1), int) else self.move.get('multi_hit', [1, 1])[1]
        base_move_array[MoveArray.SELF_SWITCH] = int(self.move.get('self_switch', False))
        base_move_array[MoveArray.FORCE_SWITCH] = int(self.move.get('self_switch', False))
        base_move_array[MoveArray.NON_GHOST] = 1 if self.move.get('non_ghost', None) == 'self' else 0
        base_move_array[MoveArray.IGNORE_AB] = int(self.move.get('ignore_ab', False))
        base_move_array[MoveArray.DAMAGE] = -1 if self.move.get('damage', None) is None else self.move.get('damage', -1) if isinstance(self.move.get('damage', -1), int) else -2 if self.move.get('damage', -1) == 'level' else -1
        base_move_array[MoveArray.SPREAD_HIT] = int(self.move.get('spread_hit', False))
        base_move_array[MoveArray.SPREAD_MOD] = self.move.get('spread_mod', 100)
        base_move_array[MoveArray.FORCE_STAB] = 1 if self.move.get('force_stab', False) else 0
        base_move_array[MoveArray.STATUS] = Status[self.move.get('status', 'None').upper()] if self.move.get('status', None) else 0
        base_move_array[MoveArray.VOL_STATUS] = self.move.get('vol_status', 0) if self.move.get('vol_status', 0) is not None else 0
        base_move_array[MoveArray.HAS_CRASH_DAMAGE] = int(self.move.get('has_crash_damage', False))
        base_move_array[MoveArray.SLEEP_USABLE] = int(self.move.get('sleep_usable', False))
        base_move_array[MoveArray.SMART_TARGET] = int(self.move.get('smart_target', False))
        base_move_array[MoveArray.BOOST_ATK] = self.move.get('boost_atk', 0)
        base_move_array[MoveArray.BOOST_DEF] = self.move.get('boost_def', 0)
        base_move_array[MoveArray.BOOST_SPATK] = self.move.get('boost_spatk', 0)
        base_move_array[MoveArray.BOOST_SPDEF] = self.move.get('boost_sp def', 0)
        base_move_array[MoveArray.BOOST_SPEED] = self.move.get('boost_speed', 0)
        base_move_array[MoveArray.BOOST_ACC] = self.move.get('boost_acc', 0)
        base_move_array[MoveArray.BOOST_EV] = self.move.get('boost_ev', 0)
        base_move_array[MoveArray.SIDE_CONDITION] = SideCondition[self.move.get('side_condition', 'None').upper()] if self.move.get('side_condition', None) else -1
        base_move_array[MoveArray.RECOIL] = self.move.get('recoil', 0)
        base_move_array[MoveArray.DRAIN] = self.move.get('drain', 0)
        return base_move_array

    def move_flags(self):
        """Array for move flags"""
        move_flags_array = np.zeros(len(MoveFlags), dtype=np.bool_)
        if self.move is None:
            return move_flags_array
        flags = self.move.get('flags', {})
        move_flags_array[MoveFlags.BYPASS_SUB] = int(flags.get('bypasssub', False))
        move_flags_array[MoveFlags.BULLET] = int(flags.get('bullet', False))
        move_flags_array[MoveFlags.BITE] = int(flags.get('bite', False))
        move_flags_array[MoveFlags.CANT_USE_TWICE] = int(flags.get('cant_use_twice', False))
        move_flags_array[MoveFlags.CHARGE] = int(flags.get('charge', False))
        move_flags_array[MoveFlags.CONTACT] = int(flags.get('contact', False))
        move_flags_array[MoveFlags.DANCE] = int(flags.get('dance', False))
        move_flags_array[MoveFlags.DEFROST] = int(flags.get('defrost', False))
        move_flags_array[MoveFlags.DISTANCE] = int(flags.get('distance', False))
        move_flags_array[MoveFlags.FAIL_COPYCAT] = int(flags.get('fail_copycat', False))
        move_flags_array[MoveFlags.FAIL_ENCORE] = int(flags.get('fail_encore', False))
        move_flags_array[MoveFlags.FAIL_INSTRUCT] = int(flags.get('fail_instruct', False))
        move_flags_array[MoveFlags.FAIL_ME_FIRST] = int(flags.get('fail_me_first', False))
        move_flags_array[MoveFlags.FAIL_MIMIC] = int(flags.get('fail_mimic', False))
        move_flags_array[MoveFlags.FUTURE_MOVE] = int(flags.get('future_move', False))
        move_flags_array[MoveFlags.GRAVITY] = int(flags.get('gravity', False))
        move_flags_array[MoveFlags.HEAL] = int(flags.get('heal', False))
        move_flags_array[MoveFlags.METRONOME] = int(flags.get('metronome', False))
        move_flags_array[MoveFlags.MIRROR] = int(flags.get('mirror', False))
        move_flags_array[MoveFlags.MUST_PRESSURE] = int(flags.get('must_pressure', False))
        move_flags_array[MoveFlags.NO_ASSIST] = int(flags.get('no_assist', False))
        move_flags_array[MoveFlags.NO_PARENTAL_BOND] = int(flags.get('no_parental_bond', False))
        move_flags_array[MoveFlags.NO_SKETCH] = int(flags.get('no_sketch', False))
        move_flags_array[MoveFlags.NO_SLEEP_TALK] = int(flags.get('no_sleep_talk', False))
        move_flags_array[MoveFlags.PLEDGE_COMBO] = int(flags.get('pledge_combo', False))
        move_flags_array[MoveFlags.POWDER] = int(flags.get('powder', False))
        move_flags_array[MoveFlags.PROTECT] = int(flags.get('protect', False))
        move_flags_array[MoveFlags.PULSE] = int(flags.get('pulse', False))
        move_flags_array[MoveFlags.PUNCH] = int(flags.get('punch', False))
        move_flags_array[MoveFlags.RECHARGE] = int(flags.get('recharge', False))
        move_flags_array[MoveFlags.REFLECTABLE] = int(flags.get('reflectable', False))
        move_flags_array[MoveFlags.SLICING] = int(flags.get('slicing', False))
        move_flags_array[MoveFlags.SNATCHING] = int(flags.get('snatching', False))
        move_flags_array[MoveFlags.SOUND] = int(flags.get('sound', False))
        move_flags_array[MoveFlags.WIND] = int(flags.get('wind', False))
        return move_flags_array

    def sec_effect(self):
        """Array for secondary effects"""
        sec_array = np.zeros(len(SecondaryArray), dtype=np.int16)
        if self.move is None:
            return sec_array
        secondary2 = {}
        if not self.move.get('secondary', None):
            return sec_array
        if isinstance(self.move.get('secondary', None), list):
            secondary = self.move.get('secondary', [])[0]
            secondary2 = self.move.get('secondary', [None, None])[1] if len(self.move.get('secondary', [])) > 1 else {}
        else:
            secondary = self.move.get('secondary', None)
        sec_array[SecondaryArray.CHANCE] = secondary.get('chance', 0) if secondary else 0
        sec_array[SecondaryArray.SEC_TARGET] = Target[secondary.get('target', 'any').upper()] if secondary and secondary.get('target', None) else -1
        sec_array[SecondaryArray.SEC_BOOST_ATK] = secondary.get('boost', {}).get('atk', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_DEF] = secondary.get('boost', {}).get('def', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_SPATK] = secondary.get('boost', {}).get('spa', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_SPDEF] = secondary.get('boost', {}).get('spd', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_SPEED] = secondary.get('boost', {}).get('spe', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_ACC] = secondary.get('boost', {}).get('accuracy', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.SEC_BOOST_EV] = secondary.get('boost', {}).get('evasion', 0) if secondary and secondary.get('boost', None) else 0
        sec_array[SecondaryArray.STATUS] = Status[secondary.get('status', 'None').upper()] if secondary and secondary.get('status', None) else 0
        sec_array[SecondaryArray.VOL_STATUS] = VolStatus[secondary.get('vol_status', 'None').upper()] if secondary and secondary.get('volatileStatus', None) else 0
        # Second secondary effect(for the fangs moves)
        sec_array[SecondaryArray.CHANCE2] = secondary2.get('chance', 0) if secondary2 else 0
        sec_array[SecondaryArray.VOL_STATUS2] = VolStatus[secondary2.get('vol_status', 'None').upper()] if secondary2 and secondary2.get('volatileStatus', None) else 0
        return sec_array

    def to_array(self):
        """Convert move to numpy array"""
        return np.concatenate((self.base_move(), self.move_flags(), self.sec_effect()))
