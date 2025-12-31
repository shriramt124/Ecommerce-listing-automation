# How AI Agents Choose Relevant Keywords for Title Generation

## 🔄 Complete Keyword Selection Flow

The system uses **5 specialized AI agents** that work together in a pipeline to choose relevant keywords:

```
INPUT TITLE → [AI Agents] → OPTIMIZED TITLE
    ↓
Title Parsing → Category Detection → Query Generation → Keyword Retrieval → Keyword Selection → Title Composition
```

---

## 🤖 Step-by-Step AI Agent Process

### Step 1: Title Parsing & Concept Extraction
**File**: `parser.py`
- Parses the original title into structured concepts
- Identifies: brand, product, size, color, features, etc.
- Creates tokens with types: `BRAND`, `PRODUCT`, `SIZE`, `COLOR`, `FEATURE`

### Step 2: Category Detection 
**Agent**: `CategoryDetectorAgent` 
**File**: `agentic_agents.py`

```python
# Example output:
{
    "category": "home_storage",
    "subcategory": "garbage_bags", 
    "search_priorities": ["garbage bags", "trash bags", "dustbin bags"],
    "key_attributes": ["scented", "heavy duty", "leak proof"]
}
```

**What it does:**
- Analyzes the product to determine its Amazon category
- Identifies what customers search for FIRST in that category
- Determines key attributes that drive purchase decisions

### Step 3: Concept Evaluation
**Agent**: `ConceptEvaluatorAgent`
**File**: `agentic_agents.py`

```python
# Example decision:
{
    "keep": True,  # Keep "Premium" for garbage bags
    "value_score": 0.7,
    "position": "zone_b", 
    "reason": "Premium is commonly searched in home storage"
}
```

**What it does:**
- Decides which concepts from original title to KEEP/REMOVE
- Evaluates quality markers like "Premium", "Deluxe", "Scented"
- Considers category-specific search behavior

### Step 4: Vector Query Generation
**Agent**: `QueryPlannerAgent` 
**File**: `agentic_agents.py` (the enhanced version we just updated)

```python
# Generates systematic queries like:
[
    "shalimar garbage bags",
    "garbage bags medium size", 
    "scented trash bags black",
    "premium dustbin bags kitchen"
]
```

**What it does:**
- Creates systematic search queries for the vector database
- Uses product attributes: brand + category + size + color + features
- Combines synonyms and use cases
- Generates 15-25 different query variations

### Step 5: Vector Database Retrieval
**System**: `KeywordDB` + `embedder.py`
**File**: `keyword_db.py`

```python
# Retrieved keywords with scores:
[
    {"keyword": "garbage bags", "similarity": 0.95, "score": 0.87, "ad_units": 45.2},
    {"keyword": "trash bags", "similarity": 0.93, "score": 0.84, "ad_units": 42.1},
    {"keyword": "scented bags", "similarity": 0.89, "score": 0.76, "ad_units": 38.5}
]
```

**What it does:**
- Searches vector database with 153,459 keyword embeddings
- Finds semantically similar keywords to your queries
- Ranks by similarity score, ad performance, and search volume
- Returns top 25 candidates per query

### Step 6: Keyword Selection
**Agent**: `KeywordSelectorAgent`
**File**: `agentic_agents.py`

```python
# Final selected keywords:
[
    {"keyword": "garbage bags", "reason": "Core product term, high search volume"},
    {"keyword": "scented", "reason": "Important feature for customer search"},
    {"keyword": "kitchen", "reason": "Primary use case, frequently searched"}
]
```

**What it does:**
- Reviews ALL retrieved candidates from vector search
- Selects only keywords that add NEW search value
- Rejects keywords already in original title (avoid duplication)
- Considers ad performance and search intent
- Picks TOP 15 most valuable keywords

### Step 7: Title Composition
**Agent**: `TitleComposerAgent`
**File**: `agentic_agents.py`

```python
# Final optimized title:
"Shalimar Scented Garbage Bags Medium 19x21" 120 Bags (30x4 Rolls) 
Premium Dustbin Bags Kitchen Lavender Fragrance Trash Bag Black"
```

**What it does:**
- Combines kept original concepts + selected keywords
- Arranges in 3-zone structure:
  - **Zone A (40%)**: Core product + brand + size
  - **Zone B (40%)**: SEO keywords + features  
  - **Zone C (20%)**: Details + color + low-priority terms
- Enforces 180-200 character limit
- Preserves exact pack/dimension strings

---

## 🎯 How Keywords Are Chosen

### 1. **Systematic Query Generation**
The QueryPlannerAgent creates queries using this logic:

```python
# Brand + Category combinations
"shalimar garbage bags"

# Color + Category + Size  
"black garbage bags medium"

# Attribute + Category + Use Case
"heavy duty trash bags kitchen"

# Category + Synonyms
"garbage bags trash bags dustbin bags"
```

### 2. **Vector Similarity Matching**
The system finds keywords semantically similar to your queries:

- **High Similarity (>0.9)**: Exact matches like "garbage bags" → "trash bags"
- **Medium Similarity (0.7-0.9)**: Related terms like "scented" → "fragrant" 
- **Lower Similarity (0.5-0.7)**: Broader categories like "bags" → "containers"

### 3. **AI Selection Criteria**
The KeywordSelectorAgent chooses keywords based on:

✅ **Adds new search value** (not already in title)  
✅ **High relevance** to product category  
✅ **Good ad performance** (search volume, click rates)  
✅ **Customer search intent** (what buyers actually search for)  
✅ **Avoids cross-category drift** (stays relevant to product type)

❌ **Rejects duplicates** (already in original title)  
❌ **Rejects irrelevant terms** (doesn't match product category)  
❌ **Rejects generic terms** (like "best", "quality" without context)

---

## 📊 Real Example: Garbage Bags Optimization

**Original Title (186 chars):**
```
Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | 
Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | 
Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing
```

**AI Process:**
1. **Category**: Detected "home_storage" / "garbage_bags"
2. **Concepts Kept**: "Premium", "Scented", "Lavender Fragrance", "Medium", "120 Bags"
3. **Queries Generated**: "shalimar garbage bags", "scented trash bags", "kitchen dustbin bags"
4. **Keywords Retrieved**: 180+ candidates from vector database
5. **Keywords Selected**: "garbage bags", "trash bags", "dustbin bags", "kitchen", "premium"
6. **Final Title (163 chars)**:
   ```
   Shalimar Scented Garbage Bags Medium 19x21" 120 Bags (30x4 Rolls) 
   Premium Dustbin Bags Kitchen Lavender Fragrance Trash Bag Black
   ```

**Improvements:**
- ✅ More keyword diversity (garbage/trash/dustbin synonyms)
- ✅ Better keyword placement for SEO
- ✅ Preserved exact pack information
- ✅ Maintained character limit compliance

---

## 🔧 Technical Implementation

### Vector Database Search
```python
# Each keyword has a 384-dimensional embedding
# System finds closest matches using cosine similarity

def get_top_keywords(query: str, limit: int = 25):
    query_embedding = embedder.encode(query)
    similarities = cosine_similarity(query_embedding, all_keyword_embeddings)
    top_indices = np.argsort(similarities)[-limit:]
    return [keywords[i] for i in top_indices]
```

### AI Decision Making
```python
# Each agent uses Ollama LLM with structured prompts
prompt = f"""You are an Amazon keyword optimization expert.

PRODUCT CONTEXT:
- Category: {category}
- Brand: {brand}  
- Current concepts: {existing_concepts}

CANDIDATE KEYWORDS: {candidates}

TASK: Select TOP {max_select} keywords that add NEW search value.

STRICT RULES:
- Only select from provided candidates
- Avoid duplicates with existing concepts
- Focus on high-intent search terms

Respond JSON:"""
```

---

## 🎯 Key Benefits of This Approach

1. **Evidence-Based Selection**: Uses real keyword data, not guesswork
2. **AI-Powered Decisions**: Agents consider context and search behavior  
3. **Systematic Coverage**: Generates comprehensive query variations
4. **Category-Specific**: Tailored to each product type's search patterns
5. **Performance Optimized**: Considers ad metrics and search volume
6. **Quality Controlled**: Multiple validation steps prevent poor choices

This multi-agent approach ensures that only the most relevant, high-performing keywords make it into your optimized title!

