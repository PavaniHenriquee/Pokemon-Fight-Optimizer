import { useState } from "react";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "./ui/combobox";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "./ui/input-group";
import type { BoxEntry, IVs, PokemonData } from "../types";

// ─── Shared helpers ───────────────────────────────────────────────────────────

const inp =
  "bg-slate-700 border border-slate-600 text-slate-100 text-sm rounded px-2 py-1 focus:outline-none focus:border-violet-500 w-full";

const IV_KEYS: (keyof IVs)[] = [
  "HP",
  "Attack",
  "Defense",
  "Special Attack",
  "Special Defense",
  "Speed",
];
const IV_LABELS = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"];

const DEFAULT_IVS: IVs = {
  HP: 31,
  Attack: 31,
  Defense: 31,
  "Special Attack": 31,
  "Special Defense": 31,
  Speed: 31,
};

function makeBlank(): Omit<BoxEntry, "id"> {
  return {
    name: "",
    gender: "Male",
    nature: "Hardy",
    ability: "",
    level: 5,
    moves: ["", "", "", ""],
    ivs: { ...DEFAULT_IVS },
  };
}

function iconUrl(id: number) {
  return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/${id}.png`;
}

function PokIcon({ id, size = 40 }: { id: number | undefined; size?: number }) {
  if (!id) {
    return (
      <div
        className="bg-slate-700 rounded shrink-0"
        style={{ width: size, height: Math.round(size * 0.75) }}
      />
    );
  }
  return (
    <img
      src={iconUrl(id)}
      width={size}
      height={Math.round(size * 0.75)}
      alt=""
      draggable={false}
      style={{ imageRendering: "pixelated" }}
    />
  );
}

// ─── Add / Edit modal ─────────────────────────────────────────────────────────

function BoxEntryModal({
  entry,
  pokemonData,
  onSave,
  onCancel,
}: {
  entry: BoxEntry | null;
  pokemonData: PokemonData;
  onSave: (entry: BoxEntry) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Omit<BoxEntry, "id">>(() =>
    entry
      ? { ...entry, moves: [...entry.moves], ivs: { ...entry.ivs } }
      : makeBlank(),
  );

  const patch = (p: Partial<Omit<BoxEntry, "id">>) =>
    setDraft((d) => ({ ...d, ...p }));

  const setMove = (i: number, v: string) => {
    const moves = [...draft.moves];
    moves[i] = v;
    patch({ moves });
  };

  const setIv = (stat: keyof IVs, raw: string) => {
    const v = Math.max(0, Math.min(31, parseInt(raw) || 0));
    patch({ ivs: { ...draft.ivs, [stat]: v } as IVs });
  };

  const { pokemon, moves, natures, abilities } = pokemonData;

  // z-index 20 so it renders above the box popup (z-index 10)
  return (
    <div className="popup-overlay" style={{ zIndex: 20 }} onClick={onCancel}>
      <div
        className="popup-panel"
        style={{ maxWidth: "460px", zIndex: 20 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="popup-header">
          <h2>{entry ? `Edit ${entry.name}` : "Add to Box"}</h2>
          <button className="close-btn" onClick={onCancel}>
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-3">
          {/* Name */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <Combobox
              value={draft.name}
              onValueChange={(v) => patch({ name: v ?? "" })}
              items={pokemon}
            >
              <ComboboxInput className={inp} showClear />
              <ComboboxContent>
                <ComboboxEmpty>No results</ComboboxEmpty>
                <ComboboxList>
                  {(item: string) => (
                    <ComboboxItem key={item} value={item}>
                      {item}
                    </ComboboxItem>
                  )}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>
          </div>

          {/* Level + Gender */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs text-slate-400 mb-1">Level</label>
              <InputGroup>
                <InputGroupAddon align="inline-start">
                  <InputGroupButton
                    onClick={() =>
                      patch({ level: Math.max(1, draft.level - 1) })
                    }
                  >
                    -
                  </InputGroupButton>
                </InputGroupAddon>
                <InputGroupInput
                  type="number"
                  min={1}
                  max={100}
                  value={draft.level}
                  onChange={(e) =>
                    patch({ level: parseInt(e.target.value) || 1 })
                  }
                  className="text-center"
                />
                <InputGroupAddon align="inline-end">
                  <InputGroupButton
                    onClick={() =>
                      patch({ level: Math.min(100, draft.level + 1) })
                    }
                  >
                    +
                  </InputGroupButton>
                </InputGroupAddon>
              </InputGroup>
            </div>
            <div className="flex-1">
              <label className="block text-xs text-slate-400 mb-1">
                Gender
              </label>
              <Combobox
                value={draft.gender ?? "None"}
                onValueChange={(v) =>
                  patch({ gender: v === "None" ? null : (v ?? null) })
                }
                items={["Male", "Female", "None"]}
              >
                <ComboboxInput className={inp} />
                <ComboboxContent>
                  <ComboboxList>
                    {(item: string) => (
                      <ComboboxItem key={item} value={item}>
                        {item}
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </div>
          </div>

          {/* Ability + Nature */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs text-slate-400 mb-1">
                Ability
              </label>
              <Combobox
                value={draft.ability}
                onValueChange={(v) => patch({ ability: v ?? "" })}
                items={abilities}
              >
                <ComboboxInput className={inp} showClear />
                <ComboboxContent>
                  <ComboboxEmpty>No results</ComboboxEmpty>
                  <ComboboxList>
                    {(item: string) => (
                      <ComboboxItem key={item} value={item}>
                        {item}
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </div>
            <div className="flex-1">
              <label className="block text-xs text-slate-400 mb-1">
                Nature
              </label>
              <Combobox
                value={draft.nature}
                onValueChange={(v) => patch({ nature: v ?? "Hardy" })}
                items={natures}
              >
                <ComboboxInput className={inp} />
                <ComboboxContent>
                  <ComboboxEmpty>No results</ComboboxEmpty>
                  <ComboboxList>
                    {(item: string) => (
                      <ComboboxItem key={item} value={item}>
                        {item}
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </div>
          </div>

          {/* Moves */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Moves</label>
            <div className="grid grid-cols-2 gap-2">
              {draft.moves.map((mv, i) => (
                <Combobox
                  key={i}
                  value={mv}
                  onValueChange={(v) => setMove(i, v ?? "")}
                  items={moves}
                >
                  <ComboboxInput
                    className={inp}
                    placeholder="— empty —"
                    showClear
                  />
                  <ComboboxContent>
                    <ComboboxEmpty>No results</ComboboxEmpty>
                    <ComboboxList>
                      {(item: string) => (
                        <ComboboxItem key={item} value={item}>
                          {item}
                        </ComboboxItem>
                      )}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
              ))}
            </div>
          </div>

          {/* IVs */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">IVs</label>
            <div className="grid grid-cols-3 gap-2">
              {IV_KEYS.map((stat, i) => (
                <div key={stat}>
                  <label className="block text-xs text-slate-500 mb-0.5">
                    {IV_LABELS[i]}
                  </label>
                  <InputGroup>
                    <InputGroupAddon align="inline-start">
                      <InputGroupButton
                        onClick={() =>
                          patch({
                            ivs: {
                              ...draft.ivs,
                              [stat]: Math.max(0, draft.ivs[stat] - 1),
                            },
                          })
                        }
                      >
                        -
                      </InputGroupButton>
                    </InputGroupAddon>
                    <InputGroupInput
                      type="number"
                      min={0}
                      max={31}
                      value={draft.ivs[stat]}
                      onChange={(e) => setIv(stat, e.target.value)}
                      className="text-center"
                    />
                    <InputGroupAddon align="inline-end">
                      <InputGroupButton
                        onClick={() =>
                          patch({
                            ivs: {
                              ...draft.ivs,
                              [stat]: Math.min(31, draft.ivs[stat] + 1),
                            },
                          })
                        }
                      >
                        +
                      </InputGroupButton>
                    </InputGroupAddon>
                  </InputGroup>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-1.5 text-sm text-slate-400 hover:text-slate-200 border border-slate-600 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() =>
              draft.name &&
              onSave({ ...draft, id: entry?.id ?? crypto.randomUUID() })
            }
            disabled={
              !draft.name ||
              !draft.ability ||
              !draft.moves.some((m) => m) ||
              !draft.ivs
            }
            className="px-4 py-1.5 text-sm bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white rounded-lg transition-colors disabled:cursor-not-allowed cursor-pointer"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Grid cell with hover three-dots menu ─────────────────────────────────────

function BoxCell({
  entry,
  nameToId,
  onEdit,
  onDelete,
}: {
  entry: BoxEntry;
  nameToId: Record<string, number>;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="relative group flex flex-col items-center gap-1 p-1.5 rounded-lg hover:bg-slate-700/60 cursor-default select-none">
      <PokIcon id={nameToId[entry.name]} />
      <span className="text-[10px] text-slate-400 truncate w-full text-center leading-tight">
        {entry.name}
      </span>

      {/* Three-dots — only visible on hover */}
      <button
        className="absolute top-0.5 right-0.5 w-4 h-4 rounded opacity-0 group-hover:opacity-100
                   bg-slate-600/90 hover:bg-slate-500 text-slate-200 text-[10px] leading-none
                   flex items-center justify-center transition-opacity z-10"
        onClick={(e) => {
          e.stopPropagation();
          setMenuOpen((v) => !v);
        }}
        title="Options"
      >
        ⋯
      </button>

      {menuOpen && (
        <>
          {/* Click-outside close */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute top-5 right-0 z-51 bg-slate-800 border border-slate-600 rounded-lg shadow-xl overflow-hidden min-w-[72px]">
            <button
              className="block w-full text-left px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-700 whitespace-nowrap"
              onClick={() => {
                onEdit();
                setMenuOpen(false);
              }}
            >
              Edit
            </button>
            <button
              className="block w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-slate-700 whitespace-nowrap"
              onClick={() => {
                onDelete();
                setMenuOpen(false);
              }}
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Box grid popup ───────────────────────────────────────────────────────────

function BoxPopup({
  box,
  pokemonData,
  onBoxChange,
  onSave,
  saved,
  onClose,
  onOpenEdit,
}: {
  box: BoxEntry[];
  pokemonData: PokemonData;
  onBoxChange: (box: BoxEntry[]) => void;
  onSave: () => void;
  saved: boolean;
  onClose: () => void;
  onOpenEdit: (entry: BoxEntry | null) => void;
}) {
  const { nameToId } = pokemonData;
  const emptyCount = box.length % 6 === 0 ? 0 : 6 - (box.length % 6);

  return (
    <div
      className="fixed inset-0 z-10 bg-black/60 flex items-center justify-center p-20 m-0"
      onClick={onClose}
    >
      <div
        className="popup-panel"
        style={{ maxWidth: "520px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="popup-header">
          <h2>
            Box{" "}
            <span
              style={{
                color: "var(--muted)",
                fontWeight: 400,
                fontSize: "0.8em",
              }}
            >
              ({box.length})
            </span>
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={onSave}
              className="text-xs px-2.5 py-1 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg transition-colors"
            >
              {saved ? "✓ Saved" : "Save"}
            </button>
            <button
              onClick={() => onOpenEdit(null)}
              className="text-xs px-2.5 py-1 bg-violet-600 hover:bg-violet-500 rounded-lg text-white transition-colors"
            >
              + New
            </button>
            <button className="close-btn" onClick={onClose}>
              ✕
            </button>
          </div>
        </div>

        {box.length === 0 ? (
          <p className="text-sm text-slate-500 italic text-center py-8">
            Box is empty — click + New to add a Pokémon
          </p>
        ) : (
          <div className="grid grid-cols-6 gap-1.5">
            {box.map((entry) => (
              <BoxCell
                key={entry.id}
                entry={entry}
                nameToId={nameToId}
                onEdit={() => onOpenEdit(entry)}
                onDelete={() =>
                  onBoxChange(box.filter((e) => e.id !== entry.id))
                }
              />
            ))}
            {/* Placeholder cells to complete the last row */}
            {Array.from({ length: emptyCount }).map((_, i) => (
              <div
                key={`ph-${i}`}
                className="rounded-lg border border-dashed border-slate-700/40"
                style={{ height: 62 }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Exported: trigger + popup orchestration ──────────────────────────────────

export default function BoxView({
  box,
  pokemonData,
  onBoxChange,
  onSave,
}: {
  box: BoxEntry[];
  pokemonData: PokemonData;
  onBoxChange: (box: BoxEntry[]) => void;
  onSave: () => void;
}) {
  const [popupOpen, setPopupOpen] = useState(false);
  const [editEntry, setEditEntry] = useState<BoxEntry | "new" | null>(null);
  const [saved, setSaved] = useState(false);

  function handleSave() {
    onSave();
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <>
      <button
        onClick={() => setPopupOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-sm text-slate-200 transition-colors cursor-pointer"
      >
        Box
        <span className="text-slate-400 text-xs">({box.length})</span>
      </button>

      {/* Grid popup */}
      {popupOpen && (
        <BoxPopup
          box={box}
          pokemonData={pokemonData}
          onBoxChange={onBoxChange}
          onSave={handleSave}
          saved={saved}
          onClose={() => setPopupOpen(false)}
          onOpenEdit={(entry) => setEditEntry(entry ?? "new")}
        />
      )}

      {/* Entry modal — z-index 20, renders above box popup */}
      {editEntry !== null && (
        <BoxEntryModal
          entry={editEntry === "new" ? null : editEntry}
          pokemonData={pokemonData}
          onSave={(entry) => {
            onBoxChange(
              editEntry === "new"
                ? [...box, entry]
                : box.map((e) => (e.id === entry.id ? entry : e)),
            );
            setEditEntry(null);
          }}
          onCancel={() => setEditEntry(null)}
        />
      )}
    </>
  );
}
