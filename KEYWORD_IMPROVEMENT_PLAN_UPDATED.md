
# Keyword Selection & Title Composition Improvement Plan (UPDATED)

## 🎯 Current Problems Identified

### 1. **KeywordSelectorAgent Issues:**
- ❌ **Wrongly rejects high-volume keywords** just because they appear in original title
- ❌ **Poor zone strategy** - doesn't prioritize decision-making vs SEO vs details
- ❌ **Ignores search volume priority** - focuses on "newness" instead of performance
- ❌ **No strategic phrase placement** - misses high-volume term combinations

### 2. **TitleComposerAgent Issues:**
- ❌ **No proper 40/40/20 zone structure** - doesn't follow strategic placement
- ❌ **No strategic keyword repetition** - misses high-volume term placement
- ❌ **Poor attribute placement** - doesn't consider decision vs SEO vs details

## 🚀 Proposed Solutions

### **Phase 1: Strategic Zone-Based Keyword Selection**

#### **Zone Strategy (CORRECTED):**

**Zone A (40% - Decision Zone):**
- **Purpose**: What users see FIRST in search results - decides if they click
- **Content**: Brand + Core Product + Key Differentiators
- **Examples**: 
  - High-volume size terms: "medium", "large", "small", "xl"
  - Brand + product combinations: "shalimar garbage bags"
  - Critical specifications: "19x21 inches", "120 bags", "pack of 30"

**Zone B (40% - SEO Power Zone):**
- **Purpose**: Most searched phrases and high-volume terms
- **Content**: SEO-optimized phrases and synonyms
- **Examples**:
  - Most searched synonyms: "garbage bags", "trash bags", "dustbin bags"
  - Category-specific high-volume terms: "kitchen trash bags", "heavy duty bags"
  - Feature combinations: "leak proof garbage bags", "scented trash bags"
  - **High-value attributes as phrases**: "premium quality", "heavy duty material"

**Zone C (20% - Details Zone):**
- **Purpose**: Supporting details and long-tail terms
- **Content**: Colors, fragrances, minor features
- **Examples**:
  - Colors: "black", "white", "green"
  - Fragrances: "lavender", "citrus", "unscented"
  - Minor features: "perforated box", "easy dispensing"
  - Long-tail keywords: "for kitchen use", "biodegradable option"

#### **New KeywordSelectorAgent Logic:**
1. **Search Volume Priority**: Rank by `score * similarity` first
2. **Zone Classification**: Categorize keywords for specific zones
3. **Strategic Duplication**: Allow high-volume terms in multiple zones
4. **Phrase Integration**: Include attribute combinations in Zone B

#### **Zone Classification Rules:**
```python
ZONE_A_KEYWORDS = {
    # High-volume size terms (key decision factors)
    'medium', 'large', 'small', 'xl', 'extra large', 'jumbo',
    # Brand + product combinations  
    'shalimar garbage bags', 'brand product combo',
    # Critical specs
    '19x21', '19 x 21', '120 bags', 'pack of', '30x4 rolls'
}

ZONE_B_KEYWORDS = {
    # Most searched synonyms
    'garbage bags', 'trash bags', 'dustbin bags', 'waste bags',
    # High-volume phrases
    'kitchen trash bags', 'heavy duty garbage bags', 'leak proof bags',
    # Category-specific terms
    'home storage bags', 'kitchen garbage bags', 'heavy duty trash'
}

ZONE_C_KEYWORDS = {
    # Colors and fragrances
    'black', 'white', 'lavender', 'citrus', 'unscented',
    # Minor features
    'perforated box', 'easy dispensing', 'biodegradable'
}
```

### **Phase 2: Enhanced Title Composition Logic**

#### **New 40/40/20 Zone Structure:**

**Zone A (40% - First 80 chars): DECISION ZONE**
```
Example: "Shalimar Garbage Bags Medium 19x21 Inches 120 Bags"
- Brand + Product + Size + Critical Spec
- What users see and decide to click on
```

**Zone B (40% - Next 80 chars): SEO POWER ZONE**
```
Example: "(30x4 Rolls) Premium Heavy Duty Trash Bags Kitchen Dustbin Bags"
- High-volume phrases + synonyms + category terms
- Maximum search coverage with most searched terms
- Attribute combinations as phrases
```

**Zone C (20% - Last 40 chars): DETAILS ZONE**
```
Example: "Black Lavender Fragrance Perforated Box Easy Dispensing"
- Colors + fragrances + minor features
- Supporting details for completeness
```

#### **Strategic Repetition Logic:**
- **"Medium"** appears in Zone A (key decision) + Zone B (high-volume search)
- **"Garbage bags"** base term + **"trash bags"** synonym in Zone B
- **"Heavy duty"** as phrase in Zone B for high search volume

### **Phase 3: Enhanced Prompt Engineering**

#### **New KeywordSelector Prompt:**
```python
prompt = f"""You are an Amazon SEO expert optimizing for STRATEGIC ZONE PLACEMENT.

ZONE STRATEGY:
- Zone A (40%): Key decision factors (size, brand+product, specs)
- Zone B (40%): Most searched phrases and high-volume terms  
- Zone C (20%): Supporting details (color, fragrance, minor features)

PRIORITY ORDER:
1. SEARCH VOLUME (highest score * similarity wins)
2. STRATEGIC ZONE PLACEMENT (decision vs SEO vs details)
3. PHRASE OPTIMIZATION (combine attributes for Zone B)

EXAMPLES:
- "medium" → Zone A (decision factor) + Zone B (high-volume search)
- "garbage bags" + "trash bags" → Zone B (synonym coverage)
- "heavy duty" → Zone B as phrase (high search volume)

CANDIDATES: {candidates}
EXISTING: {existing_concepts}

CLASSIFY each candidate as:
- ZONE_A: Brand+product, size terms, critical specs
- ZONE_B: High-volume phrases, synonyms, category terms  
- ZONE_C: Colors, fragrances, minor features

Respond JSON:"""
```

#### **New TitleComposer Prompt:**
```python
prompt = f"""Create a strategic 3-zone title structure:

ZONE A (40% - Decision Zone): {zone_a_keywords}
Brand + Core Product + Key Differentiators (size, specs)
What users see first to decide to click

ZONE B (40% - SEO Power Zone): {zone_b_keywords}
High-volume phrases + synonyms + category terms
Most searched terms and combinations

ZONE C (20% - Details Zone): {zone_c_keywords}
Colors + fragrances + minor features
Supporting details

REQUIREMENTS:
- Total: 180-200 characters
- Strategic repetition of high-volume terms across zones
- Use phrase combinations for Zone B (e.g., "heavy duty material")
- Zone A: immediate decision makers
- Zone B: maximum search coverage
- Zone C: supporting details

ORIGINAL: {original_title}
TRUTH: {truth}

Respond: {{"zones": {{"a": "...", "b": "...", "c": "..."}}, "full_title": "..."}}"""
```

## 📋 Implementation Steps

### **Step 1: Update KeywordSelectorAgent**
- [ ] Remove "avoid duplicates" logic
- [ ] Add zone-based classification (A/B/C)
- [ ] Implement search volume prioritization
- [ ] Add phrase combination logic for Zone B
- [ ] Allow strategic repetition across zones

### **Step 2: Enhance TitleComposerAgent** 
- [ ] Implement proper 40/40/20 zone structure
- [ ] Add strategic repetition logic
- [ ] Create zone-specific keyword placement
- [ ] Support phrase combinations in Zone B

### **Step 3: Update Pipeline Integration**
- [ ] Modify agent communication to include zone data
- [ ] Add zone validation logic
- [ ] Update logging to track zone distribution

### **Step 4: Testing & Validation**
- [ ] Test with sample garbage bags
- [ ] Verify zone distribution (40/40/20)
- [ ] Check character limits
- [ ] Validate decision vs SEO vs details logic

## 🎯 Expected Results

### **Before (Current):**
```
"Shalimar Scented Garbage Bags Medium 19x21" 120 Bags (30x4 Rolls) 
Premium Dustbin Bags Kitchen Lavender Fragrance Trash Bag Black"
```

### **After (Improved):**
```
Zone A (40%): "Shalimar Garbage Bags Medium 19x21 Inches 120 Bags"
Zone B (40%): "(30x4 Rolls) Premium Heavy Duty Trash Bags Kitchen Dustbin Bags"  
Zone C (20%): "Black Lavender Fragrance Perforated Box Easy Dispensing"

Full Title: "Shalimar Garbage Bags Medium 19x21 Inches 120 Bags (30x4 Rolls) Premium Heavy Duty Trash Bags Kitchen Dustbin Bags Black Lavender Fragrance Perforated Box Easy Dispensing"
```

**Key Improvements:**
✅ **Strategic "medium" placement** - Zone A (decision) + Zone B (search)  
✅ **Better phrase optimization** - "heavy duty trash bags" as single phrase  
✅ **Zone-based structure** - 40/40/20 with clear purpose  
✅ **Volume-prioritized** - high-score terms get strategic placement  
✅ **SEO optimized** - most searched phrases in Zone B for maximum coverage  
✅ **Decision-focused** - Zone A contains immediate decision factors  

---

## 🔧 Technical Changes Required

### **Files to Modify:**
1. `agentic_agents.py` - KeywordSelectorAgent + TitleComposerAgent
2. `agentic_pipeline.py` - Agent integration logic
3. `agentic_validators.py` - Zone-based validation

### **New Data Structures:**
```python
class KeywordZone:
    ZONE_A = "zone_a"  # Decision factors (brand+product+size+specs)
    ZONE_B = "zone_b"  # SEO power (high-volume phrases+synonyms)
    ZONE_C = "zone_c"  # Details (color+fragrance+minor features)

class SelectedKeyword:
    keyword: str
    zone: str
    reason: str
    priority: float  # score * similarity
    is_phrase: bool  # for Zone B combinations
```

### **Zone Classification Logic:**
```python
def classify_keyword_zone(keyword: str, context: Dict) -> str:
    keyword_lower = keyword.lower()
    
    # ZONE A: Decision factors
    if any(term in keyword_lower for term in ['medium', 'large', 'small', 'xl']):
        return "zone_a"
    if any(term in keyword_lower for term in ['19x21', '120 bags', 'pack of']):
        return "zone_a"
    
    # ZONE B: High-volume phrases and synonyms
    if any(term in keyword_lower for term in ['garbage', 'trash', 'dustbin']):
        return "zone_b"
    if ' ' in keyword_lower:  # Multi-word phrases go to Zone B
        return "zone_b"
    
    # ZONE C: Details
    return "zone_c"
```

This updated approach ensures:
- **Zone A**: Immediate decision makers (what users see first)
- **Zone B**: Maximum SEO coverage with most searched phrases
- **Zone C**: Supporting details for completeness

Ready to implement this strategic approach! 🚀

