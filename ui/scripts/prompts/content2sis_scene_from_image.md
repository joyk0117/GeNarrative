Analyze the attached image and produce a complete SceneSIS JSON that matches the provided schema.

Include all required fields: sis_type='scene', scene_id, summary, and semantics.

For semantics, include: common (mood, characters with visual details, location, time, weather, objects with colors, descriptions), text, visual, and audio.

If there are NO characters (e.g., landscape-only image), set common.characters to an empty array: [] (do NOT invent characters).

Return ONLY a valid JSON object (no prose, no comments).
