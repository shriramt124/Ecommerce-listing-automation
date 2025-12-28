Below is an “ultimate” (production-grade) algorithm design. It’s still deterministic (so it won’t randomly change format), but it uses AI/embeddings only where it is genuinely useful: **semantic grouping + synonym selection + implication learning**. Everything else is rules + optimization.

I’m going to describe **what to add/upgrade** compared to the previous algorithm, focusing on edge cases and making it robust.

---

# Ultimate Algorithm: **Constraint + Concepts + Templates + Auction (CCTA)**
Think of title optimization as:  
**“Choose the best set of concepts and place them in the best slots under hard constraints.”**

## Core upgrades vs previous versions
1) **Concept graph (not tokens)**: everything becomes a *concept* (e.g., FRAGRANCE(Lavender), FEATURE(Perforated Box), PRODUCT(Garbage Bags)).
2) **Truth constraints as a schema**: cannot violate.
3) **Implication/Redundancy graph learned from data** (not just hand rules).
4) **Slot auction (weighted interval scheduling)** for “first 40%” placement.
5) **Phrase-level knapsack + eviction**, plus “rewrite-within-concept” not rewrite-title.
6) **Stability layer** (avoid oscillations across runs; important for 10k SKUs).
7) **Policy layer** (Amazon compliance / banned phrases / competitor brands).

---

# 1) Data model (must-have)
### 1.1 Concepts (atomic units)
Represent each title item as:

- `concept_type`: BRAND | PRODUCT | SIZE | COLOR | COUNT | DIMENSION | CAPACITY | FRAGRANCE | SCENT | MATERIAL | FEATURE | USE_CASE | CERTIFICATION | COMPATIBILITY | OTHER
- `truth_value`: canonical truth value (e.g., COLOR=Black)
- `surface_forms`: allowed ways to write it (e.g., “(Black)”, “Black”, “Black Color”)
- `cost(surface_form)`: exact characters
- `value`: derived from keyword table (AdConv/AdUnits), not from AI
- `priority`: Tier-0/Tier-1/Tier-2/Tier-3
- `locked`: true for Tier-0 and Tier-1
- `group_id`: semantic synonym group (garbage/trash/dustbin)

### 1.2 Title template / separators
Extract from base title:
- separator style: pipes, dash section, parentheses
- “chunk structure”: e.g. `[Chunk1] | [Chunk2] | [Chunk3] | [Chunk4] | [Chunk5]`
You keep this structure so the “format stays same”, but you can reorder within rules.

---

# 2) Preprocessing layer (robust normalization)
## 2.1 Canonicalization (solves duplicates)
- Normalize units: `19 X 21 Inches` → `19x21 in`
- Normalize counts: `120 Bags (30 Bags X 4 Rolls)` → `120 Bags (30x4)`
- Normalize spelling: `grey/gray`, `colour/color`
- Morphology: bags/bag, inches/in.

## 2.2 Phrase chunking (solves “Heavy Duty” splitting)
Chunk with deterministic rules:
- known multiword features: “heavy duty”, “easy dispensing”, “perforated box”
- dimension regex
- count regex
- fragrance regex / parentheses
Output: concept candidates, not raw tokens.

---

# 3) Truth schema enforcement (hard constraints)
This is the “never lie” layer.

Rules:
1) For each attribute type (SIZE/COLOR/COUNT/DIMENSION/FRAGRANCE…), allow **only** truth value.
2) If keyword contains conflicting attribute values, you **strip** them and keep only non-conflicting parts.
3) If base title conflicts with truth (rare but possible), truth wins:
   - replace base title value with truth value (and log it).

This solves your “medium black keyword but large white product” scenario perfectly.

---

# 4) Semantic layer (use embeddings, but safely)
## 4.1 Synonym grouping (ChromaDB)
Create semantic groups per concept type:
- PRODUCT synonyms: garbage/trash/dustbin/waste/bin
- USE_CASE synonyms: kitchen/home/office
- FEATURE synonyms: strong/thick/heavy duty

Important: **grouping is type-aware**.  
Don’t compare “kitchen” with “heavy duty” just because embeddings can be noisy.

## 4.2 Champion/Challenger replacement (phrase-level)
For each concept group, pick the *best surface form* for the title based on:
- keyword scores (AdConv)
- replacement margin 1.15
- stability (don’t keep flipping week to week)

So:
- If title says “Trash Bag” but keywords say “Garbage Bag” is much stronger → replace synonym in-place.

---

# 5) NEW: Implication & redundancy as a *learned* graph (not just manual)
This is where your “Lavender Fragrance” vs “Scented” problem gets solved universally.

### 5.1 Build implication rules automatically from your keyword corpus
From 10k keyword phrases you can compute co-occurrence:

- If `FRAGRANCE` appears, how often does `SCENTED` also appear?
- If FRAGRANCE implies SCENTED 95% of time, then SCENTED is redundant when FRAGRANCE exists.

Compute:
- `P(B | A)` (probability of B given A)
- `lift(A,B)` (association strength)

Then create rules like:
- If `P(SCENTED | FRAGRANCE) > 0.9` → FRAGRANCE ⇒ SCENTED (SCENTED becomes optional)
- If `P(GARBAGE_BAG | TRASH_BAG)` high and garbage has higher value → prefer garbage as representative.

### 5.2 Redundancy removal is “value-aware”
Even if redundant, keep both if:
- SCENTED has high standalone keyword score
- and there is budget

This avoids over-pruning when “scented” itself is a strong search term.

---

# 6) Placement layer: **Slot Auction** (fixes “not everything at end” properly)
Instead of zones only, treat early title as **premium real estate**.

## 6.1 Define slots
From your template:
- Slot 1: start of Chunk1 (very high visibility)
- Slot 2: end of Chunk1
- Slot 3: Chunk2
- Slot 4: Chunk3
- Slot 5: Chunk4
- Slot 6: after dash section

Each slot has:
- max char budget contribution to the first 40% goal
- allowed concept types (to preserve meaning)

## 6.2 Auction / optimization
Each concept bids for slots:
- bid = `value × visibility_weight(slot) × type_priority_weight(concept_type)`
- subject to constraints:
  - Tier-0/Tier-1 must be placed before slot cutoff (first 40%)
  - no contradictions
  - no duplicate semantic groups
  - max_features

Solve:
- Greedy with backtracking OR integer programming (small because concepts are few)
This is more powerful than “append then trim”.

Result:
- SIZE/COLOR/COUNT naturally get pushed earlier because they have high visibility weight + priority.

---

# 7) Packing layer: **Phrase knapsack with eviction + backtracking**
After slot auction decides what *should* be included and where, you must fit ≤ 200 chars.

## 7.1 Pack order
1) Lock Tier-0/Tier-1
2) Add highest ROI Tier-2 (features/material/fragrance) by `value_per_char`
3) Add Tier-3 (synonyms/use cases) only if space

## 7.2 Eviction
If overflow:
- remove lowest ROI concept from the latest slot first (usually synonyms/use case)
- never remove locked
- after each eviction, re-run redundancy rules (because removing FRAGRANCE might require keeping SCENTED)

This “re-run redundancy after changes” is the missing piece in many systems.

---

# 8) Stability layer (prevents titles changing too often)
You want consistent titles.

Add:
- **hysteresis**: don’t replace a term unless improvement is significant (your 1.15 margin is part of this)
- store previous chosen representative per semantic group and prefer it unless big gain
- this avoids “today garbage, tomorrow trash” oscillation

---

# 9) Quality gates (meaning + compliance)
Before final output:
1) **Readability gate**: penalize too many features/adjectives; keep max_features=3
2) **Grammar gate (lightweight)**: enforce ordering within chunk:
   - Brand → quality marker (optional) → fragrance → product → size → color
3) **Policy gate**: ban words, competitor brands, excessive punctuation
4) **Dedup gate**: remove repeated concepts + repeated words across concepts

---

# 10) Output rendering (format preservation)
You preserve the original “format signature”:
- keep pipes and dash section
- keep parentheses for color/fragrance if that is the title’s style
- keep ordering of chunks (or allow controlled reorder inside chunks)

You’re not “rewriting”, you’re **reassembling approved concepts into the same layout**.

---

# What this “ultimate” algorithm fixes that earlier ones didn’t
- **Lavender Fragrance vs Scented redundancy**: solved via implication graph + value-aware pruning.
- **Not everything appended at end**: solved via slot auction/visibility weights.
- **Variant mismatch**: solved by truth schema (strip conflicting size/color).
- **Meaning preserved**: concept types + allowed-slot constraints prevent nonsense swaps.
- **No duplicates**: concept-level dedupe + semantic groups + morphological normalization.
- **200 char limit**: phrase-level knapsack + eviction + backtracking + rerun redundancy.

---

# If you want the next deliverable (still no real code)
I can write the pseudocode in the exact functions you asked earlier, but upgraded:

- `parse_title_to_concepts()`
- `normalize_and_canonicalize()`
- `build_truth_concepts()`
- `score_concepts_from_keywords()`
- `learn_implication_graph_from_keywords()`   
- `semantic_group_concepts_with_chroma()`
- `champion_challenger_select_surface_forms()`
- `slot_auction_place_concepts()`
- `knapsack_pack_and_evict()`
- `final_quality_gates()`
- `render_with_format_signature()`
 