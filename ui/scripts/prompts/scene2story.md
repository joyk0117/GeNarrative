# SceneSIS → StorySIS Prompt

Analyze the following SceneSIS data and generate a complete StorySIS JSON object.

## Input Scenes
${SCENES_JSON}

${ASSIGNMENTS_BLOCK}
## Task
${STORY_TYPE_TASK}
2. Extract common themes and overall story meaning
3. Determine consistent text/visual/audio style policies across scenes
4. Generate scene_blueprints that reference the provided scenes
5. Create a complete StorySIS JSON object
${ROLE_ALIGNMENT_TASK}

## Requirements
- Include ALL required fields: sis_type, story_id, title, summary, semantics, story_type, scene_blueprints
- Generate a new UUID for story_id
- ${STORY_TYPE_REQUIREMENT}
- In semantics.common, extract themes and descriptions that apply to the whole story
- In scene_blueprints, create entries that match the input scenes (use scene_type like "ki", "sho", "ten", "ketsu" or "setup", "conflict", "resolution")
- Respect the provided scene role assignments whenever they are present
- Output ONLY valid JSON (no prose, no comments)
