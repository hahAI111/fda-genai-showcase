---
name: ppt-generation
description: >
  Generate complete PowerPoint (.pptx) presentations using GPT-4.1-mini
  for content structuring and python-pptx for assembly.
  Use for: business proposals, technical deep-dives, executive briefings,
  training decks, architecture reviews, customer presentations.
allowed-tools:
  - generate_ppt
  - search_knowledge
  - analyze_data
---

# PowerPoint Generation Skill

## When to Use
Invoke this skill when the user asks to:
- Create a presentation, deck, slides, PowerPoint, or PPT
- Prepare material for a meeting, briefing, or proposal
- Generate a structured document for a topic
- Build training or onboarding content

## Workflow

1. **Clarify scope** — Extract from request:
   - Topic (required)
   - Target audience (executive / technical / sales / all-staff)
   - Preferred style (professional / minimal / vibrant)
   - Number of slides (default: 8-12)
   - Any specific sections or key points to include

2. **Optionally enrich content** — If the topic relates to knowledge in the system:
   - Search knowledge base first: `search_knowledge(topic)`
   - Inject retrieved facts into the PPT generation prompt
   - This produces grounded, accurate slides (not hallucinated)

3. **Generate deck**:
   ```
   POST /media/ppt
   {
     "topic": "<detailed topic with context>",
     "audience": "enterprise stakeholders",
     "style": "professional"
   }
   ```

4. **Return result**:
   - `file_path` — path to .pptx file
   - `title` — detected deck title
   - `slide_count` — number of slides generated

## Style Guide

| Style | When to Use | Color Scheme |
|---|---|---|
| `professional` | Executive briefings, customer decks | Blue (#1A73E8), neutral text |
| `minimal` | Technical reviews, engineering docs | Dark grey, clean layout |
| `vibrant` | Marketing, product launches | Magenta, high contrast |

## Audience Customization

| Audience | Tone | Depth |
|---|---|---|
| `C-suite executives` | Strategic, business impact | High-level, ROI-focused |
| `engineering teams` | Technical, detailed | Implementation specifics |
| `sales and customer-facing teams` | Value-driven, competitive | Use cases, differentiators |
| `enterprise stakeholders` | Balanced | Mix of strategy and detail |

## Slide Structure Best Practices
- **Slide 1**: Title + subtitle (auto-generated)
- **Slides 2-3**: Problem / Situation / Context
- **Slides 4-6**: Solution / Architecture / How it Works
- **Slides 7-9**: Benefits / Results / Evidence
- **Slide 10**: Key Takeaways (always last)

## Integration with Knowledge Base
When topic matches internal knowledge (e.g., "GenAI governance policy", "RAG architecture"):
1. Call `search_knowledge(topic, top_k=8)` first
2. Prepend retrieved context to the PPT topic prompt
3. Cite sources on the last slide

## Error Handling
- If `slide_count` is 0: LLM likely returned invalid JSON — retry with simpler prompt
- If `file_path` is missing: Check disk space in `output/generated-ppts/`
- For very long topics: Break into multiple decks and reference each other
