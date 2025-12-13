# 🧩 GeNarrative – Semantic Interface Structure (SIS) Specification

## 🎯 1. Overview

Semantic Interface Structure (SIS) is an **intermediate representation that captures the “semantic information of a work or scene” and serves as a hub for generation, search, and reuse**.
It separates **“what to create (semantics)”** from **“how to create it (models / prompts)”**, and acts as a common language across all phases of generation, retrieval, and evaluation.

### Main Advantages

1. **Modularization & Controllability**
   - Keep semantics (SIS) fixed while swapping only models (e.g., SD / MusicGen) or parameters.
2. **Reproducibility & Explainability**
   - Record “what semantic specification led to the output” as JSON. This becomes the basis for provenance tracking and regeneration.
3. **Editable Parameters & Human Correction**
   - Even if LLM-based extraction is imperfect, SIS is structured data, so humans can easily correct and supplement it.
4. **Semantic-Based Search & Recommendation**
   - Enables semantic queries like “melancholic + night + piano” for search and recommendation.
5. **Basis for Training Data & Evaluation**
   - Use SIS as ground truth to support prompt generation, QA construction, and model evaluation (semantic consistency checking).
6. **Hub for Vector DBs and Other Models**
   - Vectorize each SIS element to bridge with external DBs and embedding models.

---

## 🏗 2. Layered Structure (Story / Scene / Media)

Within the scope of GeNarrative, SIS is composed of the following three types of objects:

### StorySIS (Top Level: Whole Work)

- Holds the semantic structure of the entire work.
- Story structure type (e.g., Kishōtenketsu, three-act, etc.)
- Global themes and character settings
- Global style policy for the work (writing style, visual style, audio policy)

### SceneSIS (Middle Level: Semantic Unit)

- Represents the **minimum semantic unit (one scene)** that composes a work.
- Scene semantics (summary / semantics)
- Scene-level generation policy (text / visual / audio)
  - For reusability, SceneSIS does **not** include `story_id` (the same Scene can be reused across multiple Stories).

### MediaSIS (Lower Level: Expression Unit)

- Represents **“scene components (expression units)”** that further decompose the inside of a SceneSIS.
- Examples: shots (composition), dialogue, narration, subtitles, sound effects, BGM segments, objects, etc.

#### Connections Between Layers and External Index

- The links between StorySIS, SceneSIS, and MediaSIS (the correspondences of `story_id`, `scene_id`, and `media_id`) are **not stored directly inside each SIS JSON**, but managed as **external indexes**.
- This allows a single SceneSIS / MediaSIS to be reused from multiple StorySIS instances (reusability). Also, updating only the relationships (without modifying Story / Scene / Media bodies) makes the system more robust to change.
- Concretely, we assume saving the correspondences among Story / Scene / Media in graph structures (graph databases) or relationship tables in relational databases.

---

## 📘 3. StorySIS Specification

### 3.1 StorySIS – JSON Schema (Conceptual)

```jsonc
{
  "sis_type": "story",
  "story_id": "123e4567-e89b-12d3-a456-426614174000",

  "title": "The Girl and the Forest",
  "summary": "A curious girl explores a mysterious forest.",
  "story_type": "kishotenketsu", // e.g., "kishotenketsu" | "three_act" | "attempts" | "circular" | "catalog"

  // Global semantic structure of the work (themes, style policy)
  "semantics": {
    // Global semantic information shared across the work
    "common": {
      "themes": ["trust", "learning"],
      "descriptions": [
        "A gentle story about a girl learning to trust the forest and herself.",
        "Focuses on emotional growth rather than fast-paced action."
      ]
    },

    // Optional: global style policies of the work
    "text":  {"language": "English", "tone": "gentle", "point_of_view": "third"},
    "visual": {"style": "watercolor"},
    "audio": {"genre": "ambient"}
  }
}
```

### 3.2 Field Details (Excerpt)

| Field | Type | Description |
|---|---|---|
| story_type | string | Type of story structure (e.g., Kishōtenketsu) |
| semantics.common.themes | array | Global themes of the work |
| semantics.common.descriptions | array | Additional explanations of the work (nuances or intentions not fully captured by summary) |
| semantics.text / semantics.visual / semantics.audio | object | Global style policies of the work (can be overridden by SceneSIS / MediaSIS) |

### 3.3 Standard Values of story_type

Representative patterns and the correspondence with `SceneSIS.scene_type` are as follows:

| story_type | Overview | scene_type (SceneSIS.scene_type) |
|---|---|---|
| three_act | Drama type (difficulty → resolution) | setup / conflict / resolution |
| kishotenketsu | Twist / punchline type (meaning reverses at the end) | ki / sho / ten / ketsu |
| circular | Journey-and-return type (go out, change, and come back) | home_start / away / change / home_end |
| attempts | Multiple-attempts type (trial and error) | problem / attempt (repeated) / result |
| catalog | Catalog / introduction type (weak ordering) | intro / entry (repeated) / outro |

---

## 🎬 4. SceneSIS Specification

SceneSIS is a JSON object that describes one scene.
The storage format can be **JSON or JSONL**, but when handling many scenes, **JSONL (one Scene per line)** is recommended.

The following JSON schema is a conceptual **JSONC (JSON with comments)** for explanation. In actual files, please store plain JSON / JSONL without comments.

### 4.1 SceneSIS – JSON Schema (Conceptual)

```jsonc
{
  "sis_type": "scene",
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",

  "summary": "Introduction of the girl and the forest.",
  "scene_type": "ki",

  // Semantics of the scene + generation policies (background shared across modalities)
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
      // Salient motifs and colors (elements that are easy to semantically ground)
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

    // Semantic information for each modality
    "text":   { "style": "simple", "language": "English", "tone": "gentle", "point_of_view": "third" },
    "visual": { "style": "watercolor", "composition": "mid-shot", "lighting": "soft", "perspective": "eye-level" },
    "audio":  { "genre": "ambient", "tempo": "slow", "instruments": ["piano", "pad"] }
  }
}
```

### 4.2 Field Details (Excerpt)

#### 4.2.1 semantics (Scene Semantics)

This is the “semantic background” referenced by all modalities: image, text, and audio.
`semantics.common` may have the following fields:

| Field | Description |
|---|---|
| characters | Detailed info on characters appearing in the scene (ID, name, appearance, etc.). Scene-specific outfits can be described. |
| location | Location name |
| time | Time of day |
| weather | Weather |
| mood | Atmosphere of the scene |
| objects | Salient motifs and colors; important objects in the scene |
| descriptions | Textual notes such as scene intentions, nuances, or interpretations not fully captured by summary (can hold multiple entries) |

#### 4.2.2 semantics.text / semantics.visual / semantics.audio (Scene-Level Policies)

- `semantics.text`, `semantics.visual`, and `semantics.audio` are **scene-level default policies**.
- The **final unit for generation, editing, and output is MediaSIS** (Media elements inherit and optionally override these policies).

---

## 🧩 5. MediaSIS Specification

MediaSIS is the “component (expression unit)” obtained by decomposing the inside of a SceneSIS.
By using MediaSIS as the final unit of generation, editing, and output, both coarse-grained and fine-grained scenes can be handled within the same framework.

### 5.1 MediaSIS – JSON Schema (Conceptual)

The following is a **sample MediaSIS extracted from an image (visual)** and does not include text or audio elements.

```jsonc
{
  "sis_type": "media",
  "media_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",

  // A short summary of this media element as a whole
  "summary": "a happy scene in a park with a big sun and a small house",
  
  // Type of component and which modality it belongs to (image in this example)
  "media_type": "visual",

  // Semantic structure (extraction target)
  "semantics": {
    "common": {
      // Overall atmosphere
      "mood": "happy",
      // Semantic information and interpretation notes that are hard to divide into summary / description (can have multiple entries)
      "descriptions": [
        "The drawing conveys a strong sense of safety and warmth between the two figures.",
        "Colors are intentionally vivid to reflect a child's joyful perception of the world."
      ],

      "location": "park",
      "time": "day",
      "weather": "sunny",

      // Characters appearing in the media
      "characters": [
        {
          "name": "girl",
          "traits": ["small", "smiling"],
          "visual": {
            "style_hint": "simple_stick_figure",
            "colors": ["pink", "yellow"]
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

  // Provenance and generation record
  "provenance": {
    "assets": [
      {
        "asset_id": "child_drawing_001",
        "uri": "shared/.../child_drawing_001.png"
      }
    ],
    "generator": {
      "system": "ollama",
      "model": "..."
    }
  }
}
```

#### 5.2 semantics.text / semantics.visual / semantics.audio (Media-Level Policies)

- `semantics.text`, `semantics.visual`, and `semantics.audio` at MediaSIS level hold **media-level policies** that inherit and optionally override the SceneSIS policies.
- Typical modality-specific fields include:

| Modality | Example Fields |
|---|---|
| text | `style` (writing style), `language`, `tone`, `point_of_view`, etc. |
| visual | `style` (art style), `composition`, `lighting`, `perspective`, etc. |
| audio | `genre`, `tempo`, `instruments`, `mood`, etc. |

## 🚀 6. Use Cases

### A. Typical Use Cases in GeNarrative
- **Child drawing → SIS extraction:** Extract semantics from an image, convert it to SIS, and then generate stories and BGM from it.

### B. Cataloging Existing Content
- Automatically extract SIS from commercial picture books or public-domain texts (e.g., Aozora Bunko), and use it for semantic labeling such as “picture book recommendation” or “searching for BGM that fits the scene”.

### C. Education and Research
- Use the same SIS while changing “only the image” or “only the BGM” to perform controlled experiments and evaluate effects on learning.

### D. Connection to Evaluation Protocols
- Use SIS as the “ground-truth semantic structure” and measure how well generated content aligns with SIS to quantitatively evaluate models.

----

## 🛠 7. Storage Formats

- StorySIS: `story.json` (JSON file that stores a single StorySIS object)
- SceneSIS: `story_scenes.json` / `story_scenes.jsonl` (for multiple SceneSIS objects, use JSON or JSONL)
- MediaSIS: `story_media.json` / `story_media.jsonl` (for multiple MediaSIS objects, use JSON or JSONL)

The links among StorySIS / SceneSIS / MediaSIS (correspondences between `story_id`, `scene_id`, and `media_id`) are basically managed in **external indexes** such as separate files or databases.

----

## 🧪 8. Recommended LLM-Based Workflow

1. Generate StorySIS (decide `scene_type` according to `story_type`).
2. Based on the list of `scene_id` / `scene_type` in the external index, generate SceneSIS one by one.
3. For each SceneSIS, generate MediaSIS for required modalities (text / visual / audio), and manage the correspondence between `scene_id` and `media_id` in an external index (e.g., DB or separate JSON).
4. Save SceneSIS / MediaSIS as JSON / JSONL (when handling many records, JSONL is recommended).
5. Convert SceneSIS (policies) + MediaSIS (elements) into text / images / music / video.

----

## 🎉 9. Summary

This specification supports:

- Story structures such as Kishōtenketsu (StorySIS)
- Unified management of scene semantics and generation policies (SceneSIS)
- Decomposition into expression units via Media and subsequent editing (MediaSIS)
- Optimization for multimodal generation
- Easy handling from UI / LLM / file storage perspectives
