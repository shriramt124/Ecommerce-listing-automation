# AdKrux Multi-Agent Title Optimization Architecture

## Overview

This document provides a detailed architecture of the AdKrux multi-agent title optimization system. The system uses a modular pipeline of specialized AI agents to transform Amazon product titles while minimizing hallucinations and maximizing search relevance.

**Core Principle:** Break complex title optimization into independent, validated steps rather than one monolithic AI call.

---

## System Architecture

### Technology Stack

- **LLM:** DeepSeek-v3.1 (671b-cloud) via Ollama API
- **Vector Database:** ChromaDB with 153,459 keywords
- **Embeddings:** SentenceTransformers (all-MiniLM-L6-v2)
- **Language:** Python 3.9+
- **Retry Strategy:** Progressive temperature (0.2 → 0.3 → 0.4 → 0.5), 3-4 retries

### Pipeline Flow

```
Original Title → Category Detection → Concept Evaluation → Vector Retrieval 
→ Keyword Selection → Title Composition → Post-Processing → Validation → Output
```

---

## Agent Specifications

### 1. CategoryDetectorAgent

**Purpose:** Identify product category, subcategory, and search priorities to guide downstream agents.

**Input:**
- `base_title`: Original Amazon title
- `truth`: Product attributes (brand, product, size, color, etc.)

**Prompt Structure:**
```
You are an e-commerce category classification expert.

PRODUCT TITLE: "{base_title}"
BRAND: {truth.brand}
PRODUCT TYPE: {truth.product}

TASK: Classify this product into category/subcategory.

GUIDELINES:
1. Be SPECIFIC (not "home", use "home_storage/garbage_bags")
2. Identify key differentiating attributes (scented, size, material)
3. List search priorities (what customers actually search)
4. Determine if color is important for this category

Output ONLY JSON:
{
  "category": "specific_category",
  "subcategory": "specific_subcategory",
  "key_attributes": ["attribute1", "attribute2"],
  "search_priorities": ["priority1", "priority2"],
  "color_important": true/false
}
```

**Output Example:**
```json
{
  "category": "home_storage",
  "subcategory": "garbage_bags",
  "key_attributes": ["scented_lavender", "perforated_box_dispenser", "size_19x21_inches"],
  "search_priorities": ["scented trash bags", "lavender garbage bags", "perforated box trash bags"],
  "color_important": false
}
```

**Anti-Hallucination Measures:**
- Strict JSON schema validation
- Requires specific category/subcategory (not generic)
- Fallback to "general/unknown" if AI fails

---

### 2. ConceptEvaluatorAgent

**Purpose:** Evaluate subjective marketing terms to determine if they add value or are generic filler.

**Input:**
- `concept`: Text of the concept (e.g., "Premium", "Scented")
- `concept_type`: Type from parser (BRAND, PRODUCT, DESCRIPTOR, etc.)
- `context`: Product info, category, existing concepts

**Prompt Structure:**
```
You are an Amazon title quality evaluator.

CONCEPT: "{concept}"
TYPE: {concept_type}
PRODUCT: {context.product}
BRAND: {context.brand}
CATEGORY: {context.category}

TASK: Decide if this concept should be KEPT or REMOVED.

EVALUATION CRITERIA:
1. KEEP if:
   - Factual differentiator ("Scented", "Medium", "Black")
   - Brand-specific term
   - Functional attribute ("Perforated Box")
   
2. REMOVE if:
   - Generic filler ("Quality", "Great", "Best")
   - Redundant with product type
   - Too vague without specs

Output ONLY JSON:
{
  "keep": true/false,
  "reason": "specific explanation",
  "alternative": "better word if applicable"
}
```

**Output Example:**
```json
{
  "keep": true,
  "reason": "Premium is justified by perforated box and scented feature",
  "alternative": ""
}
```

**Trigger Words:** premium, scented, deluxe, superior, quality (only these get evaluated)

---

### 3. QueryPlannerAgent

**Purpose:** Generate search queries for vector retrieval based on product characteristics.

**Input:**
- `base_title`: Original title
- `truth`: Product attributes
- `category_info`: Category detection results
- `anchors`: Core search terms
- `existing_queries`: Already-generated queries (for AI rounds)

**Prompt Structure:**
```
You are a keyword research strategist for Amazon SEO.

PRODUCT: {truth.product}
CATEGORY: {category_info.category} / {category_info.subcategory}
SEARCH PRIORITIES: {category_info.search_priorities}

CURRENT ANCHORS:
{anchors}

EXISTING QUERIES:
{existing_queries}

TASK: Generate 3-5 NEW search queries for vector retrieval.

GUIDELINES:
1. Focus on what customers TYPE in Amazon search
2. Combine product + attribute (e.g., "scented garbage bags")
3. Use category search priorities as hints
4. Avoid duplicating existing queries
5. Keep queries natural (2-4 words)

Output ONLY JSON:
{
  "new_queries": ["query1", "query2", "query3"]
}
```

**Output Example:**
```json
{
  "new_queries": [
    "lavender scented trash bags",
    "perforated box garbage bags",
    "medium size dustbin bags"
  ]
}
```

**Fallback:** If AI fails, returns empty list. Pipeline continues with pre-built queries.

---

### 4. Vector Retrieval (Non-Agent Process)

**Purpose:** Execute search queries against ChromaDB to retrieve relevant keywords.

**Process:**
1. Execute all queries against vector database
2. Merge results by keyword (lowercase key)
3. Track which queries hit each keyword (`hit_queries`)
4. Rank by: similarity (primary), then score (secondary)
5. Return top 60 candidates

**Data Structure:**
```json
{
  "keyword": "garbage bags medium size",
  "score": 0.4167,
  "similarity": 1.0,
  "ad_units": 0.0,
  "ad_conv": 0.0,
  "hit_queries": ["medium garbage bags", "garbage bags medium", "garbage bags medium size"]
}
```

**Score Meaning:** Normalized search volume proxy (0.0 to 1.0+, higher = more searches)

---

### 5. KeywordSelectorAgent

**Purpose:** Select the TOP 10 keywords from 60 candidates based on search volume and relevance.

**Input:**
- `existing_concepts`: Text from current title concepts
- `candidates`: Top 60 keywords from vector retrieval (with score, similarity)
- `context`: Product, brand, category

**Prompt Structure:**
```
You are an Amazon search optimization expert.

PRODUCT: {context.product}
BRAND: {context.brand}
CATEGORY: {context.category}

CURRENT CONCEPTS IN TITLE:
{existing_concepts}

CANDIDATE KEYWORDS (ONLY choose from this list):
[
  {"keyword": "garbage bags medium size", "score": 0.4167, "similarity": 1.0, ...},
  {"keyword": "garbage bags medium", "score": 0.0042, "similarity": 1.0, ...},
  ...
]

TASK: Select the TOP 10 keywords for Amazon title optimization.

SELECTION CRITERIA (in priority order):
1. SEARCH VOLUME IS KING: Prioritize keywords with highest score (search volume proxy)
2. COMPLETE PHRASES WIN: Select multi-word phrases intact
   - "product medium size" is better than just "product" or "medium"
3. OVERLAP IS OKAY: High-volume phrases beat novelty
   - If title has "product" and candidate is "product medium size" with high score → SELECT IT
4. ZONE CLASSIFICATION for title composition:
   - ZONE_B (default): Most search phrases go here - high-volume terms customers search
   - ZONE_C: Variants/descriptors like fragrance, flavor, style, finish

ZONE EXAMPLES (generic patterns):
- ZONE_B: "product type size", "product for use case", "product with feature"
- ZONE_C: "lavender scented", "premium finish", "classic style", "mint flavor"

STRICT RULES:
- ONLY select from CANDIDATE KEYWORDS list
- Do NOT invent keywords
- Reject cross-category terms
- Do NOT reject high-volume keywords due to partial overlap with title

Respond ONLY JSON:
{
  "selected_keywords": [
    {"keyword": "keyword1", "zone": "ZONE_B|ZONE_C", "reason": "why selected"}
  ],
  "rejected_count": 0,
  "rejection_reasons": []
}
```

**Output Example:**
```json
{
  "selected_keywords": [
    {
      "keyword": "garbage bags medium size",
      "zone": "ZONE_B",
      "score": 0.4167,
      "reason": "Highest volume phrase, complete search term"
    },
    {
      "keyword": "lavender scented trash bags",
      "zone": "ZONE_C",
      "score": 0.0153,
      "reason": "Fragrance variant with good volume"
    }
  ],
  "rejected_count": 15,
  "rejection_reasons": ["low volume", "cross-category"]
}
```

**Auto-Fallback Logic (CRITICAL):**
If AI returns empty `selected_keywords`:
1. Auto-select top 10 keywords by score (descending)
2. Default zone assignment: `ZONE_B`
3. Zone C for terms containing: scent, fragrance, flavor, aroma, smell, style, finish, design, pattern
4. Add `reason: "auto-selected (high volume)"`

This ensures pipeline never fails due to overly conservative AI selection.

---

### 6. TitleComposerAgent

**Purpose:** Compose the final optimized title using zone-based structure.

**Input:**
- `original_title`: Original Amazon title
- `truth`: Product attributes with `_locked` facts
- `concepts`: Evaluated concepts from parser
- `selected_keywords`: TOP 10 keywords from KeywordSelector
- `category_info`: Category detection results

**Prompt Structure:**
```
You are an expert Amazon title optimization AI.

ORIGINAL TITLE (reference):
"{original_title}"

PRODUCT INFORMATION (from original):
- Brand: {truth.brand}
- Product Type: {truth.product}
- Size: {truth.size}
- Color: {truth.color}
- Count/Quantity: {truth.count}
- Dimensions: {truth.dimension}
- Material: {truth.material}
- Features: {truth.features}

LOCKED FACTS (copy EXACTLY, do not rewrite):
- Pack string: "{locked.count_exact}"
- Dimension: "{locked.dimension_exact}"

CATEGORY: {category_info.category} / {category_info.subcategory}
TOP SEARCH TERMS: {category_info.search_priorities}

CONCEPTS FROM ORIGINAL TITLE (you may reuse/reorder):
- Brand (BRAND)
- Premium (DESCRIPTOR)
- Scented (DESCRIPTOR)
- Garbage Bags (PRODUCT)
- ...

APPROVED KEYWORDS (with zone hints from retrieval):
- garbage bags medium size [ZONE_B] (score: 0.4167)
- scented trash bags [ZONE_B] (score: 0.0153)
- lavender scented [ZONE_C] (score: 0.0089)
- ...

⭐ TOP KEYWORDS BY SEARCH VOLUME (MUST INCLUDE THESE IN TITLE):
  #1: "garbage bags medium size" (score: 0.4167)
  #2: "scented trash bags" (score: 0.0153)
  #3: "lavender scented" (score: 0.0089)

TASK: Produce a single optimized title using ZONE-BASED COMPOSITION.

CRITICAL ANTI-HALLUCINATION RULES (VIOLATION = FAILURE):
1. NEVER invent words not in ORIGINAL TITLE or APPROVED KEYWORDS
2. NEVER change specific descriptors (e.g., "Lavender" → "Fresh", "Steel" → "Metal")
3. NEVER assume features not explicitly stated
4. If APPROVED KEYWORDS is empty, restructure ORIGINAL TITLE only

ZONE-BASED COMPOSITION STRATEGY:
Think of zones as logical sections that flow naturally with commas:

ZONE A (~40% chars): PURE PRODUCT INFORMATION (specs only, no keywords)
  * Brand + Product Type + Size + Dimension + Quantity + Color
  * Use LOCKED FACTS exactly ONCE (never repeat pack count or dimension)
  * Example: "Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black"

ZONE B (~40% chars): HIGH-VOLUME SEARCH PHRASES (keywords, no spec repetition)
  * Insert TOP search keywords from APPROVED KEYWORDS
  * Include COMPLETE phrases from top keywords
  * Combine naturally: "Black Garbage Bags Medium Size with Perforated Box for Easy Dispensing"
  * DO NOT repeat specs already in Zone A
  * If Zone A has "Medium" and "120 Bags", Zone B should NOT repeat these
  * Add descriptive words like "Premium", "Heavy Duty" if in original or keywords

ZONE C (~20% chars): DESCRIPTORS (fragrance/style details)
  * Exact fragrance names: "Lavender Fragrance" or "with Lavender Fragrance"
  * Secondary keywords: "Scented Trash Bags"
  * Combine with "with" or commas naturally

NATURAL FLOW EXAMPLE:
✅ GOOD: "Brand Product, Size, Quantity, Color, Search Phrase with Feature, Descriptor"
"Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30x4), Black, Garbage Bags Medium Size with Perforated Box, Lavender Fragrance"

❌ BAD: "Brand Product Medium 19x21, 120 Bags (30x4) (30x4), Medium Garbage Bags..."
(Repeats pack count, repeats "Medium")

STRICT COMPOSITION RULES:
1. Each spec appears EXACTLY ONCE (no "120 Bags (30x4) (30x4)")
2. LOCKED FACTS copied exactly, used ONCE only
3. Flow with commas, NOT pipes (|)
4. Combine naturally - don't fragment
5. Brand appears ONCE at start
6. ONLY words from ORIGINAL TITLE or APPROVED KEYWORDS
7. Target 180-200 chars

ZONE INTEGRATION:
Don't create rigid barriers. Flow zones together:
"[Zone A: specs], [Zone B: keywords with features], [Zone C: descriptors]"

Output ONLY valid JSON:
{
  "full_title": "...",
  "char_count": 0,
  "zone_a": "first ~40% of title",
  "zone_b": "middle ~40% of title",
  "zone_c": "final ~20% of title",
  "reasoning": {"zone_a_rationale": "...", "zone_b_rationale": "...", "zone_c_rationale": "..."}
}
```

**Output Example:**
```json
{
  "full_title": "Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black, Garbage Bags Medium Size with Perforated Box for Easy Dispensing, Lavender Fragrance",
  "char_count": 180,
  "zone_a": "Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black",
  "zone_b": "Garbage Bags Medium Size with Perforated Box for Easy Dispensing",
  "zone_c": "Lavender Fragrance",
  "reasoning": {
    "zone_a_rationale": "Brand, product, all specs in clean flow",
    "zone_b_rationale": "Highest-volume phrase 'garbage bags medium size' with key feature",
    "zone_c_rationale": "Exact fragrance name from original"
  }
}
```

**Fallback:** If AI fails after retries, returns original title with error flag.

---

### 7. Post-Processing (Non-Agent Process)

**Purpose:** Fix common AI output issues and enforce locked facts.

**Operations:**
1. **Enforce locked substrings:**
   - If pack count from locked facts not in title, regex-replace first occurrence
   - If dimension from locked facts not in title, regex-replace first occurrence
   
2. **Fix common spacing issues:**
   - `Inch es` → `Inches`
   - `Roll s` → `Rolls`
   - `Bag s` → `Bags`
   
3. **Remove duplicate pack counts:**
   - Detect patterns like `120 Bags (30x4) (30x4)`
   - Keep only first occurrence

4. **Clean pipes and extra spaces:**
   - Replace `|` with `,`
   - Collapse multiple spaces

---

### 8. TitleExtenderAgent (Optional)

**Purpose:** Extend titles shorter than 170 characters to utilize full Amazon SEO potential.

**Input:**
- `title`: Current title
- `truth`: Product attributes
- `selected_keywords`: Remaining unused keywords
- `category_info`: Category context
- `target_length`: Target char count (default 190)

**Prompt Structure:**
```
You are an Amazon title extension specialist.

CURRENT TITLE: "{title}"
CURRENT LENGTH: {len(title)}
TARGET LENGTH: {target_length}

REMAINING KEYWORDS:
{unused_keywords}

TASK: Extend the title to ~{target_length} chars by adding valuable keywords.

RULES:
1. Maintain natural flow
2. Add keywords from REMAINING KEYWORDS only
3. Prioritize highest-score keywords
4. Do NOT repeat existing words
5. Keep Zone C style (descriptors at end)

Output ONLY the extended title as plain text.
```

**Trigger:** Only runs if title < 170 characters

---

### 9. Validator (Non-Agent Process)

**Purpose:** Final quality checks before output.

**Validation Checks:**
- Length: 160-200 chars (warning if outside)
- Brand present (if provided)
- Product present
- Size present (if provided)
- Color present (if provided)
- No banned terms: "#1", "best seller", "free", "discount", "sale", "cheap"
- No policy violations

**Output:**
```json
{
  "is_valid": true,
  "issues": [],
  "char_count": 185
}
```

---

## Data Flow Summary

### Step-by-Step Execution

1. **Input Parsing:**
   - Parse original title into tokens/concepts
   - Extract locked facts (pack count, dimensions)
   - Build truth object with attributes

2. **Category Detection:**
   - LLM identifies category/subcategory
   - Determines search priorities
   - Sets color importance flag

3. **Concept Evaluation:**
   - Filter subjective terms ("Premium", "Quality")
   - Keep factual differentiators
   - Remove generic filler

4. **Vector Retrieval:**
   - Build search queries (hardcoded + AI-generated)
   - Query ChromaDB for similar keywords
   - Merge and rank by similarity + score
   - Return top 60 candidates

5. **Keyword Selection:**
   - LLM selects TOP 10 from 60 candidates
   - Prioritizes search volume (score)
   - Allows overlap with existing title
   - Auto-fallback if AI returns empty

6. **Title Composition:**
   - LLM composes title with zone structure
   - Zone A: Pure specs (no search keywords)
   - Zone B: High-volume search phrases
   - Zone C: Descriptors (fragrance, style)
   - Progressive temperature retries (0.2 → 0.5)

7. **Post-Processing:**
   - Enforce locked substrings exactly
   - Fix spacing issues (Inch es → Inches)
   - Remove duplicate pack counts
   - Clean pipes and spaces

8. **Extension (if needed):**
   - If < 170 chars, add remaining keywords
   - Target 190 chars for SEO

9. **Validation:**
   - Check length, brand, product, banned terms
   - Generate validation report

10. **Output:**
    - Optimized title (180-200 chars)
    - Zone breakdown
    - Validation status
    - Full execution log

---

## Anti-Hallucination Strategy

### Core Principles

1. **Source Constraint:**
   - ONLY use words from original title OR approved keywords
   - NEVER invent features, specs, or compatibility

2. **Exact Name Preservation:**
   - "Lavender" stays "Lavender" (not "Fresh")
   - "Steel" stays "Steel" (not "Metal")
   - Brand names copied exactly

3. **Locked Facts:**
   - Pack count extracted via regex, locked, enforced
   - Dimensions extracted via regex, locked, enforced
   - Post-processing ensures locked facts appear exactly once

4. **Validation at Each Step:**
   - JSON schema validation after each LLM call
   - Retry with progressive temperature if validation fails
   - Fallback to safe defaults (original title, empty list, etc.)

5. **Explicit Prompt Rules:**
   - "NEVER invent", "NEVER assume", "NEVER change descriptors"
   - Examples of good/bad behavior
   - Negative examples ("❌ BAD: Adding 'Drawstring' when not in original")

6. **Auto-Fallback Mechanisms:**
   - KeywordSelector: auto-select top 10 by score if AI returns empty
   - TitleComposer: return original title if AI fails
   - QueryPlanner: use hardcoded queries if AI fails

---

## Configuration

### Environment Variables

```bash
# Enable/disable AI pipeline
ADKRUX_USE_AI=true

# Ollama configuration
ADKRUX_OLLAMA_MODEL=deepseek-v3.1:671b-cloud
ADKRUX_OLLAMA_URL=http://localhost:11434

# Vector retrieval settings
ADKRUX_VECTOR_DEBUG=true
ADKRUX_AI_VECTOR_ROUNDS=1
ADKRUX_VECTOR_LIMIT_PER_QUERY=25
ADKRUX_VECTOR_MAX_CANDIDATES=60
```

### Model Selection Rationale

**Why DeepSeek-v3.1 over GLM-4.6:**
- Better JSON instruction following
- More consistent schema compliance
- Lower hallucination rate
- Stronger reasoning for zone classification

**Progressive Temperature Strategy:**
- Start at 0.2 (deterministic, strict)
- Increase to 0.5 if parsing fails (allow creativity)
- 3-4 retry attempts per agent call

---

## Logging and Debugging

### RunLogger Output

Each run creates a timestamped directory under `runs/`:

```
runs/20251231_010033_shalimar-premium-lavender-fragrance-scen/
├── truth_locked.json          # Product truth + locked facts
├── concepts.json               # Parsed concepts from original title
├── category.json               # Category detection results
├── retrieval.json              # Vector retrieval queries + top results
├── selected_keywords.json      # TOP 10 selected keywords with zones
├── draft.json                  # Title composition with zone breakdown
└── final.json                  # Final optimized title + validation
```

### Key Metrics

- **Original Length:** Character count of input title
- **Final Length:** Character count of output title (target: 180-200)
- **Agents Used:** List of agents invoked (shows execution path)
- **Selected Keywords:** Number and list of selected keywords
- **Validation Issues:** Any warnings or errors
- **Zone Breakdown:** Character distribution across zones

---

## Testing and Quality Assurance

### Test Cases

1. **Garbage Bags (Scented):**
   - High-volume phrase: "garbage bags medium size" (0.4167)
   - Zone B should use complete phrase
   - No hallucinated features (no "Drawstring" if not in original)
   - Exact fragrance name ("Lavender" not "Fresh")

2. **Motorcycle Parts:**
   - Technical specs in Zone A
   - Search phrases in Zone B
   - No cross-category keywords

3. **Short Titles (<100 chars):**
   - TitleExtender should activate
   - Adds remaining high-volume keywords
   - Maintains natural flow

4. **No Brand:**
   - System handles missing brand gracefully
   - Zone A starts with product type

### Known Issues and Solutions

**Issue 1: Pack count repetition**
- **Symptom:** `120 Bags (30x4) (30x4)`
- **Solution:** Post-processing regex removes duplicates

**Issue 2: Spacing artifacts**
- **Symptom:** `Inch es`, `Roll s`
- **Solution:** Post-processing normalizes spacing

**Issue 3: Empty selected_keywords**
- **Symptom:** AI rejects all keywords
- **Solution:** Auto-fallback selects top 10 by score

**Issue 4: Low-volume synonyms**
- **Symptom:** Uses "trash bags" (0.006) instead of "garbage bags medium size" (0.4167)
- **Solution:** Enhanced prompt with score comparisons and explicit volume-driven rules

---

## Future Improvements

1. **A/B Testing Framework:**
   - Compare different zone allocations (40/40/20 vs 30/50/20)
   - Test different temperature strategies

2. **Feedback Loop:**
   - Track CTR and conversion for optimized titles
   - Retrain keyword scores based on performance

3. **Category-Specific Prompts:**
   - Customize zone definitions per category
   - Electronics: emphasize compatibility
   - Food: emphasize flavor/ingredients

4. **Multi-Language Support:**
   - Extend to non-English markets
   - Locale-specific search priorities

5. **Real-Time Keyword Updates:**
   - Refresh ChromaDB with latest search trends
   - Seasonal keyword boosts

---

## Conclusion

This multi-agent architecture successfully reduces hallucinations by:
- Breaking complex optimization into specialized, validated steps
- Enforcing source constraints at every stage
- Using auto-fallback mechanisms to prevent pipeline failures
- Logging all intermediate outputs for debugging

The zone-based composition (40/40/20) provides a structured approach to balancing product information, search optimization, and natural language flow.

---

**Document Version:** 1.0  
**Last Updated:** December 31, 2025  
**Author:** AdKrux Engineering Team
