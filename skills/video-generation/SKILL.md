---
name: video-generation
description: >
  Generate professional videos using Azure AI Foundry sora-2.
  Use for: product demos, training content, marketing clips, explainer videos,
  architectural walkthroughs, event highlights.
  NOTE: Video jobs are asynchronous — always poll for status.
allowed-tools:
  - start_video_job
  - get_video_status
---

# Video Generation Skill

## When to Use
Invoke this skill when the user asks to:
- Create a video, clip, animation, or motion content
- Generate a product demo or explainer video
- Create training or onboarding content
- Produce marketing or promotional video material

## Workflow

### Phase 1 — Start Job
1. **Parse intent** — Extract: subject, duration (4/8/12s), resolution, style
2. **Craft cinematic prompt** — Include: camera motion, lighting, style, subject action
3. **Start job** — Call `start_video_job`:
   ```
   POST /media/video
   { "prompt": "<cinematic prompt>", "seconds": "4", "size": "1280x720" }
   ```
4. **Return job info** — Provide `job_id` and polling instructions

### Phase 2 — Poll Status
5. **Poll** — Call `get_video_status` with the `job_id`:
   ```
   GET /media/video/{job_id}
   ```
6. **Status values**:
   - `queued` — Job accepted, not yet started
   - `running` — Actively generating
   - `succeeded` — Done, `file_path` available
   - `failed` — Retry with simplified prompt

## Prompt Engineering

### Cinematic Prompt Template
```
[CAMERA MOTION], [SUBJECT DESCRIPTION] in [SETTING].
[ACTION/MOTION]. [LIGHTING]. [STYLE/MOOD].
```

### Examples

| Use Case | Prompt |
|---|---|
| Enterprise demo | "Slow push-in on a sleek enterprise AI dashboard with real-time data flowing across multiple screens. Blue ambient lighting, modern tech aesthetic, no people." |
| Product launch | "Aerial pan across a modern city skyline at golden hour transitioning to an abstract visualization of connected AI nodes. Cinematic grade, smooth motion." |
| Explainer video | "Clean animation of data packets flowing from user devices through a secure cloud gateway into an AI processing core. Blue and white, tech minimal style." |

## Duration Guide
| Seconds | Best For |
|---|---|
| `"4"` | Quick concept visuals, transitions |
| `"8"` | Short demos, product highlights |
| `"12"` | Explainer segments, walkthroughs |

## Resolution
- `1280x720` — HD (default, fastest)
- `1920x1080` — Full HD (richer, slower)

## Error Handling
- `failed` status: Simplify prompt, remove complex camera instructions
- Long wait: Expected for `"12"` second videos (may take 5-15 min)
- Never fabricate `file_path` — only report when status is `succeeded`
