Below is a “deep” production-style algorithm that **combines**:
 
- **Champion/Challenger** (value-based semantic replacement, e.g., trash→garbage),
- **Pattern/slot awareness** (size/color/count early, not everything appended),
- **Knapsack with eviction** (global 200-char budget, remove low-value tokens if needed),
- **Product-truth constraints** (never inject wrong size/color/etc.),
- **Limited AI usage** (only for embeddings / semantic grouping, not for writing/deciding freely).
 
I’ll describe it as a deterministic pipeline you can implement with ChromaDB + embeddings.

---

# 0) Inputs you must have (you said you do)
For each ASIN:

1) **Base title** (client’s “out of box” title)
2) **Product truth attributes** (structured):
   - brand, product_type (or category), size, color, count, capacity, material, features, compatibility, etc.
3) **Keyword table** for that ASIN (10k possible):
   - `term`, `score` (AdConv / AdUnits / blended), maybe `impressions`, `clicks`
4) **Rules config** per category:
   - stopwords/promotional bans (“bestseller”, “free”, “offer”, “#1”, etc.)
   - max title length (200 chars)
   - “first 40%” target (80 chars if 200 max)

---

# 1) Key idea: treat the title as “slots”, not a string
Instead of “append words”, you create and fill **slots**:

### Slot groups (zones)
- **Zone A (Decision Zone)**: first 40% of chars (≈80 chars)
  - Must include: `Brand + Core Product + (Size/Color/Count/Capacity as applicable)`
- **Zone B (Conversion Zone)**: next 40%
  - material, key features, strength claims that are truthful
- **Zone C (Long-tail Zone)**: last 20%
  - use cases, secondary synonyms, long tail

### Title representation
Parse base title into **token objects**:

Each token is:
- `text` (original surface form)
- `type` ∈ {BRAND, PRODUCT, SIZE, COLOR, COUNT, CAPACITY, MATERIAL, FEATURE, USE_CASE, OTHER, BANNED}
- `locked` (cannot remove; e.g., brand, essential product words)
- `value` (SEO value score)
- `cost` (character cost incl. leading space)
- `origin` ∈ {base, keyword, truth}
- `semantic_group` (cluster id, explained below)

This structure prevents grammar-breaking swaps because you only replace within the same `type` or same `semantic_group`.

---

# 2) Preprocessing: normalize, ban, and canonicalize (deterministic)
### 2.1 Normalize text
- lowercase for matching, keep original casing for output
- normalize units: `30 L`, `30L`, `30 liters` → canonical `30L`
- normalize variants: `grey/gray`, `colour/color`
- singular/plural normalization for matching: bag/bags, liner/liners

### 2.2 Remove / mark banned tokens
If base title contains promotional/forbidden terms:
- mark as `BANNED` with very low value (eligible for eviction)

### 2.3 Build “truth token set”
From your product truth attributes generate canonical tokens:
- Brand token(s)
- Core product phrase token(s) (you should have product_type)
- Size token(s) (e.g., Large, XL, 30L)
- Color token(s)
- Count token(s) (e.g., 30 pcs)
- Material token(s)
- Feature token(s)

These are the only attribute values allowed to appear for that ASIN.

**Hard constraint:** if a keyword suggests `Medium` but truth says `Large`, you may use the *pattern* but must fill the slot with `Large`.

---

# 3) Keyword understanding: “pattern extraction” without hallucination
We do NOT ask an LLM to rewrite. We only use embeddings to help grouping.

### 3.1 Build keyword candidates (top-N)
From 10k keywords, don’t process all. Do:
- keep top N by score (N=300 or 500)
- remove clear junk (very long queries, banned words, competitor brands if policy says)

### 3.2 Attribute-value filtering using truth
For each keyword phrase, detect attribute mentions:
- If keyword contains a size/color/count that conflicts with truth → **strip that conflicting part** from candidate, not the whole phrase.
  - Example:
    - keyword: “garbage bag medium black”
    - truth: size=Large, color=White
    - strip: remove “medium”, “black”
    - leftover candidate: “garbage bag” (pattern says size+color matter; we will ensure truth size+color are included elsewhere)

This single step solves your “don’t copy medium black” scenario safely.

### 3.3 Extract dominant templates
From the filtered top keywords, extract patterns like:
- PRODUCT + SIZE + COLOR
- PRODUCT + CAPACITY + FEATURE
- BRAND + PRODUCT + SIZE

You can do this deterministically via your attribute classifier (dictionary/regex), plus embeddings for “product synonyms”.

Pick the top 1–3 templates by weighted frequency (weighted by score).

---

# 4) Semantic grouping (ChromaDB use) – but controlled
You use ChromaDB/embeddings for **two things only**:

## 4.1 Synonym groups for product concepts (semantic groups)
Create clusters like:
- {trash bag, garbage bag, bin bag, dustbin bag, waste bag}
- {liner, bag liner}
- {heavy duty, strong, thick}

Implementation:
- embed each candidate phrase (2–3 grams)
- cluster using HDBSCAN or simple “nearest centroid” with threshold
- assign `semantic_group_id`

Now you can enforce: **at most one representative per semantic group** (unless group is “truth-critical” like size/color).

## 4.2 Challenger matching (find what to replace)
When inserting a candidate, use embedding similarity to find the closest existing token/phrase of the same type or group—then compare values and decide replacement.

This solves “trash already present but garbage better”.

---

# 5) The combined optimizer: “Slot-first + Champion/Challenger + Knapsack eviction”
This is the core algorithm.

## 5.1 Build the “base skeleton” (preserve format)
Start from the base title tokens, but:
- ensure brand exists (inject from truth if missing)
- ensure core product phrase exists (from truth if missing)
- ensure truth-critical attributes exist somewhere (size/color/count/etc.)

**But** we don’t dump them at end: we place them in Zone A if missing.

## 5.2 Zone A guarantee (first 40% decision zone)
Goal: within first ~80 chars include:
- Brand (truth)
- Core product (truth/product synonyms)
- Size + Color + Count/Capacity (truth, if applicable)

Mechanism:
1) Identify whether each truth-critical attribute is present in Zone A
2) If not, insert it into Zone A using **minimal reordering**:
   - Prefer inserting immediately after product phrase
   - If base title already has size/color later, **move** it earlier (don’t duplicate)
3) If Zone A exceeds budget, evict the lowest-value non-truth token from Zone A (often promotional words), pushing it to later zones or dropping it.

This addresses your “first 40% should help decision”.

## 5.3 Candidate processing (Champion/Challenger)
For each candidate keyword element (phrase or token) in descending score:

### Step A: Validate against truth
- If candidate is an attribute value conflicting with truth → reject (or strip)
- If candidate is competitor brand → reject

### Step B: Determine placement zone
- If type ∈ {SIZE, COLOR, COUNT, CAPACITY} → Zone A (truth only)
- If type ∈ {MATERIAL, FEATURE} → Zone B
- If type ∈ {USE_CASE, synonym-of-product} → Zone C or B depending on score

### Step C: Decide action (Replace vs Insert vs Skip)
1) Find semantic match in current title (same semantic group or high similarity)
2) If match found:
   - Compare values (candidate_score vs existing_token_value)
   - If candidate_score is higher AND replacement doesn’t violate truth AND keeps readability:
     - Replace in-place (Champion/Challenger)
   - Else skip
3) If no match found:
   - Attempt insert into chosen zone using knapsack budgeting and eviction logic

This solves:
- “trash already there but garbage better” (replace)
- “not present in title then how insert” (insert)
- “meaningful not arbitrary” (type-aware placement + group constraints)

---

# 6) Budgeting: real knapsack with eviction (not naive greedy)
This is where “knapsack” truly fits.

### Objective function (what we maximize)
Maximize total SEO value with penalties:
- + keyword score contribution
- + “decision completeness” bonus if Zone A contains size+color+count
- − redundancy penalty if two items from same semantic group
- − readability penalty if too many OTHER tokens or too many adjectives

### Practical implementation (fast)
Exact knapsack is expensive if you treat each word as an item, but you can do a **two-level knapsack**:

**Level 1 (Phrase-level items)**:
- Treat candidate phrases (“heavy duty”, “leak proof”, “kitchen”) as items with:
  - cost = len(phrase)+1
  - value = score_adjusted
- Choose a set that fits in remaining budget of Zone B + C
- Use MMR-like diversity constraint to avoid near duplicates (semantic groups)

**Level 2 (Eviction within title)**:
When you must add a high-value item but no space:
- Find removable tokens in target zone with lowest “value per char”
- Remove until space fits
- Never remove locked truth-critical tokens

This gives you the “remove less necessary to fit Black” behavior.

---

# 7) Handling your two key scenarios explicitly

## Scenario A: “Black Heavy Duty” but title already has “Heavy Duty”
- semantic group for “heavy duty” already present
- “black” is color attribute
- If truth color is Black:
  - Ensure color appears in Zone A (preferred) or near size, not necessarily at end
- If title already has Black at end:
  - Move Black earlier (Zone A) and remove the old occurrence (no duplicates)

## Scenario B: Top keyword “Garbage bag medium black”, but product is “Large White”
- Extract template: PRODUCT + SIZE + COLOR
- Fill SIZE with Large (truth), COLOR with White (truth)
- For PRODUCT synonym: if “garbage bag” beats “trash bag”, replace “trash” → “garbage” (Champion/Challenger)
- Never insert “medium” or “black”

Result becomes “Garbage Bag Large White …” (pattern preserved, truth preserved)

---

# 8) Where AI is used (limited, safe)
You should not use a generative LLM to “write” the title.

Use AI only for:
1) **Embeddings** (semantic groups, challenger matching)
2) Optional: **noun phrase chunking** using an NLP model (spaCy) — not an LLM, deterministic-ish
3) Optional: **readability scoring** classifier (small model) to penalize spamminess (still not generating text)

Everything else is rule-based.

---

# 9) What you will still need to decide (configuration)
Even with this algorithm, you must choose policy thresholds:

- Similarity threshold for “same semantic group”: 0.80–0.88
- Replacement margin: require candidate_score ≥ existing_score * 1.15 (avoid oscillation)
- Zone A budget: 35–45% (often ~80 chars is good)
- Max adjectives/features allowed: e.g., 2–3
- Banned/promotional word list per category

---

# 10) If you want, I can turn this into implementable steps + code skeleton
To generate a clean code blueprint, I need one more concrete sample from you:

1) A real **base title**
2) Its **truth attributes** dict
3) Top ~30 keywords with scores for that ASIN (like the table in your image)

Then I’ll output:
- a precise step-by-step flow,
- data structures,
- and a Python skeleton showing: `parse_title()`, `classify_tokens()`, `build_zones()`, `champion_challenger_replace()`, `knapsack_select_phrases()`, `evict_to_fit()`, `render_title()`.

That will be the “combined deeper algorithm” you asked for, but grounded in your real data and constraints.