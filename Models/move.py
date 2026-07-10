"""Normalize moves into numpy Arrays"""
from dataclasses import dataclass
import numpy as np
from Models.idx_const import (
    BASE_MOVE_LEN, SEC_LEN, FLAGS_LEN, OFFSET_SEC,
    Move,
    Flags as MoveFlags,
    Sec as SecondaryArray
)
from Models.helper import (
    Types, Target,SideCondition, Status, VolStatus, MoveCategory, DamageSources
)
from DataBase.MoveDB import MoveName
from DataBase.loader import moveDB



@dataclass(slots=True)
class Stat:
    """
    For override stat, so foul play, psyshock and similars
    """
    ATTACK = 1
    DEFENSE = 2
    SPECIAL_ATTACK = 3
    SPECIAL_DEFENSE = 4
    SPEED = 5



class Moves():
    """Move class"""
    def __init__(self, move: dict):
        self.move = move

    def base_move(self):
        """Populating the array for the base move"""
        base_move_array = np.zeros(BASE_MOVE_LEN, dtype=np.int32)
        if self.move is None:
            return base_move_array

        dmg_val = self.move.get('damage')
        if isinstance(dmg_val, int):
            dmg_result = dmg_val
        elif dmg_val == 'level':
            dmg_result = DamageSources.LEVEL
        elif dmg_val == 'bide':
            dmg_result = DamageSources.BIDE
        elif dmg_val == 'counter':
            dmg_result = DamageSources.COUNTER
        elif dmg_val == 'magic_coat':
            dmg_result = DamageSources.MAGIC_COAT
        else:
            dmg_result = 0

        base_move_array[Move.ID]       = getattr(MoveName, self.move['name'].upper())
        base_move_array[Move.CATEGORY] = getattr(MoveCategory, self.move['category'].upper())
        base_move_array[Move.TYPE]     = getattr(Types,self.move['type'].upper())
        base_move_array[Move.TARGET]   = getattr(Target,self.move['target'].upper())
        base_move_array[Move.POWER]    = self.move.get('power', 0)
        base_move_array[Move.ACCURACY] = (
            -1 if self.move.get('accuracy', 0) is True
            else self.move.get('accuracy', 0)
        )
        base_move_array[Move.CRIT_RATIO]  = self.move.get('crit_ratio', 1)
        base_move_array[Move.WILL_CRIT]   = int(self.move.get('will_crit', False))
        base_move_array[Move.OH_KO]       = int(self.move.get('oh_ko', False))
        base_move_array[Move.PRIORITY]    = self.move.get('priority', 0)
        base_move_array[Move.OVERRIDE_OFF_STAT] = (
            getattr(Stat, self.move.get('override_off_stat', 0).upper())
            if self.move.get('override_off_stat', 0)
            else 0
        )
        base_move_array[Move.OVERRIDE_DEF_STAT] = (
            getattr(Stat, self.move.get('override_def_stat', 0).upper())
            if self.move.get('override_def_stat', 0)
            else 0
        )
        base_move_array[Move.IGNORE_DEF]      = int(self.move.get('ignore_def', False))
        base_move_array[Move.IGNORE_IMMUNITY] = int(self.move.get('ignore_immunity', False))
        base_move_array[Move.PP]              = self.move.get('pp',0)
        base_move_array[Move.PP_UP]           = 0  # Move wont tell pp up, need to manually tell
        mult_hit = self.move.get('multi_hit',[0,0])
        base_move_array[Move.MULTI_HIT_MIN]   = mult_hit[0]
        base_move_array[Move.MULTI_HIT_MAX] = mult_hit[1]
        base_move_array[Move.SELF_SWITCH]  = int(self.move.get('self_switch', False))
        base_move_array[Move.FORCE_SWITCH] = int(self.move.get('force_switch', False))
        base_move_array[Move.DAMAGE]       = dmg_result
        status = self.move.get('status')
        base_move_array[Move.STATUS] = getattr(Status, status.upper()) if status else 0
        vol_status = self.move.get('vol_status')
        base_move_array[Move.VOL_STATUS] = getattr(VolStatus, vol_status.upper()) if vol_status else 0
        base_move_array[Move.HAS_CRASH_DAMAGE] = int(self.move.get('has_crash_damage', False))
        base_move_array[Move.SLEEP_USABLE]     = int(self.move.get('sleep_usable', False))
        base_move_array[Move.SMART_TARGET]     = int(self.move.get('smart_target', False))
        base_move_array[Move.BOOST_ATK]        = self.move.get('boost_atk', 0)
        base_move_array[Move.BOOST_DEF]        = self.move.get('boost_def', 0)
        base_move_array[Move.BOOST_SPATK]      = self.move.get('boost_spatk', 0)
        base_move_array[Move.BOOST_SPDEF]      = self.move.get('boost_spdef', 0)
        base_move_array[Move.BOOST_SPEED]      = self.move.get('boost_speed', 0)
        base_move_array[Move.BOOST_ACC]        = self.move.get('boost_acc', 0)
        base_move_array[Move.BOOST_EV]         = self.move.get('boost_ev', 0)
        side_condition = self.move.get('side_condition')
        base_move_array[Move.SIDE_CONDITION]   = (
            getattr(SideCondition, side_condition.upper())
            if side_condition
            else 0
        )
        base_move_array[Move.RECOIL] = self.move.get('recoil', 0)  #Considering division by 100 later
        base_move_array[Move.CHARGE_RECHARGE] = self.move.get('charge', 0) - self.move.get('recharge', 0)
        drain = self.move.get('drain', 0)
        if not isinstance(drain, int):
            # its 50% or 75%
            if drain[1]==2:
                base_move_array[Move.DRAIN]  = 2
            else:
                base_move_array[Move.DRAIN]  = 3
        else:
            base_move_array[Move.DRAIN]  = self.move.get('drain', 0)
        return base_move_array

    def move_flags(self):
        """Array for move flags"""
        move_flags_array = np.zeros(FLAGS_LEN, dtype=np.int32)
        if self.move is None:
            return move_flags_array
        flags = self.move.get('flags', {})
        off = BASE_MOVE_LEN
        move_flags_array[MoveFlags.BYPASS_SUB - off]       = int(flags.get('bypasssub', False))
        move_flags_array[MoveFlags.BULLET - off]           = int(flags.get('bullet', False))
        move_flags_array[MoveFlags.BITE - off]             = int(flags.get('bite', False))
        move_flags_array[MoveFlags.CHARGE - off]           = int(flags.get('charge', False))
        move_flags_array[MoveFlags.CONTACT - off]          = int(flags.get('contact', False))
        move_flags_array[MoveFlags.DANCE - off]            = int(flags.get('dance', False))
        move_flags_array[MoveFlags.DEFROST - off]          = int(flags.get('defrost', False))
        move_flags_array[MoveFlags.FAIL_ENCORE - off]      = int(flags.get('fail_encore', False))
        move_flags_array[MoveFlags.FUTURE_MOVE - off]      = int(flags.get('future_move', False))
        move_flags_array[MoveFlags.GRAVITY - off]          = int(flags.get('gravity', False))
        move_flags_array[MoveFlags.HEAL - off]             = int(flags.get('heal', False))
        move_flags_array[MoveFlags.MIRROR - off]           = int(flags.get('mirror', False))
        move_flags_array[MoveFlags.NO_SLEEP_TALK - off]    = int(flags.get('no_sleep_talk', False))
        move_flags_array[MoveFlags.POWDER - off]           = int(flags.get('powder', False))
        move_flags_array[MoveFlags.PROTECT - off]          = int(flags.get('protect', False))
        move_flags_array[MoveFlags.PULSE - off]            = int(flags.get('pulse', False))
        move_flags_array[MoveFlags.PUNCH - off]            = int(flags.get('punch', False))
        move_flags_array[MoveFlags.RECHARGE - off]         = int(flags.get('recharge', False))
        move_flags_array[MoveFlags.REFLECTABLE - off]      = int(flags.get('reflectable', False))
        move_flags_array[MoveFlags.SLICING - off]          = int(flags.get('slicing', False))
        move_flags_array[MoveFlags.SOUND - off]            = int(flags.get('sound', False))
        """move_flags_array[MoveFlags.CANT_USE_TWICE - off]   = int(flags.get('cant_use_twice', False))
        move_flags_array[MoveFlags.DISTANCE - off]         = int(flags.get('distance', False))
        move_flags_array[MoveFlags.FAIL_COPYCAT - off]     = int(flags.get('fail_copycat', False))
        move_flags_array[MoveFlags.FAIL_INSTRUCT - off]    = int(flags.get('fail_instruct', False))
        move_flags_array[MoveFlags.FAIL_ME_FIRST - off]    = int(flags.get('fail_me_first', False))
        move_flags_array[MoveFlags.FAIL_MIMIC - off]       = int(flags.get('fail_mimic', False))
        move_flags_array[MoveFlags.METRONOME - off]        = int(flags.get('metronome', False))
        move_flags_array[MoveFlags.MUST_PRESSURE - off]    = int(flags.get('must_pressure', False))
        move_flags_array[MoveFlags.NO_ASSIST - off]        = int(flags.get('no_assist', False))
        move_flags_array[MoveFlags.NO_PARENTAL_BOND - off] = int(flags.get('no_parental_bond', False))
        move_flags_array[MoveFlags.NO_SKETCH - off]        = int(flags.get('no_sketch', False))
        move_flags_array[MoveFlags.PLEDGE_COMBO - off]     = int(flags.get('pledge_combo', False))
        move_flags_array[MoveFlags.SNATCHING - off]        = int(flags.get('snatching', False))
        move_flags_array[MoveFlags.WIND - off]             = int(flags.get('wind', False))"""
        return move_flags_array

    def sec_effect(self):
        """Array for secondary effects"""
        sec_array = np.zeros(SEC_LEN, dtype=np.int32)
        if self.move is None:
            return sec_array
        secondary = self.move.get('secondary', {})
        off = OFFSET_SEC
        sec_array[SecondaryArray.CHANCE - off] = secondary.get('chance', 0) if secondary else 0
        sec_array[SecondaryArray.TARGET - off] = (
            getattr(Target,secondary.get('target', 'normal').upper())
            if secondary
            else -1
        )
        sec_array[SecondaryArray.BOOST_ATK - off]   = secondary.get('atk', 0)
        sec_array[SecondaryArray.BOOST_DEF - off]   = secondary.get('def', 0)
        sec_array[SecondaryArray.BOOST_SPATK - off] = secondary.get('spa', 0)
        sec_array[SecondaryArray.BOOST_SPDEF - off] = secondary.get('spd', 0)
        sec_array[SecondaryArray.BOOST_SPEED - off] = secondary.get('speed', 0)
        sec_array[SecondaryArray.BOOST_ACC - off]   = secondary.get('accuracy', 0)
        sec_array[SecondaryArray.BOOST_EV - off]    = secondary.get('evasion', 0)
        status = secondary.get('status')
        sec_array[SecondaryArray.STATUS - off] = (
            getattr(Status, status.upper())
            if status
            else 0
        )
        vol_status = secondary.get('vol_status')
        sec_array[SecondaryArray.VOL_STATUS - off] = (
            getattr(VolStatus, vol_status.upper())
            if vol_status
            else 0
        )

        # Second secondary effect(only for the fangs moves)
        sec_array[SecondaryArray.CHANCE2 - off] = secondary.get('chance2', 0)
        vol_status2 = secondary.get('vol_status2')
        sec_array[SecondaryArray.VOL_STATUS2 - off] = (
            getattr(VolStatus, vol_status2.upper())
            if vol_status2
            else 0
        )

        return sec_array

    def to_array(self):
        """Convert move to numpy array"""
        return np.concatenate((self.base_move(), self.move_flags(), self.sec_effect()))


STRUGGLE = Moves(moveDB['Struggle']).to_array()
# -------Curse array when not being used by a ghost type
CURSE_BOOST = Moves(moveDB['Curse']).to_array()
CURSE_BOOST[Move.VOL_STATUS]=0
CURSE_BOOST[Move.BOOST_SPEED]=-1
CURSE_BOOST[Move.BOOST_ATK]=1
CURSE_BOOST[Move.BOOST_DEF]=1
CURSE_BOOST[Move.TARGET]=Target.SELF
