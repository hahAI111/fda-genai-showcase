---
name: image-generation
description: >
  Generate professional images using Azure OpenAI gpt-image-2.
  Use for: UI mockups, dashboards, architectural diagrams, report covers,
  marketing visuals, technical illustrations, slide graphics.
allowed-tools:
  - generate_image
  - search_knowledge
---

# Image Generation Skill

## When to Use
Invoke this skill when the user asks to:
- Create an image, photo, illustration, diagram, or visual
- Generate a cover image for a presentation or report
- Visualize an architecture, data flow, or concept
- Produce UI mockup or dashboard preview

## Workflow

1. **Analyze** — Parse the user request to extract:
   - Subject (what to depict)
   - Style preference (photorealistic / diagram / abstract / corporate)
   - Size requirement (default: 1024×1024)
   - Intended use (slide cover / report / marketing / UI)

2. **Enrich Prompt** — Expand sparse inputs into detailed prompts:
   - Add quality cues: "high quality, professional, detailed"
   - Add style cues appropriate to use case
   - Add negative cues implicitly via positive framing
   - Keep prompt under 1000 characters

3. **Generate** — Call `generate_image` tool:
   ```
   POST /media/image
   { "prompt": "<enriched>", "size": "1024x1024" }
   ```

4. **Return** — Include:
   - `file_path` — absolute path to saved PNG
   - `revised_prompt` — Azure's actual prompt used
   - Suggested use and any follow-up actions

## Prompt Engineering Examples

| User Request | Enriched Prompt |
|---|---|
| "dashboard image" | "A professional enterprise data analytics dashboard with KPI cards, trend charts, and blue corporate color scheme. Clean UI, high resolution, flat design." |
| "AI agent diagram" | "Technical architecture diagram: multi-agent AI system with orchestrator, knowledge base, guardrail layers. White background, blue and grey color scheme, node-and-edge layout." |
| "team photo" | "Professional corporate team of diverse engineers collaborating in a modern glass-walled office. Natural lighting, candid but polished." |

## Size Options
- `1024x1024` — Square (default, presentations, thumbnails)
- `1536x1024` — Landscape (slide headers, banners)
- `1024x1536` — Portrait (posters, reports)

## Quality Settings
- `high` — Best quality, slower (default for enterprise)
- `standard` — Faster, good for iteration

## Error Handling
- If prompt is rejected: rephrase, removing sensitive terms
- If generation fails: retry with simplified prompt
- Always confirm `file_path` exists before reporting success
