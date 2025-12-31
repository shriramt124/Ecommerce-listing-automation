# AdKrux Multi-Agent Title Optimization Architecture

## Visual Architecture Diagram

```mermaid
flowchart TD
    %% Styling
    classDef agentStyle fill:#ADD8E6,stroke:#333,stroke-width:2px,color:#000
    classDef dataStyle fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    classDef processStyle fill:#FFFFE0,stroke:#333,stroke-width:2px,color:#000
    classDef storageStyle fill:#F08080,stroke:#333,stroke-width:2px,color:#000
    
    %% External Systems
    subgraph ChromaDB["🗄️ ChromaDB Vector Store"]
        DB1["153,459 Keywords<br/>SentenceTransformer Embeddings<br/>Similarity Search"]
    end
    
    subgraph Ollama["☁️ Ollama LLM"]
        LLM["DeepSeek-v3.1 671b-cloud<br/>Progressive Temp: 0.2→0.5<br/>Retries: 3-4<br/>JSON Outputs"]
    end
    
    %% Input/Output
    Input["📥 INPUT<br/>Original Title<br/>Product Truth<br/>(brand, product, size, color)"]
    Output["📤 OUTPUT<br/>Optimized Title 180-200 chars<br/>Zone Structure 40/40/20<br/>Validation Report"]
    
    %% Main Pipeline
    subgraph Pipeline["🔄 Agentic Optimization Pipeline"]
        
        Agent1["🤖 CategoryDetectorAgent<br/><br/>PROMPT: Analyze product<br/>- category/subcategory<br/>- key attributes<br/>- search priorities<br/>- color importance<br/><br/>OUTPUT: category_info JSON"]
        
        Agent2["🤖 ConceptEvaluatorAgent<br/><br/>PROMPT: Evaluate terms<br/>- Keep if valuable<br/>- Reject if generic filler<br/>- Check 'premium', 'quality'<br/><br/>OUTPUT: keep: true/false"]
        
        Agent3["🤖 QueryPlannerAgent<br/><br/>PROMPT: Generate queries<br/>- Based on product type<br/>- Key attributes<br/>- Category priorities<br/><br/>OUTPUT: search queries list"]
        
        Process1["⚙️ Vector Retrieval<br/><br/>1. Execute queries on ChromaDB<br/>2. Merge results by keyword<br/>3. Rank by similarity + score<br/>4. Return top 60 candidates"]
        
        Agent4["🤖 KeywordSelectorAgent<br/><br/>PROMPT: Select TOP 10<br/>1. Prioritize HIGH VOLUME<br/>2. Complete phrases<br/>3. Allow overlap<br/>4. Classify ZONE_B/ZONE_C<br/><br/>FALLBACK: Auto-select top 10<br/><br/>OUTPUT: selected_keywords"]
        
        Agent5["🤖 TitleComposerAgent<br/><br/>PROMPT: Compose title<br/>ZONE A 40%: Brand+Product+Specs<br/>ZONE B 40%: Search phrases<br/>ZONE C 20%: Descriptors<br/>RULES:<br/>- NO hallucination<br/>- NO spec repetition<br/>- Flow naturally<br/><br/>OUTPUT: full_title + zones"]
        
        Process2["⚙️ Post-Processing<br/><br/>1. Enforce locked substrings<br/>2. Fix spacing (Inch es→Inches)<br/>3. Remove duplicate pack counts<br/>4. Clean pipes and spaces"]
        
        Agent6["🤖 TitleExtenderAgent<br/>(if < 170 chars)<br/><br/>PROMPT: Extend title<br/>- Add remaining keywords<br/>- Target 190 chars<br/>- Maintain flow<br/><br/>OUTPUT: extended_title"]
        
        Process3["⚙️ Validator<br/><br/>Check:<br/>- Length 180-200 chars<br/>- Brand present<br/>- Product present<br/>- No banned terms<br/>- Policy compliance"]
    end
    
    %% Logging
    subgraph Logger["📝 RunLogger"]
        Log1["truth_locked.json"]
        Log2["concepts.json"]
        Log3["category.json"]
        Log4["retrieval.json"]
        Log5["selected_keywords.json"]
        Log6["draft.json"]
        Log7["final.json"]
    end
    
    %% Data Flow
    Input --> Agent1
    Agent1 --> Agent2
    Agent1 -.->|log| Log3
    
    Agent2 --> Agent3
    Agent2 -.->|log| Log2
    
    Agent3 --> Process1
    
    Process1 --> ChromaDB
    ChromaDB --> Process1
    Process1 --> Agent4
    Process1 -.->|log| Log4
    
    Agent4 <-->|LLM call + fallback| Ollama
    Agent4 --> Agent5
    Agent4 -.->|log| Log5
    
    Agent5 <-->|LLM composition| Ollama
    Agent5 --> Process2
    Agent5 -.->|log| Log6
    
    Process2 --> Process3
    Process2 -.->|if short| Agent6
    
    Agent6 <-->|LLM extend| Ollama
    Agent6 --> Process3
    
    Process3 --> Output
    Process3 -.->|log| Log7
    
    Agent1 <-.->|API| Ollama
    Agent2 <-.->|API| Ollama
    Agent3 <-.->|API| Ollama
    
    %% Apply Styles
    class Agent1,Agent2,Agent3,Agent4,Agent5,Agent6 agentStyle
    class Input,Output dataStyle
    class Process1,Process2,Process3 processStyle
    class DB1 storageStyle
    
    %% Notes
    Note1["💡 Anti-Hallucination Strategy<br/>1. NEVER invent words<br/>2. NEVER change descriptors<br/>3. Use EXACT names<br/>4. NO assumptions<br/>5. Fallback to original"]
    
    Note2["⚡ Auto-Fallback Logic<br/>If AI returns empty:<br/>- Auto-select top 10 by score<br/>- Default ZONE_B<br/>- Zone C for fragrance/style<br/>- Pipeline always proceeds"]
    
    Agent5 -.-> Note1
    Agent4 -.-> Note2
```

---

## Architecture Components

### 🤖 AI Agents (6)

| Agent | Purpose | Input | Output |
|-------|---------|-------|--------|
| **CategoryDetectorAgent** | Classify product into category/subcategory | base_title, truth | category_info JSON |
| **ConceptEvaluatorAgent** | Filter subjective marketing terms | concept, type, context | keep: true/false |
| **QueryPlannerAgent** | Generate search queries for vector retrieval | title, truth, category | queries list |
| **KeywordSelectorAgent** | Select TOP 10 high-volume keywords | candidates, concepts, context | selected_keywords with zones |
| **TitleComposerAgent** | Compose optimized title with zone structure | all context + keywords | full_title with zone breakdown |
| **TitleExtenderAgent** | Extend short titles to 190 chars | short title, keywords | extended_title |

### ⚙️ Processing Steps (3)

| Process | Purpose | Operations |
|---------|---------|------------|
| **Vector Retrieval** | Query ChromaDB for relevant keywords | Execute queries → Merge results → Rank by score → Return top 60 |
| **Post-Processing** | Fix AI output artifacts | Enforce locked facts → Fix spacing → Remove duplicates |
| **Validator** | Final quality assurance | Check length, brand, product, banned terms |

### 🗄️ Data Storage

- **ChromaDB**: 153,459 keywords with SentenceTransformer embeddings
- **RunLogger**: 7 JSON files per run (truth, concepts, category, retrieval, keywords, draft, final)

### ☁️ LLM Configuration

- **Model**: DeepSeek-v3.1 (671b-cloud)
- **Temperature**: Progressive 0.2 → 0.3 → 0.4 → 0.5
- **Retries**: 3-4 attempts per agent call
- **Output**: JSON-structured responses

---

## Data Flow Sequence

```
1. INPUT (Original Title + Product Truth)
   ↓
2. CategoryDetectorAgent → Identify category/subcategory
   ↓
3. ConceptEvaluatorAgent → Filter subjective terms
   ↓
4. QueryPlannerAgent → Generate search queries
   ↓
5. Vector Retrieval → Query ChromaDB (60 candidates)
   ↓
6. KeywordSelectorAgent → Select TOP 10 (with auto-fallback)
   ↓
7. TitleComposerAgent → Compose with zones (40/40/20)
   ↓
8. Post-Processing → Fix spacing, enforce locks
   ↓
9. TitleExtenderAgent → Extend if < 170 chars (optional)
   ↓
10. Validator → Quality checks
   ↓
11. OUTPUT (Optimized Title 180-200 chars)
```

---

## Zone Structure (40/40/20)

### Zone A (40%) - Pure Information
- Brand name (once)
- Product type
- ALL specifications: size, dimension, count, color, material
- Locked facts used exactly once

**Example**: `Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black`

### Zone B (40%) - Search Optimization
- High-volume search phrases from keywords
- Complete phrases (no truncation)
- NO repetition of Zone A specs
- Feature keywords customers search for

**Example**: `Garbage Bags Medium Size with Perforated Box for Easy Dispensing`

### Zone C (20%) - Descriptors
- Fragrance/flavor (exact names from original)
- Style/finish details
- Secondary attributes

**Example**: `Lavender Fragrance`

---

## Anti-Hallucination Strategy

### 5 Core Rules

1. **Source Constraint**: ONLY use words from original title OR approved keywords
2. **Exact Preservation**: NEVER change descriptors (Lavender ≠ Fresh, Steel ≠ Metal)
3. **Locked Facts**: Pack count and dimensions extracted via regex, enforced exactly once
4. **No Assumptions**: NEVER invent features not explicitly stated
5. **Fallback Safety**: Return original title if AI fails after retries

### Auto-Fallback Mechanisms

- **KeywordSelector**: If AI returns empty, auto-select top 10 by score
- **TitleComposer**: If AI fails, return original title
- **QueryPlanner**: If AI fails, use hardcoded queries
- **All Agents**: Progressive temperature increase on retry

---

## Execution Logs

Each run creates timestamped directory: `runs/YYYYMMDD_HHMMSS_title-slug/`

| File | Content |
|------|---------|
| `truth_locked.json` | Product attributes + extracted locked facts |
| `concepts.json` | Parsed concepts from original title |
| `category.json` | Category detection results |
| `retrieval.json` | Vector queries + top 60 candidates |
| `selected_keywords.json` | TOP 10 selected keywords with zones |
| `draft.json` | Title composition with zone breakdown |
| `final.json` | Optimized title + validation report |

---

## Key Metrics

- **Original Length**: Input title character count
- **Final Length**: Output title character count (target: 180-200)
- **Selected Keywords**: Number and list of TOP 10 keywords
- **Validation Status**: Pass/fail with issue list
- **Agents Used**: List of agents invoked (shows execution path)
- **Zone Distribution**: Character allocation across zones

---

## Example Transformation

### Input
```
Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 
120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing
```
(184 chars, pipes, redundant terms)

### Output
```
Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black, 
Garbage Bags Medium Size with Perforated Box for Easy Dispensing, Lavender Fragrance
```
(180 chars, clean flow, high-volume phrase "garbage bags medium size" included, no hallucinations)

### Improvements
- ✅ Added high-volume phrase "garbage bags medium size" (0.4167 score)
- ✅ Removed pipes, clean comma separation
- ✅ No duplicate pack counts
- ✅ Exact fragrance name preserved
- ✅ Natural flow across zones
- ✅ No invented features

---

**Last Updated**: December 31, 2025  
**Version**: 1.0  
**Model**: DeepSeek-v3.1 (671b-cloud)
