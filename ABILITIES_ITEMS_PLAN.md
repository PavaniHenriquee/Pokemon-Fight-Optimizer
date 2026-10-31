# Abilities & Held Items: Implementation Plan

## How to use this file across sessions

- Start a session with: "Read `ABILITIES_ITEMS_PLAN.md` and `CLAUDE.md`, then do Batch N."
- Each batch follows the CLAUDE.md per-batch flow: mechanics note with sources → your OK → engine → AI →
  tests → `pytest` / `-m jit` / `-m slow` → list the TODO boxes that can be ticked.
- Batch 0 comes first. After that, batches are independent except where a batch says "Depends on".
- The tracker and decision log are updated only when you ask, like TODO.txt.
- Anything noticed but not fixed during a batch goes in **Discoveries** below, unless you say to fix it now.

| Batch | Topic                                                               | Status |
| ----- | ------------------------------------------------------------------- | ------ |
| 0     | Foundations: item slots, Mold Breaker helper, search key            | [x]    |
| 1     | Damage items (Roark: Muscle Band, Expert Belt)                      | [x]    |
| 2     | Consumables and timers (Roark: Rindo Berry, Smooth Rock, Flame Orb) | [x]    |
| 3     | Trainer abilities: Rock Head, Sturdy                                | [x]    |
| 4     | Damage abilities                                                    | [x]    |
| 5     | Accuracy, crit, secondary effects                                   | [ ]    |
| 6     | Contact abilities                                                   | [ ]    |
| 7     | Status immunity, cures, status berries                              | [ ]    |
| 8     | Type immunity and absorb abilities                                  | [ ]    |
| 9     | Switch-in abilities and stat-drop guards                            | [ ]    |
| 10    | Speed and turn order                                                | [ ]    |
| 11    | Weather and end of turn                                             | [ ]    |
| 12    | Trapping                                                            | [ ]    |
| 13    | Survival, charge, consecutive use, drain                            | [ ]    |
| 14    | No-op confirmations and out of scope                                | [ ]    |

**Decisions**

- 2026-10-29: item effects are data. New Item slots `HOLD_EFFECT`, `EFFECT_PARAM`, `EFFECT_TYPE`, filled from
  ItemDB.json with pokeplatinum's holdEffect / effectParam.
- 2026-10-29 (Batch 0): per-type pp effects (`STRENGTHEN_<TYPE>`, `WEAKEN_SE_<TYPE>`) merged into `TYPE_BOOST` /
  `WEAKEN_SE` + `EFFECT_TYPE`; Chilan (`WEAKEN_NORMAL`) also gets `EFFECT_TYPE` Normal. Light Ball keeps the pp
  name `PIKA_SPATK_UP` (effect is still base power x2, pp battle_lib.c CalcMoveDamage).
- 2026-10-29 (Batch 0): F1 dispatch done. `item_on_rdmg` has no berry gate any more, so Berry Juice works;
  `ITEM_50HP` removed (now `HP_RESTORE_EFFECTS`). Sitrus heals at least 1 (pp `BattleSystem_Divide`).
- 2026-10-29 (Batch 0): F2 keeps the `AB_BREAKABLE` flag: `ignorable_ability(defender, attacker)`, not pp's
  per-ability signature.
- 2026-10-29 (Batch 0): F3 dropped. pp has no item-loss tracking: `canUnburden` is set on switch-in when holding
  an item (FALSE if knocked off, `BattleSystem_InitBattleMon`), and when Unburden is gained while holding one
  (battle_lib.c ABILITY_UNBURDEN case); speed x2 needs Unburden + `canUnburden` + no item
  (`BattleSystem_CompareBattlerSpeed`). Batch 10 adds VOL2 `CAN_UNBURDEN`, set only for Unburden holders.
- 2026-10-29 (Batch 0): Issue 6 (held item needs HP > 0, pp `BattleSystem_TriggerHeldItem`) stays in Batch 2.
- 2026-10-29: ItemDB `fling_power` filled for the 22 berries (pp says 10); everything else already matched pp.
- 2026-10-29 (Batch 1): Issues 2, 8, 9 fixed. Item boosts use pp's integer `x(100+effect_param)/100`, not
  Showdown's 4096 chain. Struggle stays typeless ([SD gen4] `'???'`; [pp] data says Normal), so no type item.
- 2026-10-29 (Batch 1): the confusion self-hit follows Bulbapedia's Gen IV damage-factor table: random roll,
  burn, attack abilities, Silk Scarf, Thick Club, Light Ball. Not Muscle Band (not in the table, though [pp]
  CALC_SELF_HIT runs it through CalcMoveDamage as a physical Struggle). Helping Hand, Choice Band, Power
  Trick/Split, Rivalry, Pure Power stay TODOs in `calculate_damage_confusion`.
- 2026-10-29 (Batch 2): Safeguard blocks Flame Orb ([pp] subscript_burn held-item branch; [SD] lets it through
  because the source is the holder). Resist berries and Chilan follow [SD] `onSourceModifyDamage`
  (`max(1, dmg // 2)`, SE only, eaten and recyclable): pokeplatinum's battle code has no WEAKEN_SE reference
  at all. Issues 6 and 12 fixed.
- 2026-10-29 (after Batch 3, Explosion / Selfdestruct): the user faints before the hit check when there's a
  target, so a miss, Protect or a Ghost still costs it; Damp on either side stops the whole move and Mold
  Breaker ignores the target's Damp (fixed in `ab_on_try_move` through `damp_blocks`). Gen IV Defense halving
  follows [SD] (after the stages, at least 1), not [pp] (raw stat first). The rollout keeps both moves out of
  its damage calc (weight 1), like the trainer AI's `MOVE_EXCEP`. A double KO counts as a loss: [pp] gives a
  draw and handles it like a loss, matching `evaluate_terminal`.
- 2026-10-29 (OHKO moves): Fissure, Guillotine, Sheer Cold added; Horn Drill left out (RP replaces it with Drill
  Run). Hit check and damage follow [pp BtlCmd_TryOHKOMove]: accuracy + level difference out of 100, always fails
  from a lower level, ignores stages / Gravity / Hustle / Sand Veil, damage = the target's current HP. They can't
  hit Bounce or Dig ([SD gen4]); the known gap is closed. AI: [pp] Basic_CheckOHKOWouldFail and Expert_OHKOMove,
  the three moves in `MOVE_EXCEP`. Rollout: weight 1, or 0 when `ohko_fails`. Sturdy's status audit said
  "AI only"; that was wrong, nothing scored OHKO moves into Sturdy before this.
- 2026-10-30 (Batch 4): Issues 1 and 15 fixed. Base power runs in [pp CalcMoveDamage] order: variable → Charge →
  Technician → items → `base_power_ability(attacker, defender, move, power)` (Thick Fat → Sport → pinch → Heatproof
  → Dry Skin → Rivalry → Iron Fist; Reckless stays last). It returns the power now, no 4096 multipliers.
  Heatproof halves base power per [pp]; [SD] gen4 inherits the gen5+ Atk/SpA halving. Filter / Solid Rock follow
  [pp ApplyTypeChart] (after the types, before Expert Belt, at least 1), not [SD]'s final modifier.
  `ignorable_ability` moved to the new `Engine/ability_helper.py` (damage_calc needs it, engine_helper imports
  damage_calc). Flower Gift's AbilitiesDB `when` gained `on_modify_stat` so the stat gate sees it. The confusion
  self-hit gets Pure Power and Rivalry (always same gender on itself); Unaware stays out of it.
- 2026-10-30 (Batch 4): Normalize moved out of Batch 4 to its own small batch (it changes the move type, so it
  has to reach the hit check, the AI effectiveness and the rollout). Slow Start's stat part moved to Batch 10
  with its speed part (one turn-count rule, [pp] `TOTAL_TURNS - SLOW_START_TURN_NUMBER < 5`).

**Still open (your call, at the batch that needs it)**

- Issues 1-14 below.
- [pp] vs [SD] conflicts: Shed Skin 30% vs 33% (Batch 7).

## Context

- TODO.txt has 43 open abilities (+44 deferred) and 31 open items (+22 deferred). Only Oran/Sitrus are wired
  in the engine. 50 abilities are `when: null`, the `ON_DAMAGE` bit is never read, `AB_BREAKABLE` is unused,
  and `ON_RECEIVE_DAMAGE` is the only item `WHEN` bit the engine tests.
- Roark (first target) holds **Smooth Rock** (Nosepass, Sturdy), **Rindo Berry** (Bonsly), **Expert Belt**
  (Geodude), **Muscle Band** (Onix), **Flame Orb** (Larvitar, Guts), Sitrus (Cranidos, done). TODO marks
  these items `*`, but they're trainer-used, so they go first. **Rock Head** is on 9 trainer Pokemon (5 before
  Roark, 4 of Roark's), **Magic Guard** on Harrison's Abra, **Unburden** on Helen's Treecko (holds no item,
  so it can never activate).
- Decided: item effects are data — new Item slots `HOLD_EFFECT`, `EFFECT_PARAM`, `EFFECT_TYPE` filled from
  ItemDB.json with pokeplatinum's holdEffect / effectParam.

## Sources and rules used below

- [pp] = pret/pokeplatinum, cited by function name (survives line drift). [SD] = Showdown, gen4 mod →
  gen5 → gen6 → gen7 → gen8 → base. Where they disagree on the engine, follow [pp] (as earlier engine
  decisions did) and flag it in the batch note.
- **Damage order** [pp BattleSystem_CalcMoveDamage → BattleScript_CalcMoveDamage → BattleSystem_ApplyTypeChart]:
  - Base power: variable power → Charge ×2 → Technician (≤60, ×15/10, not Struggle) → type item
    ×(100+20)/100 → Light Ball ×2 → Muscle Band ×110/100 → Thick Fat (defender) /2 → Mud/Water Sport /2 →
    Blaze/Torrent/Overgrow/Swarm ×15/10 → Heatproof (defender) /2 → Dry Skin (defender) ×125/100 →
    Rivalry ×125/100 or ×75/100 → Iron Fist ×12/10.
  - Stats: Huge/Pure Power ×2, Slow Start /2, Thick Club ×2, Hustle ×15/10, Guts ×15/10, Marvel Scale
    (defender) ×15/10, Solar Power, sandstorm SpD, Flower Gift; Simple and Unaware act on stages.
  - Then the base formula, burn (not Guts), screens, weather, Flash Fire ×15/10, +2 → crit ×2 (Sniper ×3) →
    Metronome item ×(10+n)/10 → roll → STAB (Adaptability ×2) → types → Filter/Solid Rock ×3/4 (SE) →
    Expert Belt ×120/100 (SE) → Tinted Lens ×2 (NVE).
  - Resist berries ×½: [SD] final modifier (`onSourceModifyDamage`); [pp] location not found yet.
- **AI damage mirror** [pp TrainerAI_CalcDamage = CalcMoveDamage + ApplyTypeChart + variance]: every
  base-power / stat / type-chart modifier above, for both sides, also goes into `calculate_ai_logic_damage`.
  Crit (Sniper), the Metronome item and resist berries do not. `sub_after_death` calls the engine's
  `calculate_damage`, so it picks up item/ability modifiers automatically; resist berries stay outside
  `calculate_damage`, so it never sees them, matching [pp BattleAI_PostKOSwitchIn].
- **End of turn** [pp BattleControllerPlayer_CheckMonConditions], per Pokemon: Ingrain, Aqua Ring, ABILITY
  (Speed Boost, Shed Skin), USE_ITEM (berries), LEFTOVERS (Leftovers, Black Sludge), Leech Seed, poison,
  toxic, burn, Nightmare, Curse, bind, Bad Dreams, Uproar, Thrash, Disable, Encore, Lock-On, Charge, Taunt,
  Magnet Rise, Heal Block, Embargo, Yawn, ITEM_CONDITION (status berries), ITEM_DETRIMENTAL (Flame Orb).
  The weather step before it [pp BtlCmd_EndOfTurnWeatherEffect] holds Rain Dish, Ice Body, Dry Skin,
  Hydration.
- **Accuracy order** [pp BattleControllerPlayer_CheckMoveHitAccuracy]: stages (Unaware ignores them) →
  Compound Eyes ×130/100 → Sand Veil / Snow Cloak ×80/100 → Hustle ×80/100 → Tangled Feet ×50/100 →
  Bright Powder / Lax Incense ×90/100 → Gravity.
- **Crit** [pp BattleSystem_CalcCriticalMulti]: stage = Focus Energy 2 + Scope Lens 1 + move + Super Luck 1,
  capped at 4. Battle Armor / Shell Armor are ignorable by Mold Breaker. Sniper makes the multiplier 3.
- Every new defender-side ability check goes through `ignorable_ability` (F2).
- New RNG calls run only when the ability/item is present, so golden scenarios without it keep their RNG
  order.

## Status audit (code vs TODO.txt)

| Entry                          | Code today                                                                                                                                                                                                                                  | Plan                                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Shell Armor                    | Already works: DB `on_critical`, and the `ON_CRITICAL` gate in `calculate_crit` is the immunity                                                                                                                                             | Test + Mold Breaker bypass (Batch 5), then tick    |
| Adaptability                   | AI estimate only (`damage_calc.py:546`); engine STAB is always ×1.5 (`:286`)                                                                                                                                                                | Batch 4                                            |
| Levitate                       | Toxic Spikes only (`is_grounded`); Ground moves still hit                                                                                                                                                                                   | Batch 8                                            |
| Limber / Immunity / Water Veil | Only inside `synchronize_reflect`                                                                                                                                                                                                           | Batch 7                                            |
| Sticky Hold                    | Knock Off only; Covet (`switch_items`) ignores it                                                                                                                                                                                           | Batch 13                                           |
| Leaf Guard                     | Toxic Spikes only                                                                                                                                                                                                                           | Batch 7                                            |
| Magic Guard                    | Weather, residuals, hazards, full paralysis done. Missing: recoil, Aftermath, Rough Skin, Liquid Ooze, Black Sludge, Toxic Spikes poison. Blocks the confusion self-hit, which it shouldn't (Issue 7)                                       | Spread over Batches 3, 6, 7, 11, 13; tick after 13 |
| Sturdy                         | Done (Batch 3 + OHKO moves). Gen IV effect is OHKO immunity only ([SD gen4] `onDamage` undefined; [pp BtlCmd_TryOHKOMove])                                                                                                             | Batch 3 guard                                      |
| Rock Head                      | None; Take Down is the only recoil move                                                                                                                                                                                                     | Batch 3                                            |
| Unburden                       | None                                                                                                                                                                                                                                        | Batch 10 (`CAN_UNBURDEN`, no F3)                   |
| No Gen IV singles effect       | Lightning Rod, Storm Drain ([SD gen4] `onTryHit` undefined), Plus, Minus ([pp] needs an ally), Stench ([SD gen4]), Honey Gather, Illuminate, Run Away, Anticipation, Forewarn, Frisk (messages only), Gluttony (no pinch berries in ItemDB) | Batch 14: tick after a one-line note, no code      |
| Out of scope                   | Forecast (Castform), Multitype (Arceus), Color Change (needs base-type restore on switch-out)                                                                                                                                               | Batch 14: leave open                               |

## Issues found while mapping (evidence only, nothing changed; your call before the batch that needs it)

1. **Thick Fat is read from the attacker.** `ab_modify_stat(attacker, …)` (`damage_calc.py:114,126`): a
   defender's Thick Fat never applies, and an attacker's halves its own Fire/Ice moves. [pp]: defender's
   ability, halves base power. Needed by Batch 4. **FIXED in Batch 4.**
2. **The base damage formula uses float division.** `damage_calc.py:446` (also 471, 510): `2*level/5` isn't
   floored; [pp] and [SD] floor it (level 12 gives ×6.8 instead of ×6). Affects every hit. Batch 1 and 4
   tests will run into it. **FIXED in Batch 1** (all 4 copies, incl. `struggle`).
3. **`ab_on_try_move` returns at the first match** (`engine_helper.py:324-362`): an attacker's Hustle skips
   the defender's Sand Veil, Soundproof and Water Absorb. Needed by Batches 5 and 8.
4. **Water Absorb has no target/power filter** (`engine_helper.py:358`): Rain Dance, Water Sport, Aqua Ring
   or Withdraw used against a Water Absorb foe heal it and fail. [pp BattleSystem_TriggerImmunityAbility]
   only absorbs damaging Water moves. Needed by Batch 8.
5. **Aftermath's condition looks inverted** (`battle.py:380`): `move[_MOVE_DAMAGE] != 0` is only true for
   fixed-damage moves, so Tackle-style contact moves never trigger it. Same gate as Batch 6.
6. **A berry can revive a Pokemon KO'd by its own confusion hit**: `confusion()` calls `item_on_rdmg` at
   0 HP (`engine_helper.py:631-635`) and `eat_berry` only checks ≤50%. Batch 2 reuses that hook.
   **FIXED in Batch 2** (`eat_berry` needs HP > 0).
7. **Magic Guard skips the confusion self-hit** (`engine_helper.py:628`). [pp subscript_hurt_self_in_confusion]
   has no Magic Guard check, and in [SD gen4] confusion damage is a Move effect. Batch 13.
8. **The AI estimate halves burn without the Guts exemption** (`damage_calc.py:513-515`; the engine path
   exempts it at 242-247). [pp] uses one function for both. Batch 1. **FIXED in Batch 1.**
9. **`sub_after_death` damage is divided by 100**: `trainer_ai.py:150` passes `roll_multiplier=1`.
   [pp BattleAI_PostKOSwitchIn] passes that 1 as `criticalMul`, with no variance. Until fixed, item modifiers
   there are invisible. Batch 1. **FIXED in Batch 1** (`roll_multiplier=100`).
10. **`basic_stat_change`** reads Keen Eye from the AI (`trainer_ai_helper.py:623`) while Hyper Cutter /
    Clear Body read the target, and those checks ignore the boost's sign (Swagger and Flatter score −10).
    Batch 9.
11. **The ability-guess relevance set** misses Insomnia, Sticky Hold, Poison Heal, Truant and Multitype
    (`trainer_ai_helper.py:114-170`). Every AI ability batch.
12. **Bench items are stale** in the UI and in `continue_from_node` (`serializer.py:129`,
    `SearchEngine/models.py:352-390`), so an eaten berry reappears. Shows up once Batch 2 adds consumables.
    **FIXED in Batch 2** (`bench_delta` keeps item id, consumed item and knocked off; the block is rebuilt
    from `ITEM_TABLE`).
13. `test_jit_smoke.py:74` `CASES` never asserts the switching, healing_misc and move_calling scenarios.
14. Hustle and Sand Veil scale accuracy before the stage ratio (`engine_helper.py:336-346`); [pp] scales
    after. Minor rounding.
15. Existing base-power order differs slightly from [pp]: Sport runs after Blaze/Iron Fist (`calculate_damage`);
    [pp] runs Sport before the pinch abilities and Iron Fist last. New modifiers follow [pp] order.
    **FIXED in Batch 4.**
16. Out of scope, FYI: `pokemon.py:112` (`getattr(Status, self, …)`) raises when a Pokemon is built with a
    status; recharge (`CHARGE_RECHARGE = -1`) is never handled (Hyper Beam is deferred anyway).
17. FYI for settled decisions and known gaps: [pp] Gravity accuracy is `hitRate * 10 / 6`
    (BattleControllerPlayer_CheckMoveHitAccuracy; the engine uses [SD]'s 6840/4096). `BattleAI_PostKOSwitchIn`
    exists in pokeplatinum `src/battle/battle_lib.c`; its stage 1 uses `BattleSystem_CalcEffectiveness`,
    which checks Gravity for Levitate.

## Batch 0 — Foundations (no TODO box on its own) — DONE

**F1. Item effect slots (decided).**

- The Item block gets `HOLD_EFFECT`, `EFFECT_PARAM`, `EFFECT_TYPE` after `ITEM_USER`. `ITEM_LEN` is derived,
  so only its last-slot reference changes (`idx_const.py:213`).
- New enum `HoldEffect` in `Models/helper.py`, named after [pp] hold effects: `TYPE_BOOST`,
  `POWER_UP_PHYS`, `POWER_UP_SE`, `WEAKEN_SE` (resist berries, `EFFECT_TYPE` = the type), `WEAKEN_NORMAL`
  (Chilan), `HP_RESTORE` (Oran 10, Berry Juice 20), `HP_PCT_RESTORE` (Sitrus 25), `PSN_RESTORE`,
  `SLP_RESTORE`, `STATUS_RESTORE` (Lum), `HEAL_INFATUATION`, `ACC_REDUCE`, `CRITRATE_UP`,
  `SOMETIMES_PRIORITY`, `MAYBE_ENDURE`, `HP_RESTORE_GRADUAL`, `HP_RESTORE_PSN_TYPE`, `BRN_USER`,
  `EXTEND_SCREENS`, `EXTEND_SANDSTORM`, `CHARGE_SKIP`, `SWITCH`, `BOOST_REPEATED`, `CUBONE_ATK_UP`,
  `PIKA_POWER_UP`.
- ItemDB.json gets `hold_effect`, `effect_param`, `effect_type` on every entry, values from
  `pokeplatinum/res/items/data/<item>.json` (type items 20, Muscle Band 10, Expert Belt 20, Quick Claw 20,
  Focus Band 10, Bright Powder / Lax Incense 10, Light Clay 3, Smooth Rock 3, Metronome 10, Black Sludge 16).
  `item_to_np` writes them; `ITEM_TABLE` follows automatically.
- Thick Club has two users (Cubone, Marowak) but `ITEM_USER` holds one, so its check uses a 2-species tuple.
- `item_on_rdmg` / `eat_berry` move from `ITEM_TYPE` + `ITEM_50HP` to `HOLD_EFFECT` dispatch, same behavior
  for Oran/Sitrus. Needed for Berry Juice (typed consumable, not berry) and the status berries. Touches
  existing code, needs your OK.
- Wiring: `HoldEffect` goes in `generate_constants.py` and `GENERATED_CLASSES` (`test_layout.py`); update the
  item length test (`test_layout.py:58`); `python generate_constants.py`; re-bless golden. Only hashes should
  move; turns and HP must stay identical.

**F2. `ignorable_ability(defender, attacker)`** in `engine_helper.py`: returns 0 when
`defender[AB_BREAKABLE]` is set and the attacker has Mold Breaker ([pp Battler_IgnorableAbility]). New code
uses it; the existing explicit Mold Breaker checks stay as they are unless you ask.

**F3. Item loss in one place. (DROPPED, see Decisions: pp tracks `canUnburden` instead.)** `lose_item(pok)` clears the block and sets the Unburden mark;
`use_up_item(pok)` also records `CONSUMED_ITEM` for Recycle. Unburden needs every loss path routed through
them: `eat_berry`, `eat_berry_bug_bite`, `natural_gift`, `knock_off`, the Covet victim in `switch_items`, and
`switch_in`'s knocked-off drop. Touches existing code, needs your OK.

**F4. Search key.**

- `node_key` gets one "active holds an item" bit per side, in k1's free bits 10-25. An eaten berry, a used
  Power Herb or an eaten resist berry changes outcomes (CLAUDE.md: presence, not turns left).
- Done: k1 bit 10 = opp active holds an item, bit 11 = mine (not in the death phase).
- Planned `VolStatus2` bits: `FLASH_FIRE = 2` (Batch 8), `CAN_UNBURDEN = 4` (Batch 10). That fills the 3 bits per side that
  `VOL2_KEY_BITS` already reserves (`test_search.py` asserts the sum stays below 2\*\*3). A 4th bit would first
  need Gravity moved off k2 bit 62. Slow Start and Truant use `TURNS_ACTIVE`, so they need no new bit.

**F5. AI ability guess.** Every new target-ability check in `basic_flag` also goes into
`_EXPLICIT_RELEVANT` (`trainer_ai_helper.py:115-142`). That changes RNG order, so golden moves.

## Batch 1 — Damage items (Roark: Muscle Band, Expert Belt) — DONE

| Item                                                                                                                                                                                | Gen IV effect [source]                                    | Hook                                                               |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------ |
| Muscle Band                                                                                                                                                                         | Physical power ×110/100 [pp CalcMoveDamage]               | Base-power step of `calculate_damage`, and `struggle()`'s own copy |
| Expert Belt                                                                                                                                                                         | SE damage ×120/100, after Filter [pp ApplyTypeChart]      | `multipliers` (TODO at `:303`)                                     |
| Black Belt, Charcoal, Hard Stone, Metal Coat, Miracle Seed, Mystic Water, Never-Melt Ice, Poison Barb, Sea Incense, Sharp Beak, Silk Scarf, Silver Powder, Soft Sand, Twisted Spoon | Matching-type power ×(100+20)/100 [pp sTypeBoostingItems] | One `TYPE_BOOST` check at the base-power step                      |
| Thick Club                                                                                                                                                                          | Cubone/Marowak Attack ×2 [pp]                             | Attack-stat step (`ab_modify_stat` area)                           |
| Light Ball (deferred)                                                                                                                                                               | Pikachu base power ×2, both categories [pp; SD gen4]      | Base-power step                                                    |

- AI: every row also goes into `calculate_ai_logic_damage` (Expert Belt at the TODO `:559`).
- Depends on Issues 8 and 9 (AI estimate and post-KO pick), and Issue 2 shows up in the tests.
- Tests: `test_damage_calc.py` with a fixed roll, one per item plus an order case; `test_trainer_ai.py` checks
  that the AI estimate includes them.
- TODO ticks: Expert Belt, Muscle Band, the 14 type items, Thick Club; deferred Light Ball.

## Batch 2 — Consumables and timers (Roark: Rindo Berry, Smooth Rock, Flame Orb) — DONE

| Item                                                                                                                      | Gen IV effect [source]                                                                                                                                                                                                                                 | Hook                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Rindo Berry + Babiri, Charti, Chople, Coba, Colbur, Haban, Kasib, Kebia, Occa, Passho, Payapa, Shuca, Tanga, Wacan, Yache | SE hit of its type does ½, berry eaten [SD onSourceModifyDamage]                                                                                                                                                                                       | New `resist_berry()` in `_resolve_move_damage`, after `calculate_damage` (keeps that function pure). First hit of a multi-hit only. Not in the AI estimate [pp TrainerAI_CalcDamage] |
| Chilan Berry                                                                                                              | Any Normal hit does ½                                                                                                                                                                                                                                  | Same                                                                                                                                                                                 |
| Smooth Rock                                                                                                               | Sandstorm lasts 5+3 turns [pp effectParam 3]                                                                                                                                                                                                           | `_set_weather` gets the user (`battle.py:556`, caller `:772`)                                                                                                                        |
| Light Clay                                                                                                                | Reflect / Light Screen last 5+3 [pp BtlCmd_TryLightScreen]                                                                                                                                                                                             | `_set_side_condition` gets the user (`battle.py:527`, caller `:765`; there `def_side` is a field index, not the condition value)                                                     |
| Flame Orb                                                                                                                 | End of turn, last step (after Yawn): burns the holder unless it's Fire type, already statused, Water Veil, Leaf Guard in sun, or under Safeguard [pp TriggerDetrimentalHeldItem + subscript_burn]. [SD] lets it through Safeguard, so flag in the note | New last step in `_apply_residual`; Guts already handles the rest                                                                                                                    |

- Also fixes the berry hook for Issue 6 (berries need HP > 0), since every consumable shares it.
- Bug Bite on a resist berry: the berry is gone, no effect for the biter.
- UI: consumables make Issue 12 (stale bench items) visible.
- Tests: `test_battle.py` (Rindo eaten exactly once, Flame Orb timing with Guts, Smooth Rock 8 turns, Light Clay
  8 turns); `test_engine_helper.py` for the berry HP > 0 rule.
- TODO ticks: Rindo Berry, Smooth Rock, Flame Orb, Light Clay; deferred: the 15 other resist berries, Chilan.

## Batch 3 — Trainer abilities: Rock Head, Sturdy — DONE

| Ability   | Gen IV effect [source]                                                                                | Hook                                                                                                      |
| --------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Rock Head | No recoil from Take Down; Struggle still recoils [pp subscript_recoil_1_4; SD gen4 applyRecoilDamage] | `_recoil` (`battle.py:412`); add the Magic Guard check at the same spot                                   |
| Sturdy    | OHKO moves fail [pp BtlCmd_TryOHKOMove]                                                               | Guard on `_MOVE_OH_KO` in `calculate_hit_miss`; real moves and the AI came with the OHKO moves (below) |

- Golden: weather_charge has Rock Head but no recoil move, so no change expected.
- TODO ticks: Rock Head, Sturdy.

## Batch 4 — Damage abilities — DONE (Normalize and Slow Start moved out, see Decisions)

| Ability                          | Gen IV effect                                                                                 | Hook                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Adaptability                     | STAB ×2                                                                                       | `multipliers` STAB (`:286`); the AI already has it               |
| Technician                       | Power ≤60 → ×15/10, after Charge, before items, not Struggle                                  | Base-power step (`base_power_ability` needs the power)           |
| Swarm                            | Bug ×15/10 at ≤⅓ HP                                                                           | Add to `STARTER_AB`                                              |
| Rivalry                          | Same gender ×125/100, opposite ×75/100, genderless none                                       | Base-power step (needs the defender)                             |
| Filter, Solid Rock (deferred)    | SE ×3/4, before Expert Belt                                                                   | `multipliers` (TODO at `:301`)                                   |
| Sniper                           | Crit ×3                                                                                       | `multipliers` crit step                                          |
| Heatproof (deferred)             | Fire power /2 (burn part in Batch 11)                                                         | Defender base-power check (new: the gate is attacker-only today) |
| Dry Skin, Fire part (deferred)   | Fire power ×125/100                                                                           | Same                                                             |
| Marvel Scale (deferred)          | Defense ×15/10 while statused                                                                 | New defender-stat hook in `raw_atk_def`                          |
| Pure Power (deferred)            | Same as Huge Power                                                                            | `ab_modify_stat`                                                 |
| Unaware                          | Ignores the foe's stages: as attacker Def/SpD, as defender Atk/SpA (accuracy part in Batch 5) | `raw_atk_def`                                                    |
| Normalize (deferred)             | Every move becomes Normal [pp]; [SD] keeps Struggle                                           | Move type read by damage, hit check and type chart               |
| Flower Gift (deferred)           | Cherrim in sun: own Atk and SpD ×15/10 (singles)                                              | `raw_atk_def`                                                    |
| Slow Start, stat part (deferred) | Attack /2 for its first 5 turns [pp]                                                          | `ab_modify_stat` with `TURNS_ACTIVE`; speed part in Batch 10     |

- Every row also goes into `calculate_ai_logic_damage` and `struggle()`'s copy.
- Depends on Issue 1 (Thick Fat sits in the same step) and Issue 2.
- Tests: `test_damage_calc.py` per ability plus an order test (Technician before items); AI estimate parity in
  `test_trainer_ai.py`. Golden: multihit_items has Swarm, move_calling has Thick Fat.
- TODO ticks: Adaptability, Technician, Swarm, Rivalry, Filter, Sniper, Unaware; deferred Solid Rock,
  Marvel Scale, Pure Power, Normalize, Flower Gift (Heatproof, Dry Skin, Slow Start finish later).

## Batch 5 — Accuracy, crit, secondary effects

| Name                                  | Gen IV effect                                                                                        | Hook                                  |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------- |
| Compound Eyes                         | Accuracy ×130/100                                                                                    | `calculate_hit_miss`, after stages    |
| No Guard                              | Every move hits both ways, semi-invulnerable targets included; OHKO hits if user level ≥ target [pp] | Before the semi-invulnerable check    |
| Tangled Feet                          | ×50/100 against a confused holder (ignorable)                                                        | After stages                          |
| Snow Cloak (deferred)                 | ×80/100 in hail                                                                                      | After stages                          |
| Bright Powder, Lax Incense (deferred) | Defender's item, ×90/100                                                                             | After stages, before Gravity          |
| Unaware, accuracy part                | Ignores the foe's accuracy/evasion stages [pp]                                                       | Stage step                            |
| Scope Lens, Super Luck                | Crit stage +1                                                                                        | `calculate_crit` after the move ratio |
| Shell Armor, Battle Armor             | Already block crits; add the Mold Breaker bypass                                                     | `calculate_crit` gate                 |
| Anger Point (deferred)                | Taking a crit → Attack +6                                                                            | After the hit is applied              |
| Serene Grace                          | Secondary chance ×2, flinch included [pp BtlCmd_CheckEffectActivation]                               | `sec_effects` + `flinch_checker`      |
| Shield Dust                           | No secondary effects or flinch on the holder                                                         | `sec_effects` + `flinch_checker`      |
| Skill Link (deferred)                 | 2-5 hit moves always hit 5 [pp BtlCmd_SetMultiHit]                                                   | `ps_moves_multihit`                   |

- Depends on Issue 3 (new accuracy modifiers must stack).
- AI: review the expert accuracy checks; Issue 10 lives next door.
- TODO ticks: Compound Eyes, No Guard, Tangled Feet, Bright Powder, Scope Lens, Super Luck, Shell Armor,
  Serene Grace, Shield Dust; deferred Lax Incense, Skill Link, Anger Point (Snow Cloak after Batch 11).

## Batch 6 — Contact abilities

| Ability                 | Gen IV effect [pp BattleSystem_TriggerAbilityOnHit, `RandNext % 10 < 3`] |
| ----------------------- | ------------------------------------------------------------------------ |
| Static                  | 30% paralysis                                                            |
| Flame Body              | 30% burn                                                                 |
| Cute Charm              | 30% Attract, opposite genders only, attacker not Oblivious               |
| Effect Spore (deferred) | 30%, then ⅓ each sleep / paralysis / poison                              |
| Rough Skin (deferred)   | Attacker loses ⅛ max HP, unless Magic Guard                              |

- Hook: `contact_ability` (`engine_helper.py:639`); statuses go through the shared immunity helper from
  Batch 7 and through `synchronize_reflect`. The note checks which of them fire on the KO hit (today only
  Aftermath does).
- Depends on Issue 5 (Aftermath shares the gate).
- Golden: status (Static) and multihit_items / healing_misc (Effect Spore) will move; explain each.
- TODO ticks: Cute Charm, Flame Body, Static; deferred Effect Spore, Rough Skin.

## Batch 7 — Status immunity, cures, status berries

| Name                                      | Gen IV effect                                                                                                               | Hook                                                                                                                                                   |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Limber, Immunity, Water Veil, Magma Armor | No paralysis / poison+toxic / burn / freeze (ignorable)                                                                     | One `ability_blocks_status(pok, source, status, weather)` used by `apply_status`, `synchronize_reflect`, `contact_ability`, `_toxic_spikes`, Flame Orb |
| Leaf Guard (deferred)                     | In sun, no new status (Rest exception)                                                                                      | Same helper                                                                                                                                            |
| Own Tempo (deferred)                      | No confusion                                                                                                                | `vol_status` confusion branch                                                                                                                          |
| Oblivious                                 | No Attract (Captivate isn't in MoveDB)                                                                                      | `vol_status` Attract branch + Cute Charm                                                                                                               |
| Magic Guard                               | Toxic Spikes don't poison it [SD gen4]                                                                                      | `_toxic_spikes`                                                                                                                                        |
| Early Bird                                | Sleep counter drops by 2 [pp CheckStatusDisruption]                                                                         | `early_returns` sleep step                                                                                                                             |
| Natural Cure                              | Status cured on switch-out, including Baton Pass and Roar [pp BtlCmd_TryRestoreStatusOnSwitch]                              | `reset_switch_out`, before the Worry Seed restore                                                                                                      |
| Shed Skin                                 | 30% cure in the ABILITY step [pp TriggerTurnEndAbility; SD says 33%, flag]                                                  | `on_residual`                                                                                                                                          |
| Hydration                                 | Rain: cured at the weather step [pp EndOfTurnWeatherEffect]                                                                 | `_residual_weather`                                                                                                                                    |
| Pecha, Chesto (deferred), Lum (deferred)  | Cure on getting the status (Lum also confusion), and again at the ITEM_CONDITION step; Bug Bite gives the cure to the biter | After the status is set + new end-of-turn step + `_apply_berry_effect`                                                                                 |
| Mental Herb                               | Cures Attract only in Gen IV [SD gen4 onUpdate]                                                                             | After Attract is set                                                                                                                                   |

- AI: the immunity tuples already exist (`POISON_AB_IM`, `PARA_AB_IM`, `BURN_AB_IM`); review where
  `basic_move_status` checks Leaf Guard and Hydration (only in the poison branch today).
- Search (optional): `rollout_pref` still gives weight 1 to a status move into an immune ability.
- TODO ticks: Early Bird, Hydration, Natural Cure, Oblivious, Shed Skin, Water Veil, Pecha Berry, Mental
  Herb; deferred Immunity, Leaf Guard, Limber, Magma Armor, Own Tempo, Chesto Berry, Lum Berry.

## Batch 8 — Type immunity and absorb abilities

| Ability                         | Gen IV effect [pp BattleSystem_TriggerImmunityAbility]                                                                 | Hook                                                                       |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Levitate                        | Ground immunity (ignorable; Gravity grounds it)                                                                        | `calculate_hit_miss` type check; `is_grounded` already covers hazards      |
| Volt Absorb (deferred)          | Any Electric move from the foe heals ¼, status moves too ([pp] has no power check)                                     | `ab_on_try_move`                                                           |
| Motor Drive (deferred)          | Electric immunity + Speed +1                                                                                           | Same                                                                       |
| Flash Fire                      | Damaging Fire moves and Will-O-Wisp: immune, sets `VOL2 FLASH_FIRE` (not while frozen); its Fire damage ×15/10 at Mod1 | `ab_on_try_move` + `multipliers` (TODO `:267`) + AI estimate (TODO `:536`) |
| Wonder Guard (deferred)         | Only super-effective damaging hits land; Fire Fang always does ([pp] bug)                                              | Type check                                                                 |
| Dry Skin, Water part (deferred) | Damaging Water moves heal ¼                                                                                            | `ab_on_try_move`                                                           |
| Scrappy                         | Normal and Fighting hit Ghost                                                                                          | `matchup_types` (4 callers)                                                |

- Depends on Issues 3 and 4 (the absorbs reuse Water Absorb's path).
- AI: the `trainer_ai_effectiveness` TODOs (`trainer_ai_helper.py:363-365, 379`); `basic_flag` already scores
  absorbs −12.
- Search: `rollout_pref`'s immune check (`mcts_eval.py:196-203`) should count these (CLAUDE.md step 5).
- Golden: status (Flash Fire) and healing_misc (Levitate) will move.
- TODO ticks: Flash Fire, Levitate, Scrappy; deferred Motor Drive, Volt Absorb, Wonder Guard (Dry Skin after
  Batch 11).

## Batch 9 — Switch-in abilities and stat-drop guards

| Ability                            | Gen IV effect                                                                                                                                                                                                          | Hook                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Clear Body, White Smoke (deferred) | Block every foe-caused drop, Intimidate and secondaries included (ignorable)                                                                                                                                           | `stat_changes` (same pattern as the Mist flag) + Intimidate in `switch_in` |
| Hyper Cutter                       | Blocks Attack drops only                                                                                                                                                                                               | Same                                                                       |
| Download (deferred)                | +1 SpA if the foe's Def ≥ SpD, else +1 Atk [SD gen4]                                                                                                                                                                   | `switch_in`                                                                |
| Trace                              | Copies the foe's ability on entry; can't copy Trace, Multitype, Forecast [SD gen4; confirm in pp TriggerEffectOnSwitch]. Reuses the Worry Seed mechanism (`BASE_AB_ID` + `ABILITY_TABLE`), so it reverts on switch-out | `switch_in`                                                                |
| Pressure (deferred)                | The foe's moves aimed at it cost 2 PP [pp DecrementPP]                                                                                                                                                                 | PP decrement in `_execute_move_slot`                                       |

- AI: Issue 10; Intimidate already respects Mist.
- TODO ticks: Clear Body, Hyper Cutter, Trace; deferred White Smoke, Download, Pressure.

## Batch 10 — Speed and turn order

| Name                              | Gen IV effect                                                                                                                                                          | Hook                                                 |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Quick Feet                        | ×15/10 while statused, replaces the paralysis ¼                                                                                                                        | `check_speed`                                        |
| Unburden                          | ×2 when `VOL2 CAN_UNBURDEN` is set and it holds no item; set in `switch_in` for an Unburden holder with an item, and when Trace copies Unburden while holding one [pp] | `check_speed` + `switch_in`                          |
| Slow Start (deferred)             | Speed /2 and Attack /2 for its first 5 turns (stat part moved here from Batch 4)                                                                                       | `check_speed` + `ab_modify_stat`, `TURNS_ACTIVE`     |
| Quick Claw                        | 20%: goes first within its priority bracket, one roll per holder per turn; both holders → speed [pp BattleSystem_CompareBattlerSpeed]                                  | `move_order`, between priority and the speed compare |
| Stall (deferred)                  | Last within its bracket                                                                                                                                                | Same                                                 |
| Truant (deferred)                 | Loafs every other turn ([pp Battler_CheckTruant] uses turn parity) → `TURNS_ACTIVE` parity, no new state                                                               | `early_returns`, after freeze                        |

- [pp] speed order: stages → Swift Swim / Chlorophyll → Quick Feet or paralysis → Slow Start → Unburden.
- AI: expert's move-first check uses `check_speed`, so it picks up Quick Feet and Unburden.
  [pp CompareBattlerSpeed] has an `ignoreQuickClaw` flag; confirm which value the AI passes (the
  `choose_move` docstring describes a 20% guess that isn't implemented).
- Golden: healing_misc (Truant) will move.
- TODO ticks: Quick Claw, Quick Feet, Unburden; deferred Slow Start, Stall, Truant.

## Batch 11 — Weather and end of turn

| Name                                                   | Gen IV effect                                                                  | Hook                                                                                                                  |
| ------------------------------------------------------ | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Cloud Nine, Air Lock (deferred)                        | Weather has no effect while either is out; it still counts down                | One `effective_weather(battle_array)` used at every weather read (`action`, `end_of_turn`, AI `choose_move`, rollout) |
| Drizzle, Drought, Sand Stream, Snow Warning (deferred) | Permanent weather on entry (`WEATHER_DURATION` 0)                              | `switch_in`; `start_of_battle` already orders leads by speed                                                          |
| Ice Body                                               | Hail: +1/16 and no hail damage                                                 | `heal_weather` / `weather_dmg`                                                                                        |
| Snow Cloak (deferred)                                  | No hail damage                                                                 | `weather_dmg`                                                                                                         |
| Dry Skin, weather part (deferred)                      | Rain +⅛, sun −⅛                                                                | `heal_weather` / `weather_dmg`                                                                                        |
| Leftovers                                              | +1/16 in the LEFTOVERS step (after Speed Boost / Shed Skin, before Leech Seed) | `_apply_residual` (TODO at `battle.py:1186`)                                                                          |
| Black Sludge (deferred)                                | Poison type +1/16, anyone else −⅛ unless Magic Guard                           | Same step                                                                                                             |
| Poison Heal (deferred)                                 | Heals ⅛ instead of taking poison/toxic damage                                  | Poison step                                                                                                           |
| Heatproof, burn part (deferred)                        | Burn damage 1/16 [pp subscript_burn_damage]                                    | Burn step                                                                                                             |
| Bad Dreams (deferred)                                  | Sleeping foe loses ⅛, after bind                                               | New step                                                                                                              |

- AI: expert weather logic; `GRADUAL_RECOVERY_ITEMS` already lists Leftovers / Black Sludge.
- TODO ticks: Cloud Nine, Ice Body, Leftovers; deferred Air Lock, Drizzle, Drought, Sand Stream, Snow
  Warning, Snow Cloak, Dry Skin, Black Sludge, Poison Heal, Heatproof, Bad Dreams.

## Batch 12 — Trapping

| Name                   | Gen IV effect [pp Battler_IsTrapped]                                                                      |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| Arena Trap             | Traps grounded foes (not Flying, not Levitate; Gravity grounds them)                                      |
| Shadow Tag             | Traps foes that don't have Shadow Tag                                                                     |
| Magnet Pull (deferred) | Traps Steel-type foes                                                                                     |
| Shed Shell             | Holder can always switch ([pp] returns "not trapped" before any other check; confirm it also covers bind) |

- Hooks: `valid_action_mask` (`SearchEngine/models.py:68-70`) for my switches, and the AI's `can_switch`
  (`trainer_ai.py:273`) for its withdraws. Baton Pass and Roar ignore trapping.
- TODO ticks: Arena Trap, Shadow Tag, Shed Shell; deferred Magnet Pull.

## Batch 13 — Survival, charge, consecutive use, drain

| Name                   | Gen IV effect                                                                                                                                                                        | Hook                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| Focus Band             | 10%: survives a KO at 1 HP, confusion self-hits included [pp BtlCmd_CheckHoldOnWith1HP, subscript_hurt_self_in_confusion]                                                            | `endure_damage` + `confusion()`                                                                |
| Power Herb             | Skips one charge turn (Dig, Bounce; not Bide), so no semi-invulnerable turn; used up                                                                                                 | Charge branch of `_execute_move_slot` (`battle.py:672-681`)                                    |
| Metronome (item)       | Same move again: ×(10+n)/10, n up to 10; another move resets it; not counted while locked (Uproar, Rollout); −1 when the move fails [pp UpdateMetronomeCount / VerifyMetronomeCount] | New Pok slot (move id and count packed, like Encore's counter); `multipliers` (TODO at `:276`) |
| Liquid Ooze (deferred) | Drain moves and Leech Seed hurt the drainer instead (Magic Guard drainer unaffected) [pp subscript_drain_half_damage_dealt]                                                          | `drain()` gets the defender (callers `battle.py:445, 468`) + Leech Seed (`:1039`)              |
| Berry Juice (deferred) | +20 HP at ≤½                                                                                                                                                                         | `HP_RESTORE` family from F1                                                                    |
| Sticky Hold (deferred) | Also blocks Covet [SD gen4 onTakeItem] and Bug Bite [SD takeItem]; confirm in [pp]                                                                                                   | `switch_items`, Bug Bite branch                                                                |
| Magic Guard (rest)     | Remaining sources: recoil (Batch 3), Aftermath and Rough Skin (Batch 6), Toxic Spikes (Batch 7), Black Sludge (Batch 11), Liquid Ooze (here), plus Issue 7                           | —                                                                                              |

- Search: the Metronome count changes damage; key it like Fury Cutter's `CONSEC_COUNT` (which isn't keyed
  today) or not, decide in the note.
- TODO ticks: Focus Band, Power Herb, Metronome, Magic Guard; deferred Berry Juice, Liquid Ooze, Sticky Hold.

## Batch 14 — No-op confirmations and out of scope

- Tick after a one-line note each, no code: Lightning Rod, Storm Drain, Anticipation, Forewarn, Frisk, Plus,
  Minus, Stench, Honey Gather, Gluttony.
- Leave open: Forecast, Multitype, Color Change.
- Optional extras from CLAUDE.md's known gaps, not in ItemDB (adding them shifts `ItemNames` ids): Damp Rock,
  Big Root, Grip Claw.

## Discoveries (noticed, not fixed yet)

Added at the end of each batch. Remove an entry only once it's fixed or you drop it.

- Batch 0: Berry Juice now works through the HP_RESTORE dispatch; its deferred TODO.txt box can be ticked.
- Batch 0: pp item data also has `pluckEffect` / `flingEffect`, which ItemDB doesn't carry. Fling isn't
  implemented; Bug Bite gates on `ITEM_TYPE == BERRY`, so Berry Juice can't be bitten. Check against pp's
  pluck effects when Bug Bite or Fling is touched.
- Batch 0: `ITEM_TYPE` / `WHEN` are still the gates for Bug Bite, Covet and the `item_on_rdmg` callers;
  candidates to move to `HOLD_EFFECT` when those paths are touched.
- Batch 1: [pp BattleAI_PostKOSwitchIn] stage 2 skips moves with data power 1 (variable power), not status moves;
  a status move (power 0) still scores about 2 × type effectiveness there. `sub_after_death` skips status
  moves instead. Only affects tie-breaks.
- Batch 1: `calculate_damage_confusion` applies Guts / Huge Power / Hustle after the stat stage; [pp] applies
  them to the raw stat before the stage (Thick Club already follows [pp]). Can be off by a point.
- Batch 1: [pp] Expert Belt also needs the move's data power to be non-zero (`ApplyTypeMultiplier` only flags
  super effective when `movePower`); the engine checks the effectiveness only. Same result for every MoveDB
  move: the variable-power ones (Flail, Gyro Ball, Low Kick, Magnitude, Natural Gift) have data power 1 in [pp],
  and fixed-damage moves don't reach the type chart.
- Batch 1: outdated TODO comments (left in place): `damage_calc.py` `# TODO: Expert belt` in `multipliers`, the
  Expert belt half of `# TODO: Solid Rock and Filter, Expert belt` in the AI estimate, `#TODO: Silk Scarf` and
  the Thick Club half of `#TODO: Choice Band, Thick Club` in `calculate_damage_confusion`.
- Batch 1: `ABILITIES_ITEMS_PLAN.md` got reformatted (aligned tables) by the editor on save, not by me.
- Batch 2: the rollout (`rollout_pref`, `mcts_eval` damage estimates) calls `calculate_damage`, so it doesn't
  see resist berries halving a hit. The engine and the search key do.
- Batch 2: Flame Orb's Water Veil / Leaf Guard checks are inline in `_flame_orb`; Batch 7's
  `ability_blocks_status` should take them over. Its Leaf Guard sun check will need Cloud Nine
  ([pp] `CheckIgnoreWeather`) once Batch 11 adds `effective_weather`.
- Batch 2: [pp] subscript_burn toggles `SYSCTL_TRY_SYNCHRONIZE_STATUS` for the Flame Orb burn too; the engine
  doesn't run Synchronize there ([SD] skips it when the source is the holder). Only matters for a Synchronize
  holder with Flame Orb.
- Batch 2: resist berries ignore Substitute because the engine has no Substitute yet; [SD] skips the berry
  when the hit lands on a substitute.
- Batch 2: outdated TODO comment (left in place): `_set_weather`'s `TODO: Damp Rock, Smooth Rock` (Smooth Rock
  is done; Damp Rock isn't in ItemDB).
- Explosion: the AI branches come from [pp script.s] only; Pokemow's per-move Basic/Expert pages couldn't be
  fetched. In `Expert_Explosion` the code is followed where its comments differ: the second evasion -1 starts
  at +4 (stage index 10, comment says +3), and at 30% HP or less both +1 rolls apply (comment table implies
  one). Worth a check against Pokemow when it's reachable.
- OHKO: `rollout_pref` computes `eff_ratio = eff // den`, so a resisted move rounds to 0 and takes the
  "immune, never pick" branch (weight 0); the `# 0.5x` branch can't be reached. Example: Tackle into Geodude is
  1 x 2 / 4 = 0. Every resisted move is dropped from the rollout heuristic (the random rollout half still uses it).
- OHKO: estimates that call `calculate_damage` see an OHKO move as power 0 chip (3 damage, L50 vs L50): the
  rollout's `o_dmg` for the opponent's chosen move, and `sub_after_death` phase 2 ([pp] stage 2 skips data
  power 1 moves, see Batch 1). Tie-breaks and the "can I survive" guess only.
- OHKO: [pp] Basic_Main sends moves with no damage comparison (Guillotine, Sheer Cold, Counter, ...) past
  Basic_CheckForImmunity straight to Basic_CheckSoundproof; only Fissure / Horn Drill are routed through it.
  The engine runs the immunity and absorb-ability checks for every damaging move. Differs only for Sheer Cold
  into Wonder Guard (engine -12, [pp] 0) and similar MOVE_EXCEP edge cases.
- OHKO: RP puts Drill Run in Horn Drill's move slot, so [pp] Basic_Main's `IfMoveEqualTo MOVE_HORN_DRILL` would
  skip Drill Run's damage scoring in RP if the ROM kept that script. Matters once Drill Run is added.
- OHKO: Levitate (Batch 8) has to go in `calculate_hit_miss`'s type check, which runs before the OHKO branch,
  so Fissure respects it. Lock-On / No Guard (Batch 5) bypass the roll but not the level check
  (`#TODO: No Guard, Lock-On` left in the branch).
- OHKO: now redundant but left in place: `gravity and not move[_MOVE_OH_KO]` in `calculate_hit_miss` and
  Hustle's `not move[_MOVE_OH_KO]` in `ab_on_try_move` (the OHKO branch returns before both matter).
- OHKO: outdated TODO comments (left in place): "OHKO Moves" in the Basic (`trainer_ai_helper.py:916`) and Expert
  (`:2014`) TODO docstrings. CLAUDE.md's known gap "OHKO moves skip the semi-invulnerability check" is fixed.
- Batch 4: a defending Simple doesn't check Mold Breaker (`def_is_simple` in `raw_atk_def` and `struggle`); [pp]
  doubles the defender's stages only through `Battler_IgnorableAbility(SIMPLE)`.
- Batch 4: Reckless still runs last in `base_power_ability`. It isn't in [pp] `CalcMoveDamage` and wasn't found in
  `battle_lib.c` / `battle_script.c`; if it's applied through the move's `powerMul` (the first step of
  `CalcMoveDamage`), it belongs before Charge and the items. Rounding only.
- Batch 4: `struggle()` has no weather argument, so the holder's Flower Gift Attack boost in sun doesn't reach
  Struggle ([pp] runs Struggle through `CalcMoveDamage`).
- Batch 4: [pp] CALC_SELF_HIT runs the confusion hit through `CalcMoveDamage` with attacker == defender, where
  Unaware would zero its own stages; `calculate_damage_confusion` leaves Unaware out (your call, Batch 4).
- Batch 4: like Expert Belt, [pp] Filter / Solid Rock also need the move's data power to be non-zero; the engine
  checks the effectiveness only (same result for every MoveDB move, see the Batch 1 note).
## UI (cross-batch)

- New `VolStatus2` bits get badges automatically (`serializer.py` builds the names from the enum).
- No ability is serialized anywhere; items are (the active's from the snapshot, the bench's stale, Issue 12).
- `BoxEntry` has no item field; items are picked per battle in `MyTeamSlot`. Unchanged unless you want box
  items.

## Verification (every batch)

- Unit tests in the matching file: `test_damage_calc.py` (fixed `roll_multiplier`), `test_engine_helper.py`,
  `test_status_calc.py`, `test_battle.py`, `test_trainer_ai.py`, `test_search.py`, `test_database.py`
  (new ItemDB fields convert), `test_layout.py` (item slots).
- `pytest`; `pytest -m jit` for any njit change; `pytest -m slow` when layout or turn flow changes (Batch 0,
  new Pok/VOL2 slots, new end-of-turn steps).
- Golden: `pytest tests/test_engine_golden.py --update-golden`, then compare turns/HP with the old file and
  explain each change. Scenarios already carry Static, Flash Fire, Effect Spore, Swarm, Truant, Sticky Hold,
  Levitate, Sturdy, Rock Head and Thick Fat, so those batches will move them.
- After a layout change: `python generate_constants.py`; clear `.numba_cache/` if `NUMBA_CACHE_ON=1`.
- At the end of each batch: list the TODO boxes that can be ticked and the TODO comments that became outdated
  (e.g. `damage_calc.py:301/303/312`, `battle.py:558/1186`, `engine_helper.py:782`,
  `trainer_ai_helper.py:614`), removed only when you ask.
