"""Summarize a transcript via a local Ollama server."""

from __future__ import annotations

from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPT_TEMPLATE = """You are a precise meeting notes assistant.

Below is the raw transcript of a meeting. Produce clean, structured notes in markdown.
Be specific. Do not invent details. If a section has no content, write "None recorded".

Use exactly these sections, in this order:

## TL;DR
Two to three sentences. What was the meeting about and what is the headline outcome?

## Key Discussion Points
Bulleted list. Each point one short sentence. Group related points.

## Decisions Made
Bulleted list of concrete decisions. Quote the deciding language if useful.

## Action Items
One per line in this exact format:
- [ ] **Owner** — action (deadline if mentioned)
If no owner was named, use **Unassigned**.

## Open Questions
Questions raised but not answered in the meeting.

## Notable Quotes
Optional. Up to three short verbatim quotes worth keeping.

Transcript:
---
{transcript}
---
"""


def summarize(
    transcript_path: Path,
    output_path: Path,
    model: str = "llama3.1:8b",
    temperature: float = 0.2,
    timeout: int = 600,
) -> Path:
    """Call Ollama with the meeting-notes prompt and save the response as markdown."""
    transcript_path = Path(transcript_path)
    output_path = Path(output_path)

    transcript = transcript_path.read_text(encoding="utf-8")
    prompt = PROMPT_TEMPLATE.format(transcript=transcript)

    print(f"Summarizing with {model} (this may take a minute)...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=timeout,
        )
    except requests.ConnectionError as e:
        raise SystemExit(
            "Could not reach Ollama at http://localhost:11434. "
            "Is it running? Try `brew services start ollama` or `ollama serve`."
        ) from e

    response.raise_for_status()
    summary = response.json()["response"].strip()

    output_path.write_text(summary + "\n", encoding="utf-8")
    print(f"Saved summary: {output_path}")
    return output_path
