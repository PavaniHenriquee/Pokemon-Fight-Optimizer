from Engine.Damage_Calc import calculate_damage
from Engine.Status_Calc import calculate_status
from Utils.Helper import calculate_hit_miss, calculate_crit, get_non_fainted_pokemon, switch_menu, speed_tie
from Models.TrainerAI import TrainerAI

def battle_start(party, opp_party):
    global turn
    turn = 1
    current_pokemon = party[0]
    current_opp = opp_party[0]
    print(f"You sent out {current_pokemon.name}!")
    print(f"The opponent sent out {current_opp.name}!")
    return current_pokemon, current_opp

def battle_menu(myP_alive, current_pokemon):
    current_move = -1
    switch_pok = -1
    print(f"Your current Pokemon is {current_pokemon.name}")
    while current_move < 0 or current_move >= len(current_pokemon.moves):
        print("Choose one of the moves or if you want to switch:")  if len(myP_alive) > 1 else print("Choose one of the moves:")
        for i, move in enumerate(current_pokemon.moves):
            print(f"{i+1}. {move['name']}")
        print('s. Switch') if len(myP_alive) > 1 else None
        choice = input("Choose: ")
        if choice.isdigit():
            current_move = int(choice) - 1  # Because of index 0
            if current_move < 0 or current_move >= len(current_pokemon.moves):
                print("Please select a valid move.")
                current_move = -1
            continue
        elif choice == 's' and len(myP_alive) > 0:
            alive_pokemon = myP_alive.copy()
            del alive_pokemon[alive_pokemon.index(current_pokemon)] #remove current pokemon from the list
            while switch_pok < 0 or switch_pok >= len(alive_pokemon):
                switch_pok, ret_menu, current_pokemon = switch_menu(alive_pokemon, current_pokemon)
                if ret_menu:
                    break
            if switch_pok >= 0:
                break
            else: continue
        else:
            print("Please select a valid answer.")
            current_move = -1
    return current_move, switch_pok, current_pokemon

def battle_turn(p1, move1, p2, move2, p1_switch = False):
    
    #Check for move order, by priority and speed
    if p1_switch:
        order = [(p2, move2, p1)]
    elif (move1['priority'] != 0 or move2['priority'] !=0) and move1['priority'] != move2['priority']:
        if move1['priority'] > move2['priority']:
            order = [(p1, move1, p2), (p2, move2, p1)]
        else:
            order = [(p2, move2, p1), (p1, move1, p2)]
    else:
        if p1.speed > p2.speed:
            order = [(p1, move1, p2), (p2, move2, p1)]
        elif p2.speed > p1.speed:
            order = [(p2, move2, p1), (p1, move1, p2)]
        else:
            order = speed_tie(p1,move1,p2,move2)
    
    for attacker, move, defender in order:
        if defender.current_hp <= 0:
            print(f"{attacker.name} used {move['name']} on {defender.name}!")
            print(f"But it failed.")
            continue # In cases like self-destruct
        elif attacker.current_hp <=0:
            continue #Failsafe
        
        #Check Move accuracy
        move_hit = calculate_hit_miss(move, attacker, defender)

        #Calculate the move damage or effects
        if move_hit == True:
            if move['category'] == "Physical" or move['category'] == "Special":
                #Calculate if it's a critical hit(Only gen 3 to 5)
                crit = calculate_crit()
                damage, effectiveness = calculate_damage(attacker, defender, move, crit)   
                defender.current_hp -= damage
                print(f"{attacker.name} used {move['name']} on {defender.name}!") if attacker == p1 else print(f"Opponent {attacker.name} used {move['name']} on {defender.name}!")
                print("\033[91mIt's a critical hit! \033[0m") if crit == True else None
                print(f"It dealt {damage} damage.")
                print(f"Effectiveness: {effectiveness}x") if effectiveness != 1 else None
                if defender.current_hp <= 0:
                    print(f"\033[91m{defender.name} has fainted! \033[0m")
                    defender.fainted = True
                else:
                    print(f"{defender.name} has {defender.current_hp} HP left.")
            else:
                print(f"{attacker.name} used {move['name']}!")
                calculate_status(attacker, defender, move)
        else:
            print(f"{attacker.name} used {move['name']} on {defender.name}!")
            print('But it missed!')
            
    global turn
    turn += 1


def battle(myP, oppP):
    oppAi = TrainerAI()
    myP_alive = myP
    oppP_alive = oppP
    current_pokemon, current_opp = battle_start(myP_alive, oppP_alive)
    global turn
    while len(myP_alive) > 0 and len(oppP_alive) > 0:
        opp_move_idx = oppAi.return_idx(current_opp,current_pokemon, myP_alive, oppP_alive, turn)
        opp_move = current_opp.moves[opp_move_idx]
        current_move, switch_pok, current_pokemon = battle_menu(myP_alive, current_pokemon)
        if current_move >= 0: #if switched current_move is -1
            battle_turn(current_pokemon, current_pokemon.moves[current_move], current_opp, opp_move)
        elif switch_pok >= 0:
            battle_turn(current_pokemon, 0, current_opp, opp_move, p1_switch = True)
        myP_alive = get_non_fainted_pokemon(myP_alive)
        oppP_alive = get_non_fainted_pokemon(oppP_alive)
        
        if len(myP_alive) == 0:
            print("You Lost!")
            break
        elif len(oppP_alive) == 0:
            print("You Won!")
            break
        
        if current_opp.fainted:
            current_opp = oppP_alive[oppAi.sub_after_death(oppP_alive, current_pokemon, current_opp)]
            print(f'the opponent has sent {current_opp.name} out')
        if current_pokemon.fainted:
            switch_pok = -1
            while switch_pok < 0 or switch_pok >= len(myP_alive):
                switch_pok, ret_menu, current_pokemon = switch_menu(myP_alive, current_pokemon)
