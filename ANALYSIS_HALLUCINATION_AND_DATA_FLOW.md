# Analysis: Hallucinations, Keyword Limits, and Data Flow

This document addresses your concerns regarding the Agentic V2 architecture, specifically focusing on small model performance, keyword selection limits, and data visibility.

## 1. Why Small Models Hallucinate (Llama 8B, Mistral 7B, etc.)

You noticed that the agent works well on large models (70B+) but "hallucinates" on smaller ones. This is a known limitation of smaller parameters models.

### The "Cognitive Load" Problem
Small models have a limited "reasoning budget." The current Agent 4 (Zone Builder) is asked to do **too much at once**:
1.  Read Title & Truth
2.  Read Vector DB keywords
3.  Follow 7+ negative constraints ("No pipes", "No repeated brand", etc.)
4.  Sort by search priority (Zone A)
5.  Optimized SEO (Zone B)
6.  Format JSON output

**Result:** The model gets overwhelmed. It prioritizes "generating text that looks like a title" over "following every strict rule." It might invent a feature (hallucination) just to make the title flow better because it forgot the "only use provided concepts" rule by the time it reached the end of the prompt.

### Solution: "Chain of Thought" & Strict Validation
To fix this for small models, we cannot just rely on one big prompt. We need:

1.  **Decomposition**: Don't ask for the full title at once.
    *   *Step 1:* "Given these keywords, list ONLY the ones to keep for Zone A."
    *   *Step 2:* "Now arrange them."
2.  **Strict Validator (The "Police" Agent)**:
    *   We need a code-based (non-AI) validator that runs immediately after Agent 4.
    *   **Rule:** If a word in the generated title is NOT in (Original Title + Truth + Vector DB Keywords), **REJECT IT**.
    *   This forces the AI to stay "grounded."

---

## 2. The "Top 5" Keyword Limitation

**Current Behavior:**
*   `Vector DB` retrieves ~60 candidates.
*   `Agent 3` (Ranking) filters this down to **Top 5**.
*   `Agent 4` (Builder) **only sees those 5** and the original title concepts.

**Your Concern:**
Picking just 5 is arbitrary. Valuable keywords might be at position #6 or #7. The Agent should have the full context to decide.

**Analysis:**
You are correct. Hard-limiting to 5 acts as an information bottleneck. However, passing *all* 60 candidates to a small model will cause **severe hallucinations** (distraction). It will likely pick vaguely related words just because they are in the context.

**Proposed Architecture Fix:**
Instead of a hard "Top 5", we should Categorize and Pass More, but Structured.

1.  **Vector DB** retrieves ~60 candidates.
2.  **Agent 3 (Classifier)** classifies them into buckets instead of just ranking:
    *   *Synonyms* (e.g., "Trash Can", "Waste Bin") -> **Pass ALL valid ones** (usually 2-3).
    *   *Feature Phrases* (e.g., "Leak Proof", "With Tie Tape") -> **Pass Best 3-5**.
    *   *Broad Matches* -> Filter aggressively.
3.  **Agent 4 (Builder)** receives a **curated list of ~10-15 keywords** categorized by type, not just a flat "Top 5".

**Why this is better:** It gives Agent 4 more options (15 vs 5) without overwhelming it with noise (60).

---

## 3. Data Visibility (Who sees the Vector DB?)

You asked: *"Does each level/agent have access to the titles that we are getting from vector database?"*

**Current Status:**
*   **Agent 1 (Category Detector):** ❌ **NO.** Only sees Title + Truth.
    *   *Impact:* Misses context. If title says "filters", Vector DB might clarify if it's "coffee filters" or "air filters."
*   **Agent 2 (Concept Evaluator):** ❌ **NO.** Only sees Concept + Product Context.
    *   *Impact:* It decides to remove "Premium" based on general knowledge, not knowing if "Premium" is a top keyword in the Vector DB for this category.
*   **Agent 3 (Keyword Ranker):** ✅ **YES.** This is its main job.
*   **Agent 4 (Zone Builder):** ⚠️ **PARTIAL.** Only sees the "Top 5" filtered by Agent 3.

**Proposed Changes:**
Every agent should be **"Data-Aware"**. The Vector DB provides the "Voice of the Customer" (what people search).

| Agent | Needs Vector DB? | Why? |
| :--- | :--- | :--- |
| **1. Category Detector** | **YES** | To confirm category using search clusters. |
| **2. Concept Evaluator** | **YES** | **CRITICAL.** Should keep "Scented" if "Scented" appears frequently in Vector DB results. |
| **3. Keyword Ranker** | **YES** | (Already has it) |
| **4. Zone Builder** | **YES** | Needs a broader, categorized set (not just top 5). |

---

## 4. Enhanced Architecture Diagram

Here is how the new architecture should look to address your concerns:

```mermaid
flowchart TD
    UserInput[Title + Truth] --> Parser
    Parser --> BaseConcepts[Base Concepts]
    
    %% NEW: Vector DB is queried EARLY and shared globally
    BaseConcepts --> VectorDB[Vector DB Search]
    VectorDB -->|Retrieves 60 Candidates| GlobalContext[Global Search Context]
    
    %% Agent 1 sees Search Context now
    GlobalContext --> Agent1[Agent 1: Category Detector]
    Agent1 -->|Provides Search Priorities| Agent2
    
    %% Agent 2 uses Search Volume to decide
    GlobalContext --> Agent2[Agent 2: Concept Evaluator]
    BaseConcepts --> Agent2
    Agent2 -->|Evaluated Concepts w/ Keep/Remove| Agent3
    
    %% Agent 3 categorizes instead of just "Top 5"
    GlobalContext --> Agent3[Agent 3: Keyword Curator]
    Agent3 -->|Output: Synonyms, Features, Usage (Approx 15)| Agent4
    
    %% Agent 4 builds title
    Agent2 --> Agent4[Agent 4: Title Builder]
    Agent3 --> Agent4
    
    %% NEW: The "Police" / Validator
    Agent4 --> Validator{Hallucination Check}
    Validator -- Pass --> Output
    Validator -- Fail (Found new words) --> Retry[Retry with Penalty]
    Retry --> Agent4
```

## 5. Summary of Recommended Fixes

1.  **Global Vector Context:** Fetch Vector DB results *first* and pass summary statistics to **Agent 1** and **Agent 2** so they make informed decisions.
2.  **Smart Curation (Not Top 5):** Change Agent 3 to group keywords (Synonyms, Features) and pass a larger, cleaner set (10-15) to Agent 4.
3.  **Anti-Hallucination Loop:** Implement a strict code-based check after Agent 4. If the generated title contains words not in (Input + Allowed Keywords), simpler retry logic is triggered.
