# StorySIS → SceneSIS Prompt

Generate a complete SceneSIS JSON object based on the provided story context and scene blueprint.

## Story Context
${STORY_CONTEXT_JSON}

## Scene Blueprint (#${BLUEPRINT_INDEX})
${BLUEPRINT_JSON}

## Story Type Guide
${STORY_TYPE_GUIDE}

## Task
1. **Concrete and specific content**: Use the blueprint's scene_type and summary as a starting point to create SPECIFIC content for this scene.
2. **Create concise descriptions**: Generate clear and effective descriptions. Focus on specific visual elements and actions rather than lengthy prose.
3. Inherit style policies from the story's semantics
4. Provide rich semantic information (characters, location, time, weather, objects, descriptions)
5. Provide specific visual/text/audio generation policies suitable for this scene

## Requirements
- Include ALL required fields: sis_type, scene_id, summary, semantics
- Do not try to generate or guess a unique scene_id (the system will assign it)
- **summary**: Create a clear summary (1-2 sentences).
- **semantics.common.descriptions**: Provide 2-3 concise descriptions that capture the scene's key visual and narrative elements without being overly verbose.
- **characters**: If this scene has NO characters (e.g., landscape, object-only scene, catalog entry), set semantics.common.characters to an empty array: [] (do NOT invent characters). Only include characters if they naturally appear in this scene.
- If characters do appear, include at least one with name, traits, and visual description
- Include at least one object with name and colors
- Fill in mood, location, time, weather with specific values (not empty strings)
- Provide specific style guidance in semantics.text/visual/audio
- Output ONLY valid JSON (no prose, no comments)

## Example Quality Level
Instead of: "The hero defeats the villain"
Generate: "In the dimly lit throne room, the hero engages in a duel. The hero delivers a decisive strike, knocking the crown from the villain's head."

