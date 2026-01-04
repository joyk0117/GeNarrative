# GeNarrative – Semantic Interface Structure (SIS) Specification

## 1. Overview

Semantic Interface Structure (SIS) is an **intermediate representation that extracts the “semantic information” of works and scenes and turns it into a hub for generation, search, and reuse**.
It separates **what to make (meaning)** from **how to make it (models/prompts)**, and serves as a shared language across all phases: generation, search, and learning.

### Key Benefits

1. **Modular separation & controllability**
   - Keep meaning (SIS) fixed while swapping models (SD/MusicGen, etc.) or parameters.
2. **Reproducibility & explainability**
   - Record “what semantic specification produced this” as JSON, enabling provenance checks and regeneration.
3. **Editable parameters & human correction**
   - Even if LLM extraction is imperfect, the data is structured and can be manually fixed/augmented.
4. **A common interface for search & recommendation**
   - Enables semantic search/recommendation like “melancholic + night + piano”.
5. **A foundation for training data & evaluation**
   - Use SIS as ground truth for prompt generation, QA creation, and model evaluation (consistency checks).
6. **A hub for vector DBs and other models**
   - Vectorize SIS elements to connect with external DBs or embedding models.

---

## 2. Layer Structure (Story / Scene / Media)

Within the scope of GeNarrative, SIS consists of three types of objects:

### StorySIS (Top layer: the whole work)

- An object holding the semantic structure of the entire work.
- Story structure type (Kishotenketsu, Three-Act, etc.)
- Global themes and character settings
- Global style policies (writing style / visual style / music direction)

### SceneSIS (Middle layer: minimal semantic unit)

- Represents a **single scene** as the smallest semantic unit.
- Scene meaning (summary / semantics)
- Scene-level generation policies (text / visual / audio)
  - For reusability, SceneSIS does **not** include `story_id` (the same scene can be reused across multiple stories).

### MediaSIS (Bottom layer: expression unit) — Under consideration / unused

- Represents “scene components (expression units)” by further decomposing a SceneSIS.
- Examples: shots (composition), lines, narration, subtitles, sound effects, BGM segments, props/objects, etc.

#### Connections between layers and external indexing

- The connections among StorySIS / SceneSIS / MediaSIS (mapping `story_id`, `scene_id`, `media_id`) are **not stored directly inside each SIS JSON**, but managed as an external index.
- This enables reusing a single SceneSIS / MediaSIS from multiple StorySIS objects (reusability), and makes updates robust by allowing relation-only replacements without modifying Story/Scene/Media content.
- Concretely, this is intended to be stored as relation tables in a relational DB or as edges in a graph DB.

---

## 3. StorySIS Specification

### 3.1 StorySIS – Conceptual JSON Schema

```jsonc
{
  "sis_type": "story",
  "story_id": "123e4567-e89b-12d3-a456-426614174000",

  "title": "The Girl and the Sun",
  "summary": "A girl befriends the sun and learns to share its light.",

  // Semantic structure for the whole work (themes & style policies)
  "semantics": {
    // Semantic information shared across the whole work
    "common": {
      "themes": ["trust", "learning"],
    },
    // Optional style policies for the whole work
    "text":  {"language": "English", "tone": "gentle", "point_of_view": "third"},
    "visual": {"style": "watercolor"},
    "audio": {"genre": "ambient"}
  },

  "story_type": "three_act", // e.g. "kishotenketsu" | "three_act" | "attempts" | "circular" | "catalog"

  // Scene blueprint for the story
  "scene_blueprints": [
    {
      "scene_type": "setup",
      "descriptions": [
        "Introduce the protagonist and setting (a sunny town / a hill), placing admiration for the ‘sun’ within everyday life.",
        "Depict the comfort and joy brought by sunlight while hinting at small anxieties about ‘shadows’ or ‘clouds’."
      ]
    },
    {
      "scene_type": "setup",
      "descriptions": [
        "The protagonist talks to the sun or chases its light, and the ‘seed’ of their relationship emerges.",
        "Plant foreshadowing for later conflict: an important promise (not to monopolize the light) and a small device (mirror/hat, etc.)."
      ]
    },
    {
      "scene_type": "conflict",
      "descriptions": [
        "Clouds spread and the sun is hidden. The protagonist panics and tries to bring the light back, but fails.",
        "The desire for light clashes with consideration for others, leading to misunderstandings and regret."
      ]
    },
    {
      "scene_type": "resolution",
      "descriptions": [
        "The protagonist understands that the sun is something that ‘returns’ and that light is something that can be ‘shared’.",
        "A small act (supporting a friend, finding a shady place, etc.) softens the atmosphere, and light breaks through the clouds."
      ]
    },
    {
      "scene_type": "resolution",
      "descriptions": [
        "Add a short epilogue-like beat where the same daily life looks slightly different (accepting both light and shadow).",
        "Conclude with the lesson (sharing/trust) verbalized, and the relationship with the sun gently settled."
      ]
    }
  ],



}
```

### 3.2 Field Details (Excerpt)

| Field | Type | Description |
|---|---|---|
| story_type | string | Type of story structure (e.g., Kishotenketsu) |
| semantics.common.themes | array | Themes of the whole work |
| semantics.common.descriptions | array | Additional description text that the summary cannot fully capture (nuances/intent, etc.) |
| semantics.text / semantics.visual / semantics.audio | object | Global style policies (can be overridden at SceneSIS / MediaSIS level) |

### 3.3 Standard Values for story_type

Representative patterns and the corresponding `scene_blueprints[].scene_type` are as follows.

| story_type | Overview | scene_type (scene_blueprints[].scene_type) |
|---|---|---|
| three_act | Drama style (difficulty → resolution) | setup (1–2 scenes) / conflict (1–5 scenes) / resolution (1–2 scenes) |
| kishotenketsu | Twist/turn style (meaning flips at the end) | ki (1) / sho (1–2) / ten (1) / ketsu (1–2) |
| attempts | Multiple attempts (trial and error) | problem (1) / attempt (repeat) (2–5) / result (1) |
| catalog | Catalog/intro style (weak ordering) | intro (1) / entry (repeat) (3–10) / outro (1) |

---

## 4. SceneSIS Specification

SceneSIS is a JSON object describing a single scene.

The storage format can be **JSON or JSONL**, but when handling many scenes, **JSONL (one Scene per line)** is recommended.

The JSON schema example below is **JSONC (JSON with comments)** for explanation. For actual stored files, use plain JSON/JSONL without comments.

### 4.1 SceneSIS – Conceptual JSON Schema

```jsonc
{
  "sis_type": "scene",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",

  "summary": "Introduction of the girl and the forest.",

  // Scene meaning + generation policy (shared context across modalities)
  "semantics": {
    "common": {
      "mood": "calm",
      "characters": [
        {
          "name": "Nancy",
          "traits": ["girl", "curious"],
          "visual": {
            "hair": "brown curly hair",
            "clothes": "striped shirt and purple skirt"
          }
        }
      ],
      "location": "forest",
      "time": "day",
      "weather": "sunny",
      // salient motifs and colors (easy to interpret/label semantically)
      "objects": [
        { "name": "big_sun", "colors": ["yellow", "orange"] },
        { "name": "small_house", "colors": ["red", "brown"] },
        { "name": "tree", "colors": ["green", "brown"] }
      ],
      "descriptions": [
        "Nancy quietly observes the forest, feeling both curiosity and a slight nervousness.",
        "The scene emphasizes gentle light and a peaceful, exploratory mood."
      ]
    },

    // Modality-specific semantic information
    "text": { "style": "simple", "language": "English", "tone": "gentle", "point_of_view": "third" },
    "visual": { "style": "watercolor", "composition": "mid-shot", "lighting": "soft", "perspective": "eye-level" },
    "audio": { "genre": "ambient", "tempo": "slow", "instruments": ["piano", "pad"] }
  },

}
```

> Note: Role labels for a scene (e.g., ki/sho/ten/ketsu or setup/conflict/resolution) are not stored in SceneSIS. They are managed by StorySIS `scene_blueprints[].scene_type` or by an external index.

### 4.2 Field Details (Excerpt)

#### 4.2.1 semantics (Scene semantic information)

The “semantic background” referenced by image/text/audio. In `semantics.common`, you may have fields like:

| Field | Description |
|---|---|
| characters | Character details appearing in the scene (ID, name, appearance, etc.). Scene-specific outfits can be described. |
| location | Place name |
| time | Time of day |
| weather | Weather |
| mood | Overall atmosphere |
| objects | Important motifs/colors in the scene |
| descriptions | Text notes capturing intent/nuance/interpretation beyond what the summary can express (multiple allowed) |

#### 4.2.2 semantics.text / semantics.visual / semantics.audio (Scene-level policy)

- `semantics.text/semantics.visual/semantics.audio` are **scene-level default policies**.

---

## 5. MediaSIS Specification

MediaSIS decomposes a SceneSIS into “components (expression units)”.

By aligning generation/editing/output to MediaSIS as the minimal unit, both coarse-grained and fine-grained scenes can be handled within the same framework.

### 5.1 MediaSIS – Conceptual JSON Schema

Below is a sample MediaSIS extracted from a **visual** asset only; it does not include text/audio elements.

```jsonc
{
  "sis_type": "media",
  "media_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",

  // A short summary of this media element
  "summary": "a happy scene in a park with a big sun and a small house",

  // Which modality this Media element represents (visual in this example)
  "media_type": "visual",

  // Semantic structure (extraction target)
  "semantics": {
    "common": {
      // overall mood
      "mood": "happy",
      // notes that are hard to split into fields (multiple allowed)
      "descriptions": [
        "The drawing conveys a strong sense of safety and warmth between the two figures.",
        "Colors are intentionally vivid to reflect a child's joyful perception of the world."
      ],

      "location": "park",
      "time": "day",
      "weather": "sunny",

      // characters
      "characters": [
        {
          "name": "girl",
          "traits": ["small", "smiling"],
          "visual": {
            "hair": "brown curly hair",
            "clothes": "striped shirt and purple skirt"
          }
        }
      ],

      // salient motifs and colors
      "objects": [
        { "name": "big_sun", "colors": ["yellow", "orange"] },
        { "name": "small_house", "colors": ["red", "brown"] },
        { "name": "tree", "colors": ["green", "brown"] }
      ]

    }
  },

  // provenance / generation record
  "provenance": {
    "assets": [
      {
        "asset_id": "child_drawing_001",
        "uri": "shared/.../child_drawing_001.png"
      }
    ],
    "generator": {
      "system": "ollama",
      "model": "...",
    }
  }
}
```

#### 5.2 semantics.text / semantics.visual / semantics.audio (Media-level policy)

- `semantics.text/semantics.visual/semantics.audio` are **MediaSIS-level policies**, inheriting from SceneSIS policies and overriding them when needed.
- Typical fields per modality include:

| Modality | Example fields |
|---|---|
| text | `style`, `language`, `tone`, `point_of_view`, etc. |
| visual | `style`, `composition`, `lighting`, `perspective`, etc. |
| audio | `genre`, `tempo`, `instruments`, `mood`, etc. |

---

## 6. Use Cases

### A. Typical use cases inside GeNarrative

- **Children’s drawings → SIS extraction:** Extract meaning from an image into SIS, then generate a story and BGM from it.

### B. Cataloging existing content

- Automatically extract SIS from commercial picture books or public-domain texts to enable semantic labeling for “picture-book recommendations” or “BGM search for a scene”.

### C. Education / research

- Run comparison experiments such as “change only images” or “change only BGM” under the same SIS, to study effects on learning.

### D. Connection to evaluation protocols

- Treat SIS as “ground-truth semantic structure” and measure how closely generated content matches SIS for quantitative evaluation.

----

## 7. Recommended Generation Workflow

1. Generate SceneSIS
   - Extract SceneSIS from existing assets (image/text).
2. Generate the Scene
   - Generate the remaining modalities (text/visual/audio/music) not present in the source asset, and produce a complete Scene.
   - Use meta-prompts to generate modality-specific prompts as needed.
3. Generate StorySIS
   - Choose `story_type` and generate StorySIS including `scene_blueprints`.
   - In SIS UI or via `/api/sis2sis/scene2story`, you can provide `story_type` (three-act / kishotenketsu / attempts / catalog / circular) to fix the structure without relying on LLM inference (if blank, it may be inferred).
   - If you also specify each SceneSIS’s corresponding `scene_type` (setup / ki / intro, etc.) via UI dropdown or `scene_type_overrides`, the generated `scene_blueprints[]` will reliably inherit those labels.
4. Generate remaining SceneSIS
   - Generate the remaining SceneSIS objects from `scene_blueprints`.
5. Generate remaining Scenes
   - Generate the remaining Scenes from the remaining SceneSIS.

----

## 8. Related Concepts (Inspirations)

SIS is an original specification, but shares design ideas with the following concepts.
These are for analogy only; SIS does not guarantee compliance or compatibility.

### OpenUSD (Separating scene description and rendering)

OpenUSD separates “scene description as an editable artifact” from “output steps (rendering)”, enabling swapping, composition, and reuse.
SIS extends this idea beyond 3D to multimodal creation (story/image/audio), treating “meaning” as an editable intermediate representation.

### W3C PROV (Provenance model)

SIS `provenance` holds information about “what inputs and generation settings produced this”, including assets and generators.
This aligns with W3C PROV (Entity / Activity / Agent) as a general provenance model, and is useful as a reference for future extension/interoperability.

### JSON Schema (Validation for editable JSON)

Since SIS assumes human editing, schema-based validation (required fields, types, enums) can reduce breakage and spelling/format drift.
JSON Schema can also serve as a foundation for schema evolution (backward compatibility) and tooling (form UI generation).

---

## 9. Comparison with Other Approaches (Reference)

SIS is positioned as an “intermediate representation for cross-modality coordination”, but similar goals can be achieved with other designs.
Here we summarize typical alternatives and differences.

---

### 9.1 Overview of Each Approach

#### A) SIS (Explicit schema JSON)

- **Overview:** Hold meaning as an **explicit schema (JSON)** connecting image/text/music generation, with optional human editing.
- **Best for:** Iterative improvement (generate → fix → regenerate), diff management, verification, model swapping, explainability.
- **Weakness:** Costs of schema design, conversion (SIS → modality conditions), and operations; may be overkill for “quick and rough” outputs.

#### B) Direct (No intermediate: image/text → LLM → generation)

- **Overview:** Generate captions/instructions from image/text and feed them directly into each modality generator.
- **Best for:** Fast prototypes, demos, one-off generation.
- **Weakness:** Weak reproducibility/diff management/verification; hard to stably tune only the intended attributes; behavior changes easily when models change.

#### C) Natural-language script / story bible

- **Overview:** Use structured prose (world, character settings, scene outlines, mood, etc.) as the intermediate artifact instead of JSON.
- **Best for:** Human readability/editing while retaining creative freedom.
- **Weakness:** Hard to do mechanical validation (type checks), semantic diff interpretation, and reuse/search without additional work.

#### D) Embedding / latent (Vector intermediate)

- **Overview:** Convert assets to embedding vectors and use them for similarity search or conditioning.
- **Best for:** Search/recommendation across large asset collections.
- **Weakness:** Hard for humans to edit; black-box; difficult to “change only this attribute” or verify constraints.

#### E) Graph (Knowledge graph / scene graph)

- **Overview:** Represent relations as nodes/edges (e.g., “Character A holds Object B”, “location is forest”).
- **Best for:** Consistency checks of relationships, dependency management, reasoning/constraints.
- **Weakness:** Design/implementation costs can be high; preserving creative freedom is challenging.

#### F) Existing standards + extensions (e.g., OpenUSD)

- **Overview:** Align to an existing standard (especially scene/asset management) and add required meaning as extended metadata.
- **Best for:** Integration with existing production pipelines and ecosystems.
- **Weakness:** Adoption/operations costs are large; narrative/emotional meaning often still needs a separate layer.

---

### 9.2 Balance Comparison Table (Good / Depends / Hard)

- **Good:** Works well / easy to realize
- **Depends:** Possible with conditions / needs extra design
- **Hard:** Not a good fit / usually needs additional mechanisms

| Approach | Speed (quick “good enough”) | Easy to edit by humans | Reproducibility / diffs | Verification via types/constraints | Robust to model swapping | Less black-box | Search / reuse | Implementation / ops cost | Creative freedom |
|---|---|---|---|---|---|---|---|---|---|
| **SIS (Explicit schema JSON)** | Depends | Good | Good | Good | Good | Good | Good | Depends | Depends |
| Direct (No intermediate) | Good | Hard | Hard | Hard | Depends | Hard | Depends | Good | Good |
| Natural-language story bible | Good | Good | Depends | Hard | Depends | Good | Depends | Good | Good |
| Embedding / latent (Vector) | Depends | Hard | Good | Hard | Hard | Hard | Good | Depends | Depends |
| Graph (Knowledge/scene graph) | Hard | Depends | Good | Good | Good | Good | Good | Hard | Hard |
| Existing standards + extensions (OpenUSD, etc.) | Hard | Depends | Good | Good | Good | Good | Good | Hard | Depends |

---

### 9.3 Operational Guideline: Hybrid of SIS + Natural-language description (Recommended)

In practice, a hybrid of **SIS (skeleton) + description (flesh)** is often easiest to operate.

#### Basic policy

- **Keep SIS minimal and only fix what you want to edit** (necessary and sufficient; keep it small)
- **Move free-form content into `description`** (details, aftertaste, examples, candidate lists, etc.)
- During generation, prioritize **confirmed SIS information**, using `description` as auxiliary context

#### Rule of thumb (what goes into SIS)

- **Put into SIS (want to fix/validate):**
  - Story/scene structure (what you want to validate as a schema)
  - Parameters that strongly affect outputs: characters/setting/era/POV/tone, etc.
  - Prohibitions/constraints (e.g., no violence, for children, banned vocabulary)
  - References that matter for consistency (scene_id references, parent/child relations, mappings)
- **Put into description (keep flexible):**
  - Examples, associations, phrasing candidates, mood additions
  - Items where you want interpretive slack (“like…”, “might be…”) 
  - Model/prompt-dependent details (poetic metaphors, long scenic descriptions)
  - Multiple alternatives (list candidates, etc.)

#### Minimal SIS (example: start with only this)

- StorySIS: `genre / audience / tone / structure / theme / constraints / scenes[]`
- SceneSIS: `scene_id / summary / characters / setting / mood / key_events / constraints`
- MediaSIS: `asset_id / type / purpose / style / constraints / source_refs`

Consider putting everything else into `description` first, then “promote” fields from description to SIS when needed.

## 10. Summary

This specification satisfies:

- Story structures such as Kishotenketsu (StorySIS)
- Consistent management of scene meaning and generation policies (SceneSIS)
- Decomposition into expression units via Media for editing (MediaSIS)
- Optimization for multimodal generation
- Ease of use across UI / LLM / file storage
