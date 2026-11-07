// How a party card uses the room it gets. The sizes are what each layout's content needs.

export type CardSize = "sm" | "md" | "lg"; // text and inputs

export interface CardFit {
  layout: "wide" | "tall" | "row"; // sprite beside everything / on top / beside its info
  scale: number; // the sprite is this × its 96px art
  box: number; // the sprite's box in px
  size: CardSize;
  stats: boolean; // stat bars on the card, not only on hover
  moveColumns: 1 | 2;
}

export const OPPONENT_MIN_HEIGHT = 92;

export const spriteBox = (scale: number) => Math.round(96 * scale * 0.78); // the art has transparent padding

const SMALLEST: CardFit = { layout: "row", scale: 1, box: 100, size: "sm", stats: false, moveColumns: 2 };

export function teamCardFit(width: number, height: number): CardFit {
  const big = width >= 480;
  if (width >= 600 && height >= 530) {
    const scale = Math.min(6, Math.floor(Math.min(width * 0.45, height * 0.7) / 96));
    return {
      layout: "wide",
      scale,
      box: spriteBox(scale),
      size: "lg",
      stats: true,
      moveColumns: height >= 800 ? 1 : 2,
    };
  }
  // Stacked, as long as the sprite on top still gets a good size
  const moveColumns = big && height < 910 ? 2 : 1;
  const rest = !big ? 510 : moveColumns === 1 ? 605 : 505; // what all but the sprite takes
  const widest = Math.min(4, Math.floor((width - 26) / 96));
  const scale = Math.min(widest, Math.floor((height - rest) / spriteBox(1)));
  if (scale >= (big ? 3 : 2)) {
    return {
      layout: "tall",
      scale,
      box: spriteBox(scale),
      size: big ? "lg" : "md",
      stats: true,
      moveColumns,
    };
  }
  if (width < 340) return SMALLEST; // no room beside a bigger sprite
  if (height >= 404 && big) {
    return { layout: "row", scale: 3, box: spriteBox(3), size: "md", stats: true, moveColumns: 2 };
  }
  if (height >= 400) {
    return { layout: "row", scale: 2, box: spriteBox(2), size: "md", stats: false, moveColumns: 1 };
  }
  if (height >= 314) {
    return { layout: "row", scale: 2, box: spriteBox(2), size: "md", stats: false, moveColumns: 2 };
  }
  return SMALLEST;
}
