# Job card

What it does (one sentence): Classifies a scraped book record into a category,
writes a one-sentence summary, and flags data-quality issues in the scraped record.

Input:
{
  "title": "string, 1-300 characters",
  "description": "string or null, 0-4000 characters",
  "price_gbp": "number"
}

Output:
{
  "category": one of [fiction, non-fiction, poetry, childrens, other],
  "summary": "one short sentence, max 200 characters",
  "quality_flags": array, zero or more of [missing_description, description_duplicated, generic_title, price_outlier],
  "confidence": 0.0-1.0
}

It must never: invent a category outside the list · invent a quality flag
outside the list · return free text outside the JSON object · guess when unsure

When unsure it should: return category "other" with confidence below 0.5, not a guess