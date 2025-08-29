import random
from Engine.Damage_Calc import calculate_damage
from Utils.Helper import get_type_effectiveness  # added

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
            return best_moves[0]

        # Find max damage among best moves
        max_damage = max(move_scores[move]["dmg"] for move in best_moves)
        damage_moves = [move for move in best_moves if move_scores[move]["dmg"] == max_damage]

        # If tie, pick randomly, if it's only one the random is just for show
        return random.choice(damage_moves)
    
    def sub_after_death(self, ai_party, user_pok, deadmon):
        """
        Implements the switch-in logic described in TrainerAI_switchin.txt.

        Phase 1:
          - Consider only non-fainted teammates.
          - Select teammates that have at least one move that is supereffective (>1) vs user_pok.
          - If any such teammates exist, score each teammate by summing the effectiveness
            of each of their TYPE(S) versus user_pok (single-typed counted twice).
            Higher sum wins; ties broken by party order (lower index wins).

        Phase 2:
          - If no Phase 1 candidate, for each non-fainted teammate compute the max damage
            any of its moves would do to user_pok (use calculate_damage). Apply the
            "255 overflow" rule: if damage > 255 -> damage = damage - 255.
          - Choose teammate with highest such max move damage. Ties broken by party order.

        Returns:
          index of chosen teammate in ai_party (int) or None if no valid candidate.
        """
        # filter non-fainted teammates and keep original party indices for tie-breaks
        candidates = [(i, mon) for i, mon in enumerate(ai_party) if not getattr(mon, 'fainted', False)]
        if not candidates:
            return None

        # Helper to read pokemon types robustly
        def pokemon_types(mon):
            # prefer attribute .types, fallback to base_data structure
            t = getattr(mon, 'types', None)
            if t:
                return t
            bd = getattr(mon, 'base_data', None)
            if bd:
                return bd.get('types', []) or bd.get('Type', []) or []
            return []

        # Phase 1: find mons that have at least one move that is SE (>1) vs user_pok
        phase1 = []
        for idx, mon in candidates:
            has_se_move = False
            for mv in getattr(mon, 'moves', []):
                mv_type = mv.get('type') if isinstance(mv, dict) else getattr(mv, 'type', None)
                if mv_type is None:
                    continue
                try:
                    eff = get_type_effectiveness(mv_type, getattr(user_pok, 'types', []))
                except Exception:
                    # if helper fails, skip this move
                    continue
                if eff > 1:
                    has_se_move = True
                    break
            if has_se_move:
                phase1.append((idx, mon))

        if phase1:
            # Score each mon by summing the effectiveness of each of its types vs user_pok
            scored = []
            for idx, mon in phase1:
                types = pokemon_types(mon)
                # single-typed counted twice
                if len(types) == 1:
                    types = [types[0], types[0]]
                # defensively handle missing types
                types = types[:2] + ([] if len(types) >= 2 else [])
                total = 0.0
                for t in types:
                    try:
                        total += get_type_effectiveness(t, getattr(user_pok, 'types', []))
                    except Exception:
                        total += 1.0
                if total == 8:
                    total = 1.75
                scored.append({'index': idx, 'mon': mon, 'score': total})

            # choose highest score, tie-break by party order (lower index wins)
            best = max(scored, key=lambda x: (x['score'], -x['index']))
            return best['index']

        # Phase 2: simulate moves as if used on the (full) user pok and pick mon with max single-move damage
        # Determine "full HP" for user_pok: prefer max_hp, fallback to base stat 'HP', else current_hp
        full_hp = getattr(user_pok, 'max_hp', None)
        if full_hp is None:
            bd = getattr(user_pok, 'base_data', {})
            full_hp = bd.get('base stats', {}).get('HP', None) if isinstance(bd, dict) else None
        if full_hp is None:
            full_hp = getattr(user_pok, 'current_hp', 0)

        scored_phase2 = []
        for idx, mon in candidates:
            max_move_dmg = 0
            for mv in getattr(mon, 'moves', []):
                # build move object shape expected by calculate_damage
                try:
                    raw_dmg, _ = calculate_damage(deadmon, user_pok, mv, roll_multiplier=1)
                except Exception:
                    # if damage calc fails, skip move
                    continue
                # apply overflow bug: if damage > 255, it overflows by subtracting 255
                dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
                if dmg > max_move_dmg:
                    max_move_dmg = dmg
            scored_phase2.append({'index': idx, 'mon': mon, 'max_dmg': max_move_dmg})

        if not scored_phase2:
            return None

        # choose highest max_dmg, tie-break by party order (lower index wins)
        best2 = max(scored_phase2, key=lambda x: (x['max_dmg'], -x['index']))
        return best2['index']

