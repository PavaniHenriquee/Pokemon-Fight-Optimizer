"""Actual run-through"""
from Models.trainer_ai import TrainerAI


def search_best_move(my_pty, ai_pty, cur_pok, cur_opp_pok, turn):
    """Search of the best move"""
    opp_ai = TrainerAI()
    ai_m_scores, ai_rand_scores = opp_ai.choose_move(cur_opp_pok, cur_pok, my_pty, ai_pty, turn, search=True)
    max_rand_score = 0
    min_rand_score = 0
    poss_scores = {}
    for i in ai_rand_scores:
        poss_scores[i] = ()
        score_pos = ai_rand_scores[i]['score']
        score_neg = 0
        score_pos = 0
        for j in dict(score_pos):
            if j >= 0:
                score_pos += j
            else:
                score_neg += j
        max_rand_score += score_pos
        min_rand_score += score_neg
        poss_scores[i] = (min_rand_score, max_rand_score)
    max_nrand_score = max(info["score"] for info in ai_m_scores.values())
