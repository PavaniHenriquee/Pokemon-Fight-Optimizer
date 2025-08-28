from Engine.Damage_Calc import calculate_damage
from Engine.Status_Calc import calculate_status
from Utils.Helper import has_availible_pokemon

def battle_start(party, opp_party):
    global turn
    turn = 1
    current_pokemon = party[0]
    current_opp = opp_party[0]
    print(f"You sent out {current_pokemon.name}!")
    print(f"The opponent sent out {current_opp.name}!")
    return current_pokemon, current_opp

def battle_turn(p1, move1, p2, move2):
    if p1.base_data['base stats']['Speed'] > p2.base_data['base stats']['Speed']:
        order = [(p1, move1,p2), (p2, move2,p1)]
    else:
        order = [(p2, move2,p1), (p1, move1,p2)]
    for attacker, move, defender in order:
        if attacker.current_hp <= 0 or defender.current_hp <= 0:
            continue # Skip if either Pokémon is fainted
        if move['category'] == "Physical" or move['category'] == "Special":
            damage, effectiveness = calculate_damage(attacker, defender, move)
            defender.current_hp -= damage
            print(f"{attacker.name} used {move['name']} on {defender.name}!")
            print(f"It dealt {damage} damage.")
            print(f"Effectiveness: {effectiveness}x") if effectiveness != 1 else None
            if defender.current_hp <= 0:
                print(f"{defender.name} has fainted!")
                defender.fainted = True
            else:
                print(f"{defender.name} has {defender.current_hp} HP left.")
        else:
            print(f"{attacker.name} used {move['name']}!")
            calculate_status(attacker, defender, move)
    global turn
    turn += 1

def battle(myP, oppP):
    current_pokemon, current_opp = battle_start(myP, oppP)
    while has_availible_pokemon(myP) and has_availible_pokemon(oppP):
        current_move = int(input(f'Choose a move for {current_pokemon.name}: ')) - 1 #Because of 0 index
        opp_move = int(input(f'Choose a move for {current_opp.name} which is the opponent: ')) - 1 #Because of 0 index
        battle_turn(current_pokemon, current_pokemon.moves[current_move], current_opp, current_opp.moves[opp_move])