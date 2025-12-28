# Agentic Strategy 2: AI-Powered Amazon Title Optimizer

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent Amazon product title optimization system that uses AI agents and vector database search to transform product titles for maximum search visibility and click-through rates.

## 🚀 Features

- **AI-Driven Optimization**: Uses 4 specialized AI agents instead of hardcoded rules
- **Vector Database**: Semantic search with 153,459+ keyword embeddings
- **Multi-Category Support**: Works across automotive, home storage, and other product categories
- **Local Processing**: No external API dependencies - runs entirely on your machine
- **Context-Aware**: AI agents make intelligent decisions based on product category and search behavior

## 📋 Prerequisites

Before running this project, ensure you have:

1. **Python 3.8 or higher**
2. **Ollama installed and running** ([Setup Guide](#ollama-setup))
3. **Git** (to clone this repository)

## 🛠️ Installation & Setup

### Step 1: Clone and Navigate

```bash
git clone <repository-url>
cd agentic_strategy_2
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `sentence-transformers>=2.2.0` - For vector embeddings
- `numpy>=1.21.0` - For numerical operations
- `pandas>=1.3.0` - For data processing
- `requests>=2.25.0` - For HTTP client

### Step 3: Ollama Setup

#### Install Ollama

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:** Download from [ollama.ai](https://ollama.ai)

#### Download and Run Ollama Model

```bash
# Start Ollama service
ollama serve

# In a new terminal, download a model
ollama pull gemma3:4b
```

**Alternative Models** (choose one):
```bash
ollama pull deepseek-v3.1:671b-cloud  # Cloud model (requires internet)
ollama pull gpt-oss:20b-cloud         # Alternative cloud model
```

#### Verify Ollama is Running

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing available models.

### Step 4: Environment Configuration

The project includes an `.env` file with default settings. Review and customize as needed:

```bash
# Core AI Configuration
ADKRUX_USE_AI=true                    # Enable AI features
ADKRUX_OLLAMA_MODEL=gemma3:4b         # Your chosen model
ADKRUX_OLLAMA_URL=http://localhost:11434

# Vector Search Configuration
ADKRUX_EMBED_MODEL=all-MiniLM-L6-v2   # Embedding model
ADKRUX_VECTOR_DEBUG=true              # Enable debugging
ADKRUX_AI_VECTOR_ROUNDS=1             # AI query expansion
ADKRUX_VECTOR_LIMIT_PER_QUERY=25      # Results per query
```

### Step 5: Build Keyword Database

If you don't have a keyword database, build one from the included sample data:

```bash
python3 ingest_keywords.py --reset
```

This creates `st_keywords_index/keywords_index.npz` with ~153k keyword embeddings.

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

#### 1. Ollama Connection Failed

**Error:** `Cannot connect to Ollama at http://localhost:11434`

**Solution:**
```bash
# Check if Ollama is running
ollama serve

# Verify model is downloaded
ollama list

# Test connection
curl http://localhost:11434/api/tags
```

#### 2. No Keywords Found

**Error:** `No index found. Run 'python3 ingest_keywords.py' first!`

**Solution:**
```bash
python3 ingest_keywords.py --reset
```

#### 3. Out of Memory

**Error:** System runs out of memory during embedding

**Solution:**
- Reduce `ADKRUX_VECTOR_MAX_CANDIDATES` in .env
- Use smaller embedding model: `ADKRUX_EMBED_MODEL=all-MiniLM-L6-v2`
- Close other applications

#### 4. Slow Performance

**Symptoms:** Optimization takes >30 seconds

**Solutions:**
- Set `ADKRUX_AI_VECTOR_ROUNDS=0` for faster processing
- Use local model instead of cloud: `ADKRUX_OLLAMA_MODEL=gemma3:4b`
- Reduce `ADKRUX_VECTOR_LIMIT_PER_QUERY=15`

### Getting Help

1. **Check Logs**: Enable `ADKRUX_DEBUG=true` in .env
2. **Verify Setup**: Run the test commands in the Testing section
3. **Review Architecture**: See `ARCHITECTURE_OVERVIEW.md` for detailed system design
4. **Check Requirements**: Ensure all dependencies are installed correctly

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
