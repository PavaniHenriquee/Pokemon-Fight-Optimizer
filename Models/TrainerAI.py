import random
from Engine.Damage_Calc import calculate_damage

class TrainerAI:
    def __init__(self, name=None, difficulty=None, gen=4):
        self.gen = gen
        self.name = name
        self.difficulty = difficulty

    def choose_move(self, ai_pok, user_pok):
        move_scores = {}
        for move in ai_pok.moves:
            score = 0
            # Basic check: type effectiveness
            final_damage, effectiveness = calculate_damage(ai_pok, user_pok, move)
            if final_damage >= user_pok.current_hp: 
                score += 4

            # TODO: Add more checks (STAB, status, accuracy, etc.)


            move_scores[move['name']] = {"score":score, "dmg":final_damage}

        # Find max score
        max_score = max(info["score"] for info in move_scores.values())
        best_moves = [move for move, info in move_scores.items() if info["score"] == max_score]

        if len(best_moves) == 1:
            return best_moves

        # Find max damage among best moves
        max_damage = max(move_scores[move]["dmg"] for move in best_moves)
        damage_moves = [move for move in best_moves if move_scores[move]["dmg"] == max_damage]

        # If tie, pick randomly, if it's only one the random is useless
        return random.choice(damage_moves)