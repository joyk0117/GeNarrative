You are an expert prompt engineer for an image generation AI like Stable Diffusion.

Below is a JSON object representing the Semantic Interface Structure (SIS; formerly SIS) of a scene.

Your task is to:
1. Read and understand the JSON data.
2. Convert the structured information into a vivid, coherent, and descriptive **natural language prompt** suitable for generating a ${width}x${height} image in the specified style.
3. Keep it within 1–2 sentences.
4. Focus on key visual and emotional elements.
5. Do NOT include any JSON or explanation in the output — output only the prompt.

Here is the SIS data:

```json
${sis_json}
```

Generate the image prompt:
