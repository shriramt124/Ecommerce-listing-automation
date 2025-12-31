# Agentic Strategy 2: AI-Powered Amazon Title Optimizer

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent Amazon product title optimization system that uses AI agents and vector database search to transform product titles for maximum search visibility and click-through rates.

## 🎯 What This Does

Transforms verbose Amazon product titles into optimized, search-friendly versions using AI agents:

**Before:** `Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing` (186 chars)

**After:** `Shalimar Scented Garbage Bags Medium 19x21" 120 Bags (30 Bags x 4 Rolls) Premium Dustbin Bags for Kitchen Lavender Fragrance Trash Bag Black` (163 chars)

## 🚀 Key Features

- **AI-Driven Optimization**: Uses 4 specialized AI agents instead of hardcoded rules
- **Vector Database**: Semantic search with 153,459+ keyword embeddings
- **Multi-Category Support**: Works across automotive, home storage, and other product categories
- **Local Processing**: No external API dependencies - runs entirely on your machine
- **Context-Aware**: AI agents make intelligent decisions based on product category and search behavior

## ⚡ QUICK START (5 Minutes)

### Step 1: Prerequisites Check

```bash
# Check Python version (need 3.8+)
python3 --version

# Check if pip is available
pip3 --version

# Install Ollama (if not installed)
brew install ollama  # macOS
# OR curl -fsSL https://ollama.ai/install.sh | sh  # Linux
# OR download from ollama.ai  # Windows
```

### Step 2: Project Setup

```bash
# Navigate to project directory
cd agentic_strategy_2

# The .env file is already created with optimal defaults
# You can customize it if needed (see Configuration section below)

# Install dependencies
pip3 install -r requirements.txt
```

### Step 3: Start Ollama & Download Model

```bash
# Terminal 1: Start Ollama server
ollama serve

# Terminal 2: Download AI model (choose one)
ollama pull gemma3:4b              # Recommended: Fast local model
# OR ollama pull deepseek-v3.1:671b-cloud  # Alternative cloud model

# Verify it's working
curl http://localhost:11434/api/tags
```

### Step 4: Build Keyword Database (First Time Only)

```bash
# Build vector database from sample data
python3 ingest_keywords.py --reset

# This creates st_keywords_index/keywords_index.npz with ~153k keywords
```

### Step 5: Test Run

```bash
# Interactive mode
python3 main.py

# Test with sample data
python3 agentic_main.py
```

## 🎯 STEP-BY-STEP DETAILED GUIDE

### Prerequisites Installation

#### 1. Python Installation
**macOS:**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.8+
brew install python@3.11
```

**Windows:**
- Download Python from [python.org](https://python.org/downloads/)
- Check "Add to PATH" during installation
- Verify: `python --version`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

#### 2. Ollama Installation

**macOS (Recommended):**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
- Download installer from [ollama.ai](https://ollama.ai)
- Run installer and follow prompts

**Verify Installation:**
```bash
ollama --version
```

#### 3. Download AI Model

```bash
# Start Ollama service (keep running in background)
ollama serve

# Download model (in new terminal)
ollama pull gemma3:4b

# Alternative models:
ollama pull deepseek-v3.1:671b-cloud  # More capable, requires internet
ollama pull llama3.1:8b               # Another local option
ollama pull qwen2.5:7b                # Fast alternative

# Verify download
ollama list
```

### Project Setup

#### 1. Environment Configuration

The project includes a pre-configured `.env` file with optimal defaults. You can customize it based on your needs:

```bash
# View current configuration
cat .env

# Edit environment file (optional - defaults work well for most users)
nano .env  # or use your preferred editor
```

**Configuration Options Explained:**

**For Fast Processing (Quick Results):**
```bash
ADKRUX_USE_AI=true
ADKRUX_OLLAMA_MODEL=gemma3:4b
ADKRUX_AI_VECTOR_ROUNDS=0             # Skip AI query expansion
ADKRUX_VECTOR_DEBUG=false             # Disable verbose logging
ADKRUX_VECTOR_LIMIT_PER_QUERY=15      # Fewer results per query
ADKRUX_VECTOR_MAX_CANDIDATES=30       # Limit total candidates
```

**For High Quality (Best Results):**
```bash
ADKRUX_USE_AI=true
ADKRUX_OLLAMA_MODEL=deepseek-v3.1:671b-cloud  # More capable model
ADKRUX_AI_VECTOR_ROUNDS=2             # Enhanced AI expansion
ADKRUX_VECTOR_DEBUG=true              # Enable detailed logging
ADKRUX_VECTOR_LIMIT_PER_QUERY=35      # More results per query
ADKRUX_VECTOR_MAX_CANDIDATES=100      # Consider more keywords
```

**For Development/Debugging:**
```bash
ADKRUX_USE_AI=true
ADKRUX_OLLAMA_MODEL=gemma3:4b
ADKRUX_AI_VECTOR_ROUNDS=1
ADKRUX_VECTOR_DEBUG=true              # Show detailed process
ADKRUX_DEBUG=true                     # Additional debug info
```

#### 2. Install Dependencies

```bash
# Install required packages
pip3 install -r requirements.txt

# Expected packages:
# - sentence-transformers>=2.2.0
# - numpy>=1.21.0  
# - pandas>=1.3.0
# - requests>=2.25.0

# Verify installation
python3 -c "import sentence_transformers, numpy, pandas, requests; print('✅ All dependencies installed')"
```

#### 3. Build Keyword Database

```bash
# Create keyword database from sample data
python3 ingest_keywords.py --reset

# Expected output:
# ============================================================
#   STRATEGY 2: KEYWORD INGESTION (SentenceTransformers)
# ============================================================
# [1/3] Loading existing index (if any): st_keywords_index/keywords_index.npz
#       -> No existing index found
# [2/3] Ingesting keywords and computing embeddings...
#    -> Ingesting dataset: KeywordResearch_Home_Home Storage...
# [3/3] Writing index to disk...
# ============================================================
#   SUCCESS: Added 153459 keywords to ST index
# ============================================================
```

### Testing Your Setup

#### 1. Verify Environment Configuration

```bash
# Check if .env file exists and has correct format
ls -la .env
cat .env

# Verify environment variables are loaded
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('✅ Environment file loaded successfully')
print(f'AI Enabled: {os.getenv(\"ADKRUX_USE_AI\")}')
print(f'Ollama Model: {os.getenv(\"ADKRUX_OLLAMA_MODEL\")}')
print(f'Vector Debug: {os.getenv(\"ADKRUX_VECTOR_DEBUG\")}')
"
```

#### 2. Test Individual Components

```bash
# Test keyword database
python3 -c "from keyword_db import KeywordDB; db = KeywordDB(); print('✅ KeywordDB working')"

# Test embedding model
python3 -c "from embedder import get_embedder; model = get_embedder(); print('✅ Embedding model working')"

# Test Ollama connection (requires Ollama to be running)
python3 -c "
try:
    import requests
    response = requests.get('http://localhost:11434/api/tags', timeout=2)
    if response.status_code == 200:
        print('✅ Ollama server is running')
    else:
        print('❌ Ollama server error:', response.status_code)
except Exception as e:
    print('❌ Ollama connection failed:', str(e)[:100])
"

# Test environment loading in main components
python3 -c "
from agentic_optimizer import AgenticOptimizer
print('✅ AgenticOptimizer can be imported')
try:
    optimizer = AgenticOptimizer()
    print('✅ AgenticOptimizer initialized successfully')
except Exception as e:
    print('❌ AgenticOptimizer failed:', str(e)[:100])
"
```

#### 3. First-Time Setup Checklist

```bash
# Complete this checklist after initial installation:

# ✅ 1. Verify Python and dependencies
python3 --version  # Should be 3.8+
pip3 list | grep -E "(sentence-transformers|numpy|pandas|requests)"

# ✅ 2. Check environment configuration
ls -la .env && head -10 .env

# ✅ 3. Verify Ollama installation and model
ollama --version
ollama list  # Should show at least one model

# ✅ 4. Build keyword database (first time only)
python3 ingest_keywords.py --reset

# ✅ 5. Test system components
python3 -c "from keyword_db import KeywordDB; db = KeywordDB(); print('✅ Database ready')"
python3 -c "from embedder import get_embedder; model = get_embedder(); print('✅ Embeddings ready')"

# ✅ 6. Run a test optimization
echo "Testing with sample title..." && python3 -c "
from main import get_sample_title, get_sample_truth
from agentic_optimizer import AgenticOptimizer
optimizer = AgenticOptimizer()
title = get_sample_title()
truth = get_sample_truth()
result = optimizer.optimize(title, truth)
print('✅ System working - optimization completed')
"
```

#### 4. Run Optimization Test

```bash
# Interactive mode (recommended first run)
python3 main.py
```

**What to expect:**
```
Enter product title: [paste your title]
============================================================
  AGENTIC STRATEGY 2: AI-POWERED TITLE OPTIMIZATION
============================================================
[1/4] Extracting product truth with AI...
[2/4] Detecting category and search priorities...
[3/4] Retrieving relevant keywords from vector database...
[4/4] Building optimized title with AI agents...
============================================================

ORIGINAL TITLE (186 chars):
Shalimar Premium (Lavender Fragrance) Scented Garbage Bags...

OPTIMIZED TITLE (163 chars):
Shalimar Scented Garbage Bags Medium 19x21" 120 Bags...

Characters saved: 23 chars ✅ PERFECT
============================================================
```

#### 3. Batch Processing Test

```bash
# Run predefined test cases
python3 agentic_main.py
```

This shows multiple optimization examples with detailed AI agent reasoning.

## 🎯 Quick Start

### Method 1: Interactive Mode

```bash
python3 main.py
```

1. Enter your product title when prompted
2. The system will automatically extract product attributes
3. AI agents will optimize the title
4. View the optimized result with character count and improvements

**Sample Input:**
```
Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing
```

### Method 2: Test with Sample Data

```bash
python3 agentic_main.py
```

This runs pre-configured test cases and shows the optimization process.

## 📊 Understanding the Output

### Character Breakdown

```
Original: 186 chars
Optimized: 163 chars
Characters saved: 23 chars

Status: ✅ PERFECT - Within target range (160-200 chars)!
```

### AI Agents Used

The optimization process uses 4 AI agents:

1. **Category Detector**: Identifies product category and search priorities
2. **Concept Evaluator**: Decides keep/remove for quality markers like "Premium"
3. **Keyword Ranker**: Selects high-value keywords from vector database
4. **Zone Builder**: Constructs the final optimized title with 3-zone structure

### Zone Structure

- **Zone A (40%)**: Decision zone - what users see first in search results
- **Zone B (40%)**: SEO zone - synonyms and additional keywords  
- **Zone C (20%)**: Details zone - color, features, and low-priority attributes

## 🔧 Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADKRUX_USE_AI` | `true` | Enable/disable AI features |
| `ADKRUX_OLLAMA_MODEL` | `gemma3:4b` | Ollama model name |
| `ADKRUX_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `ADKRUX_EMBED_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformers model |
| `ADKRUX_VECTOR_DEBUG` | `true` | Enable vector retrieval debugging |
| `ADKRUX_AI_VECTOR_ROUNDS` | `1` | AI query expansion rounds (0-3) |

### Performance Tuning

For faster optimization:
```bash
ADKRUX_AI_VECTOR_ROUNDS=0  # Skip AI query expansion
ADKRUX_VECTOR_DEBUG=false  # Disable verbose logging
```

For better quality:
```bash
ADKRUX_AI_VECTOR_ROUNDS=2  # More AI query suggestions
ADKRUX_VECTOR_MAX_CANDIDATES=100  # Consider more keywords
```

## 📁 Project Structure

```
agentic_strategy_2/
├── main.py                    # Interactive optimization interface
├── agentic_main.py           # Test cases and batch processing
├── agentic_optimizer.py      # Core AI optimization engine
├── ingest_keywords.py        # Build keyword database
├── keyword_db.py             # Vector database interface
├── parser.py                 # Title parsing and concept extraction
├── token_types.py            # Token classification system
├── .env                      # Environment configuration
├── requirements.txt          # Python dependencies
├── st_keywords_index/        # Vector database storage
│   └── keywords_index.npz    # 153k keyword embeddings
└── data files/               # Sample keyword research data
```

## 🧪 Testing & Development

### Run Tests

```bash
# Test individual components
python3 -c "from keyword_db import KeywordDB; db = KeywordDB(); print('✅ KeywordDB working')"
python3 -c "from embedder import get_embedder; model = get_embedder(); print('✅ Embedding model working')"
```

### Debug Mode

Enable verbose debugging:

```bash
export ADKRUX_VECTOR_DEBUG=true
python3 main.py
```

This shows:
- Vector queries used
- AI agent decisions
- Keyword ranking process
- Title construction steps

### Performance Benchmark

```bash
time python3 main.py  # Add 'time' command to measure performance
```

Typical performance:
- Category detection: ~2-3 seconds
- Keyword ranking: ~3-4 seconds  
- Title generation: ~5-8 seconds
- Total pipeline: ~15-20 seconds

## 🛠️ Troubleshooting

### Common Issues

#### 1. Environment File Issues

**Error:** `Environment variables not loading` or `ModuleNotFoundError: No module named 'dotenv'`

**Solution:**
```bash
# Check if .env file exists
ls -la .env

# Install python-dotenv if missing
pip3 install python-dotenv

# Verify environment loading
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print('✅ Environment loaded:', os.getenv('ADKRUX_USE_AI'))"

# Check for syntax errors in .env file
python3 -c "
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
    print('✅ .env file syntax is valid')
except Exception as e:
    print('❌ .env file error:', e)
"
```

#### 2. Ollama Connection Failed

**Error:** `Cannot connect to Ollama at http://localhost:11434`

**Solution:**
```bash
# Check if Ollama is running
ollama serve

# Verify model is downloaded
ollama list

# Test connection
curl http://localhost:11434/api/tags

# Check environment configuration
grep ADKRUX_OLLAMA .env
```

#### 3. No Keywords Found

**Error:** `No index found. Run 'python3 ingest_keywords.py' first!`

**Solution:**
```bash
# Build the keyword database
python3 ingest_keywords.py --reset

# Verify database was created
ls -la st_keywords_index/
python3 -c "from keyword_db import KeywordDB; db = KeywordDB(); print(f'✅ Database loaded with {len(db.get_all_keywords())} keywords')"
```

#### 4. Environment Configuration Problems

**Error:** Settings not applying or getting wrong model/behavior

**Solution:**
```bash
# Reload environment variables
source .env

# Check current settings
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Current settings:')
print(f'  AI Enabled: {os.getenv(\"ADKRUX_USE_AI\")}')
print(f'  Model: {os.getenv(\"ADKRUX_OLLAMA_MODEL\")}')
print(f'  Debug: {os.getenv(\"ADKRUX_VECTOR_DEBUG\")}')
print(f'  Rounds: {os.getenv(\"ADKRUX_AI_VECTOR_ROUNDS\")}')
"

# Reset to defaults if needed
cp .env .env.backup  # Backup current settings
# Edit .env to restore default values
```

#### 5. Out of Memory

**Error:** System runs out of memory during embedding

**Solution:**
```bash
# Reduce memory usage in .env:
ADKRUX_VECTOR_MAX_CANDIDATES=30       # Lower from 60
ADKRUX_VECTOR_LIMIT_PER_QUERY=15      # Lower from 25
ADKRUX_AI_VECTOR_ROUNDS=0             # Skip AI expansion

# Use lighter embedding model
ADKRUX_EMBED_MODEL=all-MiniLM-L6-v2

# Close other applications and try again
```

#### 6. Slow Performance

**Symptoms:** Optimization takes >30 seconds

**Solutions:**
```bash
# For faster processing, update .env:
ADKRUX_AI_VECTOR_ROUNDS=0             # Skip AI query expansion
ADKRUX_VECTOR_DEBUG=false             # Disable verbose logging
ADKRUX_VECTOR_LIMIT_PER_QUERY=15      # Reduce from 25
ADKRUX_OLLAMA_MODEL=gemma3:4b         # Use faster local model

# Test performance
time python3 main.py
```

#### 7. Permission Errors

**Error:** `Permission denied` when creating database files

**Solution:**
```bash
# Fix file permissions
chmod 755 .
chmod 644 .env

# Ensure write permissions for database directory
mkdir -p st_keywords_index
chmod 755 st_keywords_index

# Run with appropriate permissions
python3 ingest_keywords.py --reset
```

### Getting Help

1. **Check Logs**: Enable `ADKRUX_DEBUG=true` in .env
2. **Verify Setup**: Run the test commands in the Testing section
3. **Review Architecture**: See `ARCHITECTURE_OVERVIEW.md` for detailed system design
4. **Check Requirements**: Ensure all dependencies are installed correctly

## 🎯 COMPLETE SETUP SUMMARY

### Quick Verification Checklist

Run this complete checklist to ensure everything is working:

```bash
# 1. System Requirements
python3 --version  # Should be 3.8+
ollama --version   # Should show version
ls -la .env        # Should show environment file

# 2. Dependencies
pip3 list | grep -E "(sentence-transformers|numpy|pandas|requests|dotenv)"

# 3. Environment Configuration
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
settings = {
    'AI_Enabled': os.getenv('ADKRUX_USE_AI'),
    'Model': os.getenv('ADKRUX_OLLAMA_MODEL'),
    'Debug': os.getenv('ADKRUX_VECTOR_DEBUG'),
    'Rounds': os.getenv('ADKRUX_AI_VECTOR_ROUNDS')
}
for k, v in settings.items():
    print(f'✅ {k}: {v}')
"

# 4. Ollama Service
curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama running" || echo "❌ Ollama not running"

# 5. Keyword Database
python3 -c "
from keyword_db import KeywordDB
db = KeywordDB()
keywords = db.get_all_keywords()
print(f'✅ Database loaded: {len(keywords)} keywords')
" 2>/dev/null || echo "❌ Database not built - run: python3 ingest_keywords.py --reset"

# 6. System Integration Test
python3 -c "
from agentic_optimizer import AgenticOptimizer
try:
    optimizer = AgenticOptimizer()
    print('✅ AgenticOptimizer initialized')
    print('✅ System ready for optimization')
except Exception as e:
    print('❌ System error:', str(e)[:100])
"

# 7. Performance Test (optional)
echo "Testing optimization speed..."
time python3 -c "
from main import get_sample_title
from agentic_optimizer import AgenticOptimizer
optimizer = AgenticOptimizer()
title = get_sample_title()
result, _ = optimizer.optimize(title, {})
print(f'✅ Optimization completed: {len(result)} chars')
" 2>/dev/null || echo "❌ Optimization test failed"
```

### Final Setup Confirmation

If all checks pass, you're ready to optimize titles! Here's what you can do:

```bash
# ✅ Ready for optimization
python3 main.py  # Interactive mode
python3 agentic_main.py  # Test with samples

# ✅ Ready for batch processing
# Edit the main files to add your own titles

# ✅ Ready for development
# All components are working and can be extended
```

### What You Should See

**Successful setup output:**
```
✅ AI_Enabled: true
✅ Model: gemma3:4b
✅ Debug: true
✅ Rounds: 1
✅ Ollama running
✅ Database loaded: 153459 keywords
✅ AgenticOptimizer initialized
✅ System ready for optimization
```

**Ready to optimize titles!**
```bash
python3 main.py
# Enter a title and see the AI optimization in action
```

## 📚 Additional Resources

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md) - Detailed system design
- [Comprehensive Analysis](COMPREHENSIVE_PROJECT_ANALYSIS.md) - Complete project analysis
- [Ollama Setup Guide](OLLAMA_SETUP_GUIDE.txt) - Detailed Ollama installation
- [Algorithm Explanation](ALGORITHM_EXPLAINED.txt) - Technical algorithm details

## 🤝 Contributing

This project demonstrates an AI-first approach to title optimization. Key innovations include:

- **Multi-Agent Architecture**: 4 specialized AI agents for different optimization tasks
- **Vector Database Search**: Evidence-based keyword selection using semantic similarity
- **Context-Aware Decisions**: AI considers product category and search behavior
- **Local Processing**: No external API dependencies for cost-effective scaling

## 📄 License

MIT License - feel free to use this for your own projects.

---

**Need Help?** Check the troubleshooting section or review the architecture documentation for detailed system insights.
