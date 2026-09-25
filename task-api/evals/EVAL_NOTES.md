# Eval notes

Ran the 8 cases in cases.json against the real model (results.json has full output).

## What passed
- Clear fiction (The Great Gatsby): correct category, confidence 1.0.
- Missing description, generic title, price outlier: all correctly flagged.
- Duplicated description: correctly caught — this is the real bug pattern found
  in the A9 scraper (some Books to Scrape descriptions repeat mid-sentence in
  the raw HTML). The model noticed it without being shown the exact phrase.

## Where my test design was wrong, not the model
- "clear_poetry" expected category "childrens"; got "poetry". On review, poetry
  is the more defensible answer for a poetry collection — my expectation was
  too narrow, not a model failure.
- "ambiguous_genre" expected low confidence; got 0.75. The description wasn't
  actually ambiguous enough to justify low confidence — my test case needs a
  genuinely harder example to prove what I intended.

## A real model weakness
- "empty_title_edge_case" had description = "No real description here." — a
  real, non-empty string — but the model still flagged missing_description.
  It appears to have reacted to the sentence's content rather than checking
  whether the field was actually empty/null. This is a genuine, reproducible
  limitation worth knowing about before trusting this endpoint on real input
  with unusual or self-referential text.