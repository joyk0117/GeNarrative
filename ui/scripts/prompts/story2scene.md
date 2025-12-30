# StorySIS → SceneSIS Prompt

Generate a complete SceneSIS JSON object based on the provided story context and scene blueprint.

## Story Context
${STORY_CONTEXT_JSON}

## Scene Blueprint (#${BLUEPRINT_INDEX})
${BLUEPRINT_JSON}

## Task
1. Reflect the narrative intent of the blueprint (respect its scene_type and summary) without emitting a scene_type field
2. Inherit style policies from the story's semantics
3. Provide rich semantic information (characters, location, time, weather, objects, descriptions)
4. Provide specific visual/text/audio generation policies suitable for this scene

## Requirements
- Include ALL required fields: sis_type, scene_id, summary, semantics
- Generate a new UUID for scene_id
- In semantics.common, provide detailed scene-specific information
- Include at least one character with name, traits, and visual description
- Include at least one object with name and colors
- Provide specific style guidance in semantics.text/visual/audio
- Output ONLY valid JSON (no prose, no comments)
