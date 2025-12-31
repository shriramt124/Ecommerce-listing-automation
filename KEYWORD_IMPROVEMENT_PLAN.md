# Keyword Selection & Title Composition Improvement Plan

## 🎯 Current Problems Identified

### 1. **KeywordSelectorAgent Issues:**
- ❌ **Wrongly rejects high-volume keywords** just because they appear in original title
- ❌ **Ignores search volume priority** - focuses on "newness" instead of performance
- ❌ **Poor zone-based placement** - no strategic positioning
- ❌ **Limited synonym handling** - doesn't use "garbage/trash" pattern

### 2. **TitleComposerAgent Issues:**
- ❌ **No proper zone structure** - doesn't follow 40/40/20 rule
- ❌ **No strategic keyword repetition** - misses high-volume term placement
- ❌ **Poor attribute placement** - puts fragrance at end instead of strategically

## 🚀 Proposed Solutions

### **Phase 1: Enhanced Keyword Selection Logic**

#### **New KeywordSelectorAgent Approach:**
1. **Search Volume Priority**: Rank by `score * similarity` first, not "newness"
2. **Strategic Duplication**: Allow repetition of high-performing keywords
3. **Zone Classification**: Categorize keywords for specific zones
4. **Synonym Grouping**: Group related terms (garbage/trash/dustbin)

#### **New Selection Criteria:**
```python
PRIORITY 1 (Zone A): Key Differentiators
- High-volume size terms (medium, large, small)
- Brand + core product combinations
- Critical specifications

PRIORITY 2 (Zone B): SEO Power Terms  
- Most searched synonyms (garbage/trash)
- Category-specific high-volume terms
- Feature combinations

PRIORITY 3 (Zone C): Supporting Details
- Colors, fragrances, minor features
- Long-tail keywords
```

### **Phase 2: Zone-Based Title Composition**

#### **New 40/40/20 Zone Structure:**

**Zone A (40% - First 80 chars):**
- Brand + Core Product + Key Differentiator
- Example: `shalimar scented garbage bags medium`

**Zone B (40% - Next 80 chars):**
- High-volume SEO terms + Synonyms + Details  
- Example: `19*21 inches 120bags(30bags*4rolls) premium Black garbage bags medium size`

**Zone C (20% - Last 40 chars):**
- Fragrance + Features + Minor details
- Example: `with Lavender fragrence and perforated box for easy despensing`

#### **Strategic Keyword Repetition:**
- **"Medium"** appears in both Zone A (key differentiator) and Zone B (high-volume)
- **"Garbage bags"** base term + **"trash bags"** synonym in different zones
- **"Size"** variations for search coverage

### **Phase 3: Enhanced Prompt Engineering**

#### **New KeywordSelector Prompt:**
```python
prompt = f"""You are an Amazon SEO expert optimizing for SEARCH VOLUME and STRATEGIC PLACEMENT.

PRIORITY ORDER:
1. SEARCH VOLUME (highest score * similarity wins)
2. STRATEGIC VALUE (key differentiators for Zone A)
3. SYNONYM COVERAGE (garbage/trash for broader search)
4. ZONE OPTIMIZATION (different keywords for different zones)

AVOID: Generic terms, duplicates within same zone
EMBRACE: High-volume terms, strategic repetition across zones

CANDIDATES: {candidates}
EXISTING: {existing_concepts}
TARGET: {target_keywords}

CLASSIFY each candidate as:
- ZONE_A: Key differentiators (brand+product+size)
- ZONE_B: SEO power terms (high-volume, synonyms)
- ZONE_C: Supporting details (color, fragrance, features)

Respond JSON:"""
```

#### **New TitleComposer Prompt:**
```python
prompt = f"""Create a strategic 3-zone title structure:

ZONE A (40%): {zone_a_keywords}
Brand + Core Product + Key Differentiator

ZONE B (40%): {zone_b_keywords}  
High-volume SEO terms + Synonyms + Specifications

ZONE C (20%): {zone_c_keywords}
Fragrance + Features + Minor details

REQUIREMENTS:
- Total: 180-200 characters
- Strategic repetition of high-volume terms
- Use slash syntax for synonyms: "garbage/trash bags"
- Place critical specs (size) in multiple zones

ORIGINAL: {original_title}
TRUTH: {truth}

Respond: {{"zones": {{"a": "...", "b": "...", "c": "..."}}, "full_title": "..."}}"""
```

## 📋 Implementation Steps

### **Step 1: Update KeywordSelectorAgent**
- [ ] Remove "avoid duplicates" logic
- [ ] Add zone-based classification
- [ ] Implement search volume prioritization
- [ ] Add synonym grouping

### **Step 2: Enhance TitleComposerAgent** 
- [ ] Implement 3-zone structure
- [ ] Add strategic repetition logic
- [ ] Create zone-specific keyword placement
- [ ] Add slash syntax for synonyms

### **Step 3: Update Pipeline Integration**
- [ ] Modify agent communication
- [ ] Add zone data to agent outputs
- [ ] Update validation logic
- [ ] Enhance logging

### **Step 4: Testing & Validation**
- [ ] Test with sample garbage bags
- [ ] Verify zone distribution
- [ ] Check character limits
- [ ] Validate SEO improvements

## 🎯 Expected Results

### **Before (Current):**
```
"Shalimar Scented Garbage Bags Medium 19x21" 120 Bags (30x4 Rolls) 
Premium Dustbin Bags Kitchen Lavender Fragrance Trash Bag Black"
```

### **After (Improved):**
```
shalimar scented garbage bags medium 19*21 inches,120bags(30bags*4rolls) 
,premium Black garbage bags medium size with Lavender fragrence 
and perforated box for easy despensing
```

**Key Improvements:**
✅ **Strategic "medium" placement** - appears in both Zone A and B  
✅ **Better synonym coverage** - "garbage/trash" for broader search  
✅ **Zone-based structure** - clear 40/40/20 distribution  
✅ **Volume-prioritized** - high-score terms get multiple placements  
✅ **SEO optimized** - critical terms repeated for search coverage  

---

## 🔧 Technical Changes Required

### **Files to Modify:**
1. `agentic_agents.py` - KeywordSelectorAgent + TitleComposerAgent
2. `agentic_pipeline.py` - Agent integration logic
3. `agentic_validators.py` - Zone-based validation

### **New Data Structures:**
```python
class KeywordZone:
    ZONE_A = "zone_a"  # Brand + Product + Key Differentiation
    ZONE_B = "zone_b"  # SEO + Synonyms + Volume  
    ZONE_C = "zone_c"  # Details + Features + Minor

class SelectedKeyword:
    keyword: str
    zone: str
    reason: str
    priority: float  # score * similarity
```

Ready to implement? This will transform the system from a basic "avoid duplicates" approach to a sophisticated **search-volume-driven, zone-optimized** strategy! 🚀

