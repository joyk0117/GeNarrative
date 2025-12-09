# 🧩 GeNarrative – Semantic Interface Structure (SIS) Specification

## 🎯 1. Overview

Semantic Interface Structure (SIS) is an intermediate representation that **extracts "semantic information of works and scenes" and serves as a "hub" for generation, search, and reuse.**
It separates "what to create (semantics)" from "how to create (models/prompts)" and functions as a common language across all phases of generation, search, and learning.

### Key Benefits

1.  **Module Separation & Controllability**
    *   Semantics (SIS) remain fixed while models (e.g., SD, MusicGen) or parameters can be swapped out.
2.  **Reproducibility & Explainability**
    *   Fully records "what semantic specifications gave birth to this content" in JSON. Serves as a foundation for provenance verification and regeneration.
3.  **Editable "Knobs" & Manual Correction**
    *   Even if LLM extraction is imperfect, the structured data allows for easy manual correction and completion.
    *   Fine-tuning style or tempo is simple just by adjusting the semantics (SIS).
4.  **Common Interface for Search & Recommendation**
    *   Enables semantics-based search and recommendation across text, images, and music (e.g., "melancholy + night + piano").
5.  **Foundation for Training Data & Evaluation**
    *   SIS can be used as ground truth data for prompt generation, QA pair creation, and automated model evaluation (consistency checking).
6.  **Hub for Vector DBs & Other Models**
    *   Elements of SIS can be vectorized to bridge with external DBs or Embedding models.

## 🏗 2. Layer Structure (Story / Scene)

In the scope of GeNarrative, SIS consists of the following two types of objects:

### StorySIS (Upper Layer)

- An object that holds the semantic structure of the entire work.
- Basic story information (title, etc.)
- Story type (Kishotenketsu, Three-act structure, etc.)
- Character settings
- List of scenes and their roles
- Overall style policy (writing style, art style, music policy)

### SceneSIS (Lower Layer)

- An object representing the **minimum semantic unit (1 scene)** that makes up the work.
- Scene semantics (summary, emotions, etc.)
- Text generation parameters
- Visual generation parameters (image/video)
- Audio generation parameters (music/speech/sfx)
- SceneSIS is saved as a JSONL file (1 JSON per line).
- **For reusability, SceneSIS does not include `story_id` (the same scene can be reused in multiple stories).**

## 📘 3. StorySIS Specification

### 3.1 StorySIS – JSON Schema (Conceptual)

```jsonc
{
  "sis_type": "story",
  "story_id": "string",
  "title": "string or null",
  "summary": "string or null",

  // Story Structure Type (Required)
  "story_type": "kishotenketsu", 
  // e.g.: "kishotenketsu" | "three_act" | "three_attempts" | "circular"

  // Themes of the work
  "themes": ["trust", "learning"],

  // Characters
  "characters": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Nancy",
      "traits": ["girl", "curious"],
      "visual": {
        "hair": "brown curly hair",
        "clothes": "striped shirt and purple skirt"
      }
    }
  ],

  // List of Scenes (Also serves as structural info)
  "scenes": [
    {
      "scene_id": "123e4567-e89b-12d3-a456-426614174000",
      "role": "ki",       // Introduction (Ki)
      "summary": "Introduction of the girl and the forest."
    }
  ]
}
```

### 3.2 Field Details

| Field                 | Type   | Description                                            |
|-----------------------|--------|--------------------------------------------------------|
| story_type            | string | Type of story structure (e.g., Kishotenketsu)          |
| themes                | array  | Themes of the entire work                              |
| scenes[].role         | string | Role of the scene (e.g., ki/sho/ten/ketsu)             |
| characters[]          | array  | Character traits and visual information                |


### 3.3 Standard Values for story_type

| story_type       | roles (scene.role)                                  |
|------------------|-----------------------------------------------------|
| kishotenketsu    | ki / sho / ten / ketsu                              |
| three_act        | setup / conflict / resolution                       |
| three_attempts   | problem / attempt1 / attempt2 / attempt3 / result   |
| circular         | home_start / away / change / home_end               |

## 🎬 4. SceneSIS Specification

SceneSIS is a JSON object describing a single scene.
Saving in JSONL (1 Scene per line) is recommended.

### 4.1 SceneSIS – JSON Schema (Conceptual)

```jsonc
{
  "sis_type": "scene",
  // Matches StorySIS
  "scene_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "ki",       // Introduction (Ki)
  "summary": "Introduction of the girl and the forest.",
  
  // Scene Semantics (Common across modalities)
  "semantics": {
    "mood": "calm",
    "characters": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Nancy",
        "visual": { "clothes": "raincoat" }
      }
    ],
    "location": "forest",
    "time": "day",
    "weather": "sunny"
  },

  // Text Generation
  "text": {
    "mode": "narrative",   // narrative/expository/dialogue/caption/question
    "style": "simple",
    "language": "English",
    "tone": "gentle",
    "point_of_view": "third"
  },

  // Visual Generation (Image/Video)
  "visual": {
    "mode": "image",       // image | video
    "style": "watercolor",
    "composition": "mid-shot",
    "lighting": "soft",
    "perspective": "eye-level"
  },

  // Audio Generation (Music/Speech/SFX)
  "audio": {
    "mode": "music",       // music | speech | sfx | ambience
    "genre": "ambient",
    "tempo": "slow",
    "instruments": ["piano", "pad"]
  }
}
```

### 4.2 Field Details

#### 4.2.1 Common Fields

| Field      | Description    |
|------------|----------------|
| summary    | Scene summary  |
| mood       | Atmosphere/Mood|
| themes     | Themes         |

#### 4.2.2 semantics (Scene Semantic Information)

"Semantic background" referenced by image, text, and sound.

| Field        | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| characters   | List of detailed character info for the scene (ID, name, visuals, etc.). Can describe scene-specific clothing. |
| location     | Location name                                                               |
| time         | Time of day                                                                 |
| weather      | Weather                                                                     |

#### 4.2.3 text (Text Generation)

| Field           | Description                            |
|-----------------|----------------------------------------|
| mode            | narrative / expository / dialogue, etc.|
| style           | Writing style                          |
| tone            | Tone of the text                       |
| point_of_view   | First-person / Third-person, etc.      |

#### 4.2.4 visual (Image/Video Generation)

| Field        | Description                           |
|--------------|---------------------------------------|
| mode         | image or video                        |
| style        | watercolor, anime, realistic, etc.    |
| composition  | Composition                           |
| lighting     | Lighting/Atmosphere                   |
| perspective  | Perspective                           |

#### 4.2.5 audio (Music/Speech/SFX)

| Field        | Description                           |
|--------------|---------------------------------------|
| mode         | music / speech / sfx / ambience       |
| genre        | Music genre                           |
| tempo        | Speed/Tempo                           |
| instruments  | List of instruments                   |

## 🔗 5. Relationship between StorySIS and SceneSIS

```
StorySIS
 ├── scenes[0] → SceneSIS(scene_001)
 ├── scenes[1] → SceneSIS(scene_002)
 ├── scenes[2] → SceneSIS(scene_003)
 ...
```

## 🚀 6. Use Cases

### A. Typical Use Cases in GeNarrative
*   **Child's Drawing → SIS Extraction:** Extract semantics from an image to create an SIS, then generate a story and BGM from it.
*   **SIS DB:** Save generated SIS to serve as a foundation for reusing "works with similar atmosphere" or "sequels".

### B. Cataloging Existing Content
*   Automatically extract SIS from commercial picture books or public domain works (e.g., Aozora Bunko) to use for semantic labeling like "picture book recommendations" or "BGM search matching a scene".

### C. Education & Research
*   Use the same SIS to conduct experiments changing "only the image" or "only the BGM" to verify the impact on learning effects.

### D. Connection with Evaluation Protocols
*   Use SIS as the "ground truth semantic structure" and measure how much the generated content matches the SIS for quantitative model evaluation.

## 🛠 7. Storage Format

- StorySIS: `story.json`
- SceneSIS: `story_scenes.jsonl (1 Scene per line)`

## 🧪 8. LLM Generation Workflow (Recommended)

1. Generate StorySIS (Determine roles according to story_type)
2. Generate SceneSIS one by one based on scenes[].scene_id
3. Save SceneSIS to JSONL
4. Convert SceneSIS → Text/Image/Music/Video

## 🎉 9. Summary

This specification fully satisfies:

- Story structures like Kishotenketsu
- Consistent management of Scene semantics + generation conditions
- Optimization for multi-modal generation
- Clarity across UI/LLM/File storage
