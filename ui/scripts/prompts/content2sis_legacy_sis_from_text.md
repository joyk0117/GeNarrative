Analyze the following text and create a Semantic Interface Structure (SIS) in JSON format.

Text: "${text_content}"

Provide ONLY a JSON object with the following structure:
{
  "summary": "brief description of the text content",
  "emotions": ["emotion1", "emotion2", "emotion3"],
  "mood": "overall mood",
  "themes": ["theme1", "theme2", "theme3"],
  "narrative": {
    "characters": ["character descriptions"],
    "location": "setting description",
    "weather": "weather conditions",
    "tone": "narrative tone",
    "style": "narrative style"
  },
  "visual": {
    "style": "visual style implied by the text",
    "composition": "scene composition",
    "lighting": "lighting conditions described",
    "perspective": "narrative viewpoint",
    "colors": ["color1", "color2", "color3"]
  },
  "audio": {
    "genre": "music genre that would fit",
    "tempo": "tempo description",
    "instruments": ["instrument1", "instrument2"],
    "structure": "musical structure"
  }
}
