# Agentic Strategy 2: Architecture Overview

This document explains the architecture of the **AI-Powered Amazon Title Optimizer** in detail.
 

## 1. High-Level Architecture

The system transforms Amazon product titles by replacing hardcoded rules with **AI-driven decisions** using a local LLM (Ollama).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Base Title: "Shalimar Premium (Lavender Fragrance) Scented..."     │   │
│  │  Truth Dict: {brand, product, size, color, count, features...}      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC OPTIMIZER                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                       │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │ │
│  │   │  AGENT 1    │    │  AGENT 2    │    │  AGENT 3    │              │ │
│  │   │  Category   │───▶│  Concept    │───▶│  Keyword    │              │ │
│  │   │  Detector   │    │  Evaluator  │    │  Ranker     │              │ │
│  │   └─────────────┘    └─────────────┘    └─────────────┘              │ │
│  │          │                  │                  │                      │ │
│  │          │                  │                  │                      │ │
│  │          └──────────────────┴──────────────────┘                      │ │
│  │                             │                                         │ │
│  │                             ▼                                         │ │
│  │                    ┌─────────────────┐                                │ │
│  │                    │    AGENT 4      │                                │ │
│  │                    │  Zone Builder   │◀───── CORE AI AGENT            │ │
│  │                    │  (Title Gen)    │                                │ │
│  │                    └─────────────────┘                                │ │
│  │                             │                                         │ │
│  └─────────────────────────────┼─────────────────────────────────────────┘ │
│                                │                                           │
│                                ▼                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    POST-PROCESSING                                    │ │
│  │   • Enforce locked substrings (pack strings, dimensions)              │ │
│  │   • Fix word artifacts (Inch es → Inches)                             │ │
│  │   • Validate length (≤200 chars)                                      │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Optimized Title: "Shalimar Scented Garbage Bags Medium 19x21..."   │   │
│  │  Report: {zones, reasoning, keywords_used...}                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### 2.1 Entry Point: `agentic_main.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                     agentic_main.py                             │
├─────────────────────────────────────────────────────────────────┤
│  • Sets environment: ADKRUX_USE_AI=true                         │
│  • Creates AgenticOptimizer instance                            │
│  • Runs test cases OR single title optimization                 │
│  • Prints summary report                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                 create_agentic_optimizer()
                              │
                              ▼
                    AgenticOptimizer.optimize()
```

### 2.2 Core Engine: `agentic_optimizer.py`

This is the brain of the system. It contains 4 AI Agents that work sequentially:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgenticOptimizer Class                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INITIALIZATION                                                             │
│  ├── Connect to Ollama LLM (default: deepseek-v3.1:671b-cloud)             │
│  ├── Initialize KeywordDB (vector search)                                  │
│  └── Set retrieval parameters (rounds, limits, debug flags)                │
│                                                                             │
│  MAIN METHOD: optimize(title, truth)                                        │
│  │                                                                          │
│  │   1. Extract locked substrings (pack strings, dimensions)                │
│  │                     ▼                                                    │
│  │   2. AGENT 1: detect_category(title, truth)                              │
│  │      └── Returns: {category, subcategory, search_priorities}             │
│  │                     ▼                                                    │
│  │   3. Parse title into concepts using parser.py                           │
│  │                     ▼                                                    │
│  │   4. Multi-query vector retrieval                                        │
│  │      ├── Build queries from truth + category info                        │
│  │      ├── AI suggests additional queries (optional rounds)                │
│  │      └── Merge & deduplicate candidates                                  │
│  │                     ▼                                                    │
│  │   5. AGENT 3: rank_keywords(concepts, db_results, context)               │
│  │      └── Returns: Top 5 keywords with reasons                            │
│  │                     ▼                                                    │
│  │   6. AGENT 4: build_optimized_title(truth, concepts, keywords)           │
│  │      └── Returns: {full_title, zone_a, zone_b, zone_c, reasoning}        │
│  │                     ▼                                                    │
│  │   7. Enforce locked substrings & post-process                            │
│  │                     ▼                                                    │
│  │   8. Return (optimized_title, report)                                    │
│  │                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 4 AI Agents

### Agent 1: Category Detector

**Purpose**: Identify product category without hardcoded rules.

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT 1: Category Detector                   │
├─────────────────────────────────────────────────────────────────┤
│  INPUT:                                                         │
│  ├── Title: "Shalimar Premium Garbage Bags..."                  │
│  └── Truth: {brand, product, size, color}                       │
│                                                                 │
│  LLM PROMPT:                                                    │
│  "You are an Amazon product categorization expert..."           │
│                                                                 │
│  OUTPUT:                                                        │
│  {                                                              │
│    "category": "home_storage",                                  │
│    "subcategory": "garbage_bags",                               │
│    "key_attributes": ["scented", "medium", "kitchen"],          │
│    "search_priorities": ["scent", "size", "room", "count"],     │
│    "color_important": false                                     │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Agent 2: Concept Evaluator

**Purpose**: Context-aware keep/remove decisions for concepts like "Premium", "Scented".

```
┌─────────────────────────────────────────────────────────────────┐
│                   AGENT 2: Concept Evaluator                    │
├─────────────────────────────────────────────────────────────────┤
│  INPUT:                                                         │
│  ├── Concept: "Premium"                                         │
│  ├── Type: "quality_marker"                                     │
│  └── Context: {product, brand, category, existing_concepts}     │
│                                                                 │
│  DECISION LOGIC (via LLM):                                      │
│  ├── Is "Premium" a common search term for garbage bags? → Yes  │
│  ├── Is this a high-end product? → Check pricing signals        │
│  └── Does it add search value? → Evaluate                       │
│                                                                 │
│  OUTPUT:                                                        │
│  {                                                              │
│    "keep": true,                                                │
│    "value_score": 0.65,                                         │
│    "position": "zone_b",                                        │
│    "reason": "Premium is searched for garbage bags"             │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Agent 3: Keyword Ranker

**Purpose**: Select best keywords from vector DB results.

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT 3: Keyword Ranker                      │
├─────────────────────────────────────────────────────────────────┤
│  INPUT:                                                         │
│  ├── Current concepts: ["Shalimar", "Garbage Bags", "Medium"]   │
│  ├── Vector DB candidates (top 20):                             │
│  │   ├── "scented garbage bags medium" (sim=0.92, score=0.85)   │
│  │   ├── "dustbin bags for kitchen" (sim=0.88, score=0.72)      │
│  │   └── ...                                                    │
│  └── Context: {product, brand, category}                        │
│                                                                 │
│  SELECTION CRITERIA:                                            │
│  ├── Adds NEW search value (not rearrangement)                  │
│  ├── Highly relevant to product                                 │
│  ├── Appears in multiple hit_queries (robust)                   │
│  └── No cross-category leakage                                  │
│                                                                 │
│  OUTPUT:                                                        │
│  [                                                              │
│    {"keyword": "dustbin bags", "reason": "synonym coverage"},   │
│    {"keyword": "trash bags kitchen", "reason": "use-case"},     │
│    ...                                                          │
│  ]                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Agent 4: Zone Builder (CORE)

**Purpose**: Build the final optimized title using 3-zone structure.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AGENT 4: Zone Builder                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ZONE STRUCTURE:                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ZONE A (40% = ~80 chars): DECISION ZONE                             │   │
│  │ ├── What users see first in search results                          │   │
│  │ ├── Brand + Product + Key Differentiators                           │   │
│  │ └── Order by SEARCH PRIORITY (not alphabetical)                     │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ ZONE B (40% = ~80 chars): SEO ZONE                                  │   │
│  │ ├── Synonyms of product type from Vector DB                         │   │
│  │ ├── Repetition ALLOWED if high-value search term                    │   │
│  │ └── No brand repetition                                             │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ ZONE C (20% = ~40 chars): DETAILS ZONE                              │   │
│  │ ├── Color (if not in Zone A)                                        │   │
│  │ ├── Remaining features                                              │   │
│  │ └── Low-priority attributes                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  CRITICAL RULES ENFORCED:                                                   │
│  ├── NO PIPES (|) - use natural phrasing                                   │
│  ├── Locked strings (pack, dimension) copied EXACTLY                       │
│  ├── Brand appears ONLY ONCE (Zone A)                                      │
│  ├── Color can be placed at END if visible in image                        │
│  └── Target 180-200 chars                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Diagram

```
                    ┌──────────────────────┐
                    │    User Input        │
                    │  (Title + Truth)     │
                    └──────────┬───────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           STEP 1: PARSING                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  parser.py                                                              │ │
│  │  ├── Extract BRAND, PRODUCT, SIZE, COLOR, COUNT...                     │ │
│  │  ├── Handle parentheses content as single concepts                     │ │
│  │  └── Mark truth-critical tokens as LOCKED                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        STEP 2: CATEGORY DETECTION                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AGENT 1 (LLM Call)                                                     │ │
│  │  ├── Analyze title + truth                                              │ │
│  │  ├── Detect: home_storage / garbage_bags                                │ │
│  │  └── Return search_priorities: [scent, size, count...]                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    STEP 3: VECTOR KEYWORD RETRIEVAL                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  keyword_db.py + AI Query Expansion                                     │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │ │
│  │  │ Build Queries   │───▶│ Vector Search   │───▶│ Merge Results   │     │ │
│  │  │ from Truth      │    │ (153k keywords) │    │ & Deduplicate   │     │ │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘     │ │
│  │         │                                                               │ │
│  │         ▼                                                               │ │
│  │  ┌─────────────────┐                                                    │ │
│  │  │ AI Suggests     │ ◀── Optional: LLM proposes broader queries         │ │
│  │  │ More Queries    │                                                    │ │
│  │  └─────────────────┘                                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      STEP 4: KEYWORD RANKING                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AGENT 3 (LLM Call)                                                     │ │
│  │  ├── Input: 20 keyword candidates + current concepts                   │ │
│  │  ├── Filter: cross-category leakage, redundancy                        │ │
│  │  └── Output: Top 5 keywords with reasons                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      STEP 5: TITLE GENERATION                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AGENT 4 (LLM Call) - THE CORE AGENT                                    │ │
│  │  ├── Input: truth, concepts, ranked keywords, category info            │ │
│  │  ├── Build Zone A (decision), Zone B (SEO), Zone C (details)           │ │
│  │  ├── Apply search-driven ordering                                      │ │
│  │  └── Output: full_title + zone breakdown + reasoning                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      STEP 6: POST-PROCESSING                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  _enforce_locked_substrings()                                           │ │
│  │  ├── Ensure pack string is exact: "120 Bags (30 Bags x 4 Rolls)"       │ │
│  │  ├── Ensure dimension is exact: "19 x 21 Inches"                       │ │
│  │  ├── Fix word artifacts: "Inch es" → "Inches"                          │ │
│  │  └── Clean whitespace and punctuation                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Final Output      │
                    │  (Optimized Title)   │
                    └──────────────────────┘
```

---

## 5. Supporting Components

### 5.1 Vector Database: `keyword_db.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                      KeywordDB                                  │
├─────────────────────────────────────────────────────────────────┤
│  Storage: st_keywords_index/keywords_index.npz                  │
│  ├── embeddings: (153,459 x 384) float32 array                  │
│  ├── keywords: string array                                     │
│  ├── scores: float32 array (importance)                         │
│  ├── ad_units: float32 array (search volume proxy)              │
│  └── dataset_ids: string array (source dataset)                 │
│                                                                 │
│  Embedding Model: all-MiniLM-L6-v2 (SentenceTransformers)       │
│  Similarity: Cosine (via dot product of L2-normalized vectors)  │
│                                                                 │
│  METHOD: get_top_keywords(query, limit=25)                      │
│  ├── Encode query to 384-dim vector                             │
│  ├── Compute similarity with all 153k keywords                  │
│  └── Return top-N results with scores                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 AI Validator: `ai_validator.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                   AIKeywordValidator                            │
├─────────────────────────────────────────────────────────────────┤
│  PURPOSE: Validate individual keyword relevance                 │
│                                                                 │
│  METHOD: validate_keyword(keyword, product_context)             │
│  ├── Build validation prompt                                    │
│  ├── Call Ollama LLM                                            │
│  └── Return: {is_relevant, confidence, reason}                  │
│                                                                 │
│  REJECTION CRITERIA:                                            │
│  ├── Different product type                                     │
│  ├── Different category                                         │
│  ├── Redundant (already in title)                               │
│  └── Just rearrangement of existing words                       │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Parser: `parser.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                      TitleParser                                │
├─────────────────────────────────────────────────────────────────┤
│  PURPOSE: Extract typed concepts from title                     │
│                                                                 │
│  TOKEN TYPES EXTRACTED:                                         │
│  ├── BRAND      (locked, value=100, tier=0)                     │
│  ├── PRODUCT    (locked, value=90, tier=0)                      │
│  ├── SIZE       (locked, value=75, tier=1)                      │
│  ├── COLOR      (locked, value=70, tier=1)                      │
│  ├── COUNT      (locked, value=80, tier=1)                      │
│  ├── DIMENSION  (value=60, tier=2)                              │
│  ├── FRAGRANCE  (value=40, tier=2)                              │
│  ├── FEATURE    (value=35, tier=2)                              │
│  ├── QUALITY_MARKER (value=5, tier=3) ← Usually evicted         │
│  └── OTHER      (value=10, tier=3)                              │
│                                                                 │
│  SPECIAL HANDLING:                                              │
│  ├── Parentheses content as single concept                      │
│  ├── Material phrases kept together (e.g., "Plastic Bucket")    │
│  └── Compatibility patterns (e.g., "for Honda Pulsar")          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. LLM Integration

### Ollama Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ollama Integration                           │
├─────────────────────────────────────────────────────────────────┤
│  DEFAULT MODEL: deepseek-v3.1:671b-cloud                        │
│  BASE URL: http://localhost:11434                               │
│  API ENDPOINT: /api/generate                                    │
│                                                                 │
│  ENVIRONMENT VARIABLES:                                         │
│  ├── ADKRUX_USE_AI=true              (enable AI)                │
│  ├── ADKRUX_OLLAMA_MODEL=...         (model name)               │
│  ├── ADKRUX_OLLAMA_URL=...           (server URL)               │
│  ├── ADKRUX_AI_VECTOR_ROUNDS=1       (AI query expansion)       │
│  ├── ADKRUX_VECTOR_LIMIT_PER_QUERY=25 (results per query)       │
│  └── ADKRUX_VECTOR_MAX_CANDIDATES=60 (total candidates)         │
│                                                                 │
│  PROMPT ENGINEERING:                                            │
│  ├── Temperature: 0.1-0.2 (deterministic)                       │
│  ├── Max tokens: 200-800 (depending on agent)                   │
│  ├── Structured JSON output required                            │
│  └── Few-shot examples embedded in prompts                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Example Transformation

### Input
```
Title: "Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | 
        Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | 
        Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing"

Truth: {
    brand: "Shalimar",
    product: "Garbage Bags",
    size: "Medium",
    color: "Black",
    count: "120 Bags (30 x 4 Rolls)",
    dimension: "19 x 21 Inches"
}
```

### Agent Processing

```
AGENT 1 → Category: home_storage/garbage_bags
          Search priorities: [scented, size, count, room]

AGENT 3 → Selected keywords:
          ✓ "dustbin bags" - synonym coverage
          ✓ "trash bags kitchen" - use-case
          ✓ "medium garbage bags" - size+product

AGENT 4 → Zone construction:
          Zone A: "Shalimar Scented Garbage Bags Medium 19x21 Inches 120 Bags"
          Zone B: "(30 Bags x 4 Rolls) Premium Dustbin Bags for Kitchen"
          Zone C: "Lavender Fragrance Trash Bag Black"
```

### Output
```
"Shalimar Scented Garbage Bags Medium 19x21 Inches 120 Bags (30 Bags x 4 Rolls) 
 Premium Dustbin Bags for Kitchen Lavender Fragrance Trash Bag Black"

Length: ~145-180 chars
Char saved: ~30-50 chars (pipes removed, natural phrasing)
```

---

## 8. File Structure

```
agentic_strategy_2/
├── agentic_main.py         # Entry point
├── agentic_optimizer.py    # Core optimizer with 4 AI agents
├── ai_validator.py         # Keyword validation agent
├── parser.py               # Title parsing (concept extraction)
├── keyword_db.py           # Vector database interface
├── token_types.py          # Token/Concept type definitions
├── normalizer.py           # Text normalization utilities
├── st_keywords_index/      # Vector database storage
│   └── keywords_index.npz  # 153k keyword embeddings
├── ALGORITHM_EXPLAINED.txt # Detailed algorithm documentation
├── AGENTIC_TRANSFORMATION_PLAN.txt # Roadmap document
└── requirements.txt        # Dependencies
```

---

## 9. Key Design Decisions

| Decision | Rule-Based (Old) | Agentic (New) |
|----------|-----------------|---------------|
| Remove "Premium" | Always remove | Ask AI: "Is it valuable here?" |
| Remove "Scented" | Remove if fragrance exists | Keep - it's a top search term |
| Keyword ordering | Fixed: Brand→Product→Size | Search-driven priority |
| Context detection | Hardcoded rules | AI infers from title/truth |
| Cross-category filter | Manual word lists | AI rejects automatically |
| Title structure | Pipes required | Natural phrasing |

---

## 10. Summary

The **Agentic Strategy 2** transforms Amazon title optimization from a rigid, rule-based system to an intelligent, AI-driven pipeline. The key insight is that **search behavior patterns cannot be hardcoded** — they must be learned from data and context.

The 4-agent architecture provides:
1. **Flexibility**: Works across any product category
2. **Intelligence**: Context-aware decisions
3. **Quality**: Search-optimized, natural-sounding titles
4. **Maintainability**: No hardcoded rules to update

 
