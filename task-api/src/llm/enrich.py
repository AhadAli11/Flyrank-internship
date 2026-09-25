import os
import json
import time
from openai import OpenAI
from src.llm.schema import EnrichmentResult

import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from src.llm.schema import EnrichmentResult

load_dotenv()


client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)

SYSTEM_PROMPT = """You classify a scraped book record. Respond with ONLY a JSON object, no other text, matching exactly this shape:

{
  "category": one of "fiction", "non-fiction", "poetry", "childrens", "other",
  "summary": a one-sentence summary, max 200 characters,
  "quality_flags": an array containing zero or more of "missing_description", "description_duplicated", "generic_title", "price_outlier",
  "confidence": a number between 0.0 and 1.0
}

Rules:
- Never invent a category outside the list.
- Never invent a quality flag outside the list.
- If a description appears to repeat itself mid-sentence (duplicated text), include "description_duplicated".
- If description is null or empty, include "missing_description".
- If you are unsure, use category "other" and confidence below 0.5. Do not guess.
- Output ONLY the JSON object. No markdown, no explanation, no code fences.
"""


def call_model_once(title, description, price_gbp):
    user_content = json.dumps({
        "title": title,
        "description": description,
        "price_gbp": price_gbp
    })

    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        timeout=15,
    )
    raw = response.choices[0].message.content
    return raw


def enrich_book(title, description, price_gbp, max_retries=2):
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            raw = call_model_once(title, description, price_gbp)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            return EnrichmentResult(**parsed)

        except json.JSONDecodeError as e:
            last_error = f"Model did not return valid JSON: {e}"
        except Exception as e:
            last_error = f"Validation or request failed: {e}"

        if attempt < max_retries:
            time.sleep(1 * (attempt + 1))

    raise RuntimeError(f"enrich_book failed after {max_retries + 1} attempts: {last_error}")