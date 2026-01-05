Analyze the following text and produce a complete SceneSIS JSON that matches the provided schema.

Include all required fields: sis_type='scene', scene_id, summary, and semantics.

For semantics, include: common (mood, characters with visual details, location, time, weather, objects with colors, descriptions), text, visual, and audio.

If the text implies NO characters (e.g., scenery-only), set common.characters to an empty array: [] (do NOT invent characters).

Text:
${text_json}

Return ONLY a valid JSON object (no prose, no comments).
