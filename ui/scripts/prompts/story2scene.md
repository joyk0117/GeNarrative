# StorySIS → SceneSIS Prompt

Generate a complete SceneSIS JSON object based on the provided story context and scene blueprint.

## Story Context
${STORY_CONTEXT_JSON}

## Scene Blueprint (#${BLUEPRINT_INDEX})
${BLUEPRINT_JSON}

## Story Type Guide
${STORY_TYPE_GUIDE}

## Task
1. **Expand and enrich the blueprint**: Use the blueprint's scene_type and summary as a starting point, but create MORE DETAILED and SPECIFIC content for this scene
2. **Create unique descriptions**: Generate NEW, expanded descriptions that go beyond the blueprint summary. Add specific details about what happens, visual elements, atmosphere, and character actions
3. Inherit style policies from the story's semantics
4. Provide rich semantic information (characters, location, time, weather, objects, descriptions)
5. Provide specific visual/text/audio generation policies suitable for this scene

## Requirements
- Include ALL required fields: sis_type, scene_id, summary, semantics
- Do not try to generate or guess a unique scene_id (the system will assign it)
- **summary**: Create a detailed summary that expands on the blueprint (2-3 sentences minimum)
- **semantics.common.descriptions**: Provide 2-5 detailed descriptions that elaborate on the scene's visual, emotional, and narrative elements (DO NOT just copy the blueprint summary)
- Include at least one character with name, traits, and visual description
- Include at least one object with name and colors
- Fill in mood, location, time, weather with specific values (not empty strings)
- Provide specific style guidance in semantics.text/visual/audio
- Output ONLY valid JSON (no prose, no comments)

## Example Quality Level
Instead of: "The hero defeats the villain"
Generate: "In the dimly lit throne room, the hero engages in a final duel with the villain. Sparks fly from their clashing swords as the hero delivers a decisive strike, sending the villain's crown clattering across the marble floor. The hero stands victorious as dawn light streams through the shattered windows."

