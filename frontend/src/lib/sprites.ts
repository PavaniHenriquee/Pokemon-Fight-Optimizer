// Every image the app shows. Each builder returns URLs in the order <Sprite> tries them:
// the local copy from fetch_sprites.py first (works offline in Electron), then the remote one.
const LOCAL = `${import.meta.env.BASE_URL}sprites`;
const POKEAPI = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon";
const SHOWDOWN = "https://play.pokemonshowdown.com/sprites";

// Showdown names these icons without hyphens
const ITEM_SLUG_OVERRIDES: Record<string, string> = {
  "bright-powder": "brightpowder",
  "never-melt-ice": "nevermeltice",
  "silver-powder": "silverpowder",
  "twisted-spoon": "twistedspoon",
};

// Same rule fetch_sprites.py uses for the local file names
export const itemSlug = (name: string) => {
  const slug = name.toLowerCase().replace(/[\s_]+/g, "-");
  return ITEM_SLUG_OVERRIDES[slug] ?? slug;
};

// Animated Gen V battle sprite, static PNG when there's no animation (some forms)
export function battleSprite(id: number, side: "front" | "back"): string[] {
  const back = side === "back" ? "back/" : "";
  return [
    `${LOCAL}/${side}/${id}.gif`,
    `${LOCAL}/${side}-static/${id}.png`,
    `${POKEAPI}/versions/generation-v/black-white/animated/${back}${id}.gif`,
    `${POKEAPI}/${back}${id}.png`,
  ];
}

export function frontStatic(id: number): string[] {
  return [`${LOCAL}/front-static/${id}.png`, `${POKEAPI}/${id}.png`];
}

export function pokIcon(id: number): string[] {
  return [
    `${LOCAL}/icons/${id}.png`,
    `${POKEAPI}/versions/generation-vii/icons/${id}.png`,
  ];
}

export function itemIcon(name: string): string[] {
  const slug = itemSlug(name);
  return [`${LOCAL}/items/${slug}.png`, `${SHOWDOWN}/itemicons/${slug}.png`];
}

// PokeAPI type ids (same numbering as Types in Models/helper.py); Typeless has no sprite
const TYPE_IDS: Record<string, number> = {
  normal: 1, fighting: 2, flying: 3, poison: 4, ground: 5, rock: 6, bug: 7, ghost: 8,
  steel: 9, fire: 10, water: 11, grass: 12, electric: 13, psychic: 14, ice: 15,
  dragon: 16, dark: 17, fairy: 18,
};

// Scarlet/Violet type badges (200×40, include Fairy)
export function typeSprite(type: string): string[] {
  const id = TYPE_IDS[type.toLowerCase()];
  if (!id) return [];
  return [
    `${LOCAL}/types/${id}.png`,
    `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/types/generation-ix/scarlet-violet/${id}.png`,
  ];
}

export function trainerSprite(sprite: string): string[] {
  return [`${LOCAL}/trainers/${sprite}.png`, `${SHOWDOWN}/trainers/${sprite}.png`];
}
