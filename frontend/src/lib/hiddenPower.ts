import type { IVs, MoveInfo } from "../types";

// Hidden Power, same rule as Models/pokemon.py hidden_power ([pp] CalcHiddenPowerParams)
const HP_ORDER: (keyof IVs)[] = [
  "HP",
  "Attack",
  "Defense",
  "Speed",
  "Special Attack",
  "Special Defense",
];
const HP_TYPES = [
  "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel",
  "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon", "Dark",
];

// No IVs set means all 31, like Models/pokemon.py
export function hiddenPower(ivs?: IVs): { type: string; power: number } {
  let typeBits = 0;
  let powerBits = 0;
  HP_ORDER.forEach((s, i) => {
    const iv = ivs?.[s] ?? 31;
    typeBits |= (iv & 1) << i;
    powerBits |= ((iv >> 1) & 1) << i;
  });
  return {
    type: HP_TYPES[Math.floor((typeBits * 15) / 63)],
    power: Math.floor((powerBits * 40) / 63) + 30,
  };
}

// A move as this Pokémon has it: MoveDB's data, but Hidden Power's type and power follow its IVs
export function moveInfoFor(
  moveInfo: Record<string, MoveInfo> | undefined,
  move: string,
  ivs?: IVs,
): MoveInfo | undefined {
  const info = moveInfo?.[move];
  if (!info || move !== "Hidden Power") return info;
  return { ...info, ...hiddenPower(ivs) };
}
