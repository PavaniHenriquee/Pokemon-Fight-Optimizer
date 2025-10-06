"""Battlefield class, so to check weather, Trick Room, hazards, etc."""
import numpy as np


class Battlefield:
    """ Battlefield conditions"""
    def __init__(self, my_pok=0, opp_pok=0, turn=1):
        self.my_pok = my_pok
        self.opp_pok = opp_pok
        self.turn = turn
        self.weather = None
        self.weather_duration = None
        self.trickroom = None
        self.trickroom_duration = None
        self.my_screen = None
        self.my_screen_duration = None
        self.opp_screen = None
        self.opp_screen_duration = None
        self.phase = None

    def to_array(self):
        """Transform in np array to add oin battle_array"""
        bat_array = np.zeros(12)
        bat_array[0] = self.my_pok
        bat_array[1] = self.opp_pok
        bat_array[2] = self.turn
        bat_array[3] = 0 if self.weather is None else self.weather.value
        bat_array[4] = 0 if self.weather_duration is None else self.weather_duration
        bat_array[5] = 0 if self.trickroom is None else int(self.trickroom)
        bat_array[6] = 0 if self.trickroom_duration is None else self.trickroom_duration
        bat_array[7] = 0 if self.my_screen is None else self.my_screen.value
        bat_array[8] = 0 if self.my_screen_duration is None else self.my_screen_duration
        bat_array[9] = 0 if self.opp_screen is None else self.opp_screen.value
        bat_array[10] = 0 if self.opp_screen_duration is None else self.opp_screen_duration
        bat_array[11] = 0 if self.phase is None else self.phase
        return bat_array
