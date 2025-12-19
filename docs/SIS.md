# 🧩 GeNarrative – Semantic Interface Structure (SIS) Specification

## 🎯 1. Overview

Semantic Interface Structure (SIS) is an intermediate representation that **extracts “semantic information of a work or a scene” and makes it a hub for generation, search, and reuse**.
It separates **what to create (meaning)** from **how to create it (models/prompts)**, and functions as a common language across all phases: generation, retrieval, and learning.

### Key benefits

1. **Modularity & controllability**
   - You can keep the meaning (SIS) fixed and swap only the model (e.g., SD/MusicGen) or parameters.
2. **Reproducibility & explainability**
   - Records “what semantic specification produced this” in JSON. This becomes the basis for provenance checks and regeneration.
3. **Editable parameters & manual correction**
   - Even if LLM extraction is imperfect, the data is structured, so humans can fix and augment it.
4. **A common interface for search & recommendation**
   - Enables meaning-based search/recommendation such as “melancholic + night + piano”.
5. **A foundation for training data & evaluation**
   - SIS can be used as ground-truth for prompt generation, QA creation, and model evaluation (consistency checks).
6. **A hub for vector DBs and other models**
   - Each SIS element can be vectorized to bridge to external DBs or embedding models.

---

## 🏗 2. Layer structure (three layers: Story / Scene / Media)

Within the scope of GeNarrative, SIS consists of the following three types of objects.

### StorySIS (top layer: the whole work)

- An object that holds the semantic structure of the entire work.
- Story type (e.g., Kishōtenketsu, three-act structure)
- Global themes and character settings
- Overall style policies (writing style, visual style, music policy)

### SceneSIS (middle layer: unit of meaning)

- An object representing the **smallest semantic unit (one scene)** that makes up a work.
- Scene meaning (`summary` / `semantics`)
- Scene-level generation policies (`text` / `visual` / `audio`)
  - For reusability, SceneSIS does not include `story_id` (so the same Scene can be reused across multiple Stories).

### MediaSIS (bottom layer: unit of expression)

- An object that further decomposes a SceneSIS into **“scene components (expression units)”**.
- Examples: shots (composition), dialogue, narration, subtitles, sound effects, BGM segments, props/objects, etc.

#### Connections between layers and external indices

- The links between StorySIS, SceneSIS, and MediaSIS (the mapping among `story_id`, `scene_id`, and `media_id`) are not stored directly inside each SIS JSON; instead, they are managed as an external index.
- This allows a single SceneSIS/MediaSIS to be reused by multiple StorySIS objects (reusability), and also makes updates robust by swapping only relationships without editing the Story/Scene/Media objects themselves.
- Concretely, the mapping is expected to be stored in a graph structure (graph DB) or relationship tables in a relational DB.

---

## 📘 3. StorySIS Specification

### 3.1 StorySIS – JSON schema (conceptual)

```jsonc
{
  "sis_type": "story",
  "story_id": "123e4567-e89b-12d3-a456-426614174000",

  "title": "The Girl and the Forest",
  "summary": "A curious girl explores a mysterious forest.",
  "story_type": "kishotenketsu", // e.g.: "kishotenketsu" | "three_act" | "attempts" | "circular" | "catalog"

  // Semantic structure of the whole work (themes / style policies)
  "semantics": {
    // Common semantic information for the whole work
    "common": {
      "themes": ["trust", "learning"],
      "descriptions": [
        "A gentle story about a girl learning to trust the forest and herself.",
        "Focuses on emotional growth rather than fast-paced action."
      ]
    },

    // Overall style policies (optional)
    "text":  {"language": "English", "tone": "gentle", "point_of_view": "third"},
    "visual": {"style": "watercolor"},
    "audio": {"genre": "ambient"}
  },

}
```

### 3.2 Field details (excerpt)

| Field | Type | Description |
|---|---|---|
| story_type | string | The type of story structure (e.g., Kishōtenketsu) |
| semantics.common.themes | array | Global themes of the work |
| semantics.common.descriptions | array | Supplementary descriptions of the whole work (nuances/intent not fully covered by `summary`) |
| semantics.text / semantics.visual / semantics.audio | object | Global style policies of the work (can be overridden on SceneSIS / MediaSIS) |

### 3.3 Standard values for `story_type`

Representative patterns and their correspondence to `SceneSIS.scene_type` are as follows.

| story_type | Overview | scene_type (SceneSIS.scene_type) |
|---|---|---|
| three_act | Drama pattern (difficulty → resolution) | setup / conflict / resolution |
| kishotenketsu | Twist/“punchline” pattern (meaning flips at the end) | ki / sho / ten / ketsu |
| circular | Journey-and-return pattern (leave → change → return) | home_start / away / change / home_end |
| attempts | Multiple-attempts pattern (trial and error) | problem / attempt (repeated) / result |
| catalog | Catalog/introduction pattern (weak ordering) | intro / entry (repeated) / outro |

---

## 🎬 4. SceneSIS Specification

SceneSIS is a JSON object that describes one scene.
Both **JSON and JSONL** are supported formats, but when handling many scenes, **JSONL (one Scene per line)** is recommended.

The JSON schema examples below are **JSONC (JSON with comments)** for explanation. For actual files, use plain JSON/JSONL without comments.

### 4.1 SceneSIS – JSON schema (conceptual)

```jsonc
{
  "sis_type": "scene",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",

  "summary": "Introduction of the girl and the forest.",
  "scene_type": "ki",

  // Scene meaning + generation policy (shared background across modalities)
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
      // Salient motifs and colors (easy to attach meaning)
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

    // Semantic info per modality
    "text": { "style": "simple", "language": "English", "tone": "gentle", "point_of_view": "third" },
    "visual": { "style": "watercolor", "composition": "mid-shot", "lighting": "soft", "perspective": "eye-level" },
    "audio": { "genre": "ambient", "tempo": "slow", "instruments": ["piano", "pad"] }
  },

}
```

### 4.2 Field details (excerpt)

#### 4.2.1 `semantics` (scene semantic information)

The “semantic background” referenced by image/text/audio. `semantics.common` contains fields such as:

| Field | Description |
|---|---|
| characters | Character details appearing in the scene (ID, name, appearance, etc.). Scene-specific outfits can be described. |
| location | Location name |
| time | Time of day |
| weather | Weather |
| mood | Atmosphere / mood |
| objects | Important objects in the scene, including salient motifs and colors |
| descriptions | Text notes such as intent/nuance/interpretation memos that cannot be fully expressed in `summary` (multiple allowed) |

#### 4.2.2 `semantics.text` / `semantics.visual` / `semantics.audio` (Scene-level policies)

- `semantics.text/semantics.visual/semantics.audio` are **Scene-level default policies**.

---

## 🧩 5. MediaSIS Specification

MediaSIS decomposes a SceneSIS into “components (expression units)”.
By aligning generation/editing/output to the MediaSIS unit, both coarse and fine-grained scenes can be handled within the same framework.

### 5.1 MediaSIS – JSON schema (conceptual)

The following is a **sample MediaSIS extracted from an image (visual)**; it does not include text/audio elements.

```jsonc
{
  "sis_type": "media",
  "media_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",

  // The type of component and which modality it belongs to (this example is visual)
  // A short summary of this Media element
  "summary": "a happy scene in a park with a big sun and a small house",

  // The type of component and which modality it belongs to (this example is visual)
  "media_type": "visual",

  // Semantic structure (extraction target)
  "semantics": {
    "common": {
      // Overall mood
      "mood": "happy",
      // Semantic info / interpretation memos that are hard to split by summary/description (multiple allowed)
      "descriptions": [
        "The drawing conveys a strong sense of safety and warmth between the two figures.",
        "Colors are intentionally vivid to reflect a child's joyful perception of the world."
      ],

      "location": "park",
      "time": "day",
      "weather": "sunny",

      // Characters
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

      // Salient motifs and colors
      "objects": [
        { "name": "big_sun", "colors": ["yellow", "orange"] },
        { "name": "small_house", "colors": ["red", "brown"] },
        { "name": "tree", "colors": ["green", "brown"] }
      ]

    }
  },

  // Provenance / generation record
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

#### 5.2 `semantics.text` / `semantics.visual` / `semantics.audio` (Media-level policies)

- `semantics.text/semantics.visual/semantics.audio` are **MediaSIS-level policies**, inheriting the SceneSIS policies and overriding them as needed.
- Typical example fields per modality are:

| Modality | Example fields |
|---|---|
| text | `style` (writing style), `language`, `tone`, `point_of_view`, etc. |
| visual | `style` (art style), `composition`, `lighting`, `perspective`, etc. |
| audio | `genre`, `tempo`, `instruments`, `mood`, etc. |

## 🚀 6. Use Cases

### A. Typical use cases within GeNarrative
- **Children's drawings → SIS extraction:** Extract semantics from an image into SIS, then generate story and BGM from it.

### B. Cataloging existing content
- Automatically extract SIS from commercial picture books or public-domain works, and use it for semantic labeling such as “picture-book recommendation” or “BGM search that fits a scene”.

### C. Education / research
- Use the same SIS to run comparative experiments such as “change only the image” or “change only the BGM”, and use it as a basis for studying impacts on learning outcomes.

### D. Connecting to evaluation protocols
- Treat SIS as “ground-truth semantic structure” and measure how well generated content matches SIS, enabling quantitative model evaluation.

----

## 🛠 7. Storage formats

- StorySIS: `story.json` (a JSON containing a single StorySIS object)
- SceneSIS: `story_scenes.json` / `story_scenes.jsonl` (for multiple SceneSIS objects, either JSON or JSONL is fine)
- MediaSIS: `story_media.json` / `story_media.jsonl` (for multiple MediaSIS objects, either JSON or JSONL is fine)

As a rule, the mapping among StorySIS/SceneSIS/MediaSIS (`story_id`, `scene_id`, `media_id`) should be managed as an **external index** (e.g., another file or a database), rather than embedded in the SIS objects.

----

## 🧪 8. Recommended LLM generation workflow

1. Prepare MediaSIS (optional)
   - Create from existing assets (images/text/audio), or create manually
2. Generate SceneSIS
   - Define the Scene's semantic background (`semantics.common`) and modality-specific policies (`semantics.text/visual/audio`)
   - Generate MediaSIS for needed modalities (text/visual/audio), and manage the mapping between `scene_id` and `media_id` in an external index (e.g., a DB or separate JSON)
3. Generate StorySIS
   - Decide `scene_type` according to `story_type`, and manage Story ↔ Scene mappings in an external index

----

## 🔗 9. Inspirations / related concepts

SIS is an original specification, but its design philosophy shares similarities with the following existing concepts.
Note: these are **references (analogies)**; SIS does not guarantee compliance or compatibility with them.

### OpenUSD (separating scene description ↔ rendering)

OpenUSD separates “scene description as an editable artifact” from “the output process (rendering)” in 3D production, enabling easy swapping, composition, and reuse.
SIS extends this idea beyond 3D to multimodal creation such as stories, images, and audio, aiming to treat “meaning” as an editable intermediate representation.

### W3C PROV (a model for provenance / generation history)

SIS `provenance` is an area for recording “what inputs and what generation conditions produced this”, such as assets and generators.
This aligns well with the general provenance model W3C PROV (Entity / Activity / Agent) and can be a reference for future extensions and interoperability.

### JSON Schema (validation for editable JSON)

Because SIS assumes manual editing, introducing schema-based validation (required fields, types, enums, etc.) helps reduce corruption and inconsistency.
JSON Schema can be a foundation for future SIS schema evolution (backward compatibility) and tool integration (e.g., form-based UI generation).

## 🧭 10. Comparison with alternatives (reference)

SIS is positioned as an “intermediate representation for connecting modalities,” but similar goals can be achieved with other designs.
This section summarizes representative alternatives and how they differ from SIS.

---

### 10.1 Overview of approaches

#### A) SIS (explicit schema JSON)
- **Overview**: Store semantic information as an **explicit schema (JSON)** that can be edited by humans when needed, and use it to connect image/text/audio generation.
- **Good for**: Iterative improvement (generate → edit → regenerate), diff/versioning, validation, model swapping, and explainability.
- **Weakness**: Schema design, transformations (SIS → modality-specific conditions), and operations can add overhead. For a quick “good-enough” output, it may be too heavy.

#### B) Direct piping (no intermediate)
- **Overview**: Create captions/instructions from images or text, then pass them directly into each modality generator (text/image/music). The intermediate artifact is not fixed.
- **Good for**: Fast prototypes, demos, and one-off personal use.
- **Weakness**: Weak reproducibility/diffability/validation; harder to stably adjust only intended attributes. Behavior changes more easily when the model changes.

#### C) Natural-language script / story bible
- **Overview**: Use a structured document (world, characters, scene summaries, mood, etc.) as the intermediate artifact instead of schema JSON.
- **Good for**: Human-readable editing while preserving creative freedom.
- **Weakness**: Hard to mechanically validate (type checks), interpret diffs semantically, and build search/reuse without extra work.

#### D) Embedding / latent (vector intermediate)
- **Overview**: Convert images/audio into embedding vectors and use them for similarity search or conditioning (the intermediate representation is a vector).
- **Good for**: Search/recommendation over large asset libraries; reuse by similarity.
- **Weakness**: Hard for humans to edit; tends to be black-box. Validation and “change only this attribute” are difficult.

#### E) Graph (knowledge graph / scene graph)
- **Overview**: Represent relationships like “Character A holds Object B” and “location is forest” as nodes/edges.
- **Good for**: Consistency checks of relationships, dependency management, inference, and constraints.
- **Weakness**: Design/implementation costs can be high. Preserving creative freedom requires careful modeling.

#### F) Existing standards + extension (e.g., OpenUSD)
- **Overview**: Align with an existing standard format (especially for scene/asset management) and store additional meaning as extension metadata.
- **Good for**: Integration with existing production/asset pipelines and leveraging ecosystem tooling.
- **Weakness**: Adoption/operations costs are large; narrative/emotion semantics often still require another layer.

---

### 10.2 Balance table (〇/△/×)

- **〇**: Strong / easy to realize as-is
- **△**: Depends / achievable with additional design
- **×**: Weak / often needs another mechanism

| Approach | Startup speed (quick “good-enough”) | Human-editable | Reproducibility / diffs | Type/constraint validation | Robust to model swapping | Less black-box | Search / reuse | Implementation / ops cost | Creative freedom |
|---|---|---|---|---|---|---|---|---|---|
| **SIS (explicit schema JSON)** | △ | 〇 | 〇 | 〇 | 〇 | 〇 | 〇 | △ | △ |
| Direct piping (no intermediate) | 〇 | × | × | × | △ | × | △ | 〇 | 〇 |
| Natural-language script / story bible | 〇 | 〇 | △ | × | △ | 〇 | △ | 〇 | 〇 |
| Embedding / latent (vector intermediate) | △ | × | 〇 | × | × | × | 〇 | △ | △ |
| Graph (knowledge graph / scene graph) | × | △ | 〇 | 〇 | 〇 | 〇 | 〇 | × | × |
| Existing standards + extension (OpenUSD etc.) | × | △ | 〇 | 〇 | 〇 | 〇 | 〇 | × | △ |

---

### 10.3 Operational guideline: SIS + natural-language descriptions (recommended)

In practice, a hybrid approach of **SIS (skeleton) + descriptions (flesh)** is often the easiest to operate.

#### Basic policy
- Keep SIS **small and focused**: fix only the minimum elements you want to edit and validate.
- Put freer content into `descriptions`: details, aftertaste, examples, candidate lists, etc.
- During generation, prioritize **confirmed SIS fields**; treat `descriptions` as supportive context.

#### What to put into SIS vs descriptions
- **Put into SIS (things you want to fix/validate)**
  - Story/scene structure (things you want to validate as types)
  - Characters/locations/era/POV/tone—parameters that change the whole output
  - Prohibitions/constraints (e.g., no violence, for children, forbidden vocabulary)
  - References related to consistency (e.g., mappings like `scene_id` references, parent-child relationships)
- **Put into `descriptions` (keep flexible)**
  - Concrete examples, associations, phrasing candidates, mood supplements
  - Elements you want to leave room for interpretation (“like…”, “maybe…”) 
  - Details that are highly model/prompt-dependent (poetic expressions, metaphors, long scenery)
  - Multiple alternatives you want to keep (e.g., list candidates)

#### Minimal SIS (example: start with this)
- StorySIS: `genre / audience / tone / structure / theme / constraints / scenes[]`
- SceneSIS: `scene_id / summary / characters / setting / mood / key_events / constraints`
- MediaSIS: `asset_id / type / purpose / style / constraints / source_refs`

If needed, promote items gradually from `descriptions` into explicit SIS fields (description → SIS field).

## 🎉 11. Summary

This specification provides:

- Story structures such as Kishōtenketsu (StorySIS)
- Consistent management of Scene meaning + generation policies (SceneSIS)
- Decomposition into expression units with Media (MediaSIS)
- Optimization for multimodal generation
- Usability across UI / LLM / file storage
