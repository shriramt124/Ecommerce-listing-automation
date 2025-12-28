#!/bin/bash

# =============================================================================
# AGENTIC STRATEGY 2: SETUP SCRIPT
# Automated setup for AI-Powered Amazon Title Optimizer
# =============================================================================

set -e  # Exit on any error

echo "🚀 Setting up Agentic Strategy 2: AI-Powered Title Optimizer"
echo "================================================================"

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.8"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "❌ Error: Python 3.8+ required. Found: $python_version"
    exit 1
fi
echo "✅ Python version OK: $python_version"

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✅ Dependencies installed successfully"

# Create necessary directories
echo ""
echo "📁 Creating directories..."
mkdir -p st_keywords_index
echo "✅ Directories created"

# Check if keyword database exists
if [ ! -f "st_keywords_index/keywords_index.npz" ]; then
    echo ""
    echo "🗄️  Building keyword database..."
    echo "   This may take 2-5 minutes depending on your system..."
    python3 ingest_keywords.py --reset
    echo "✅ Keyword database built successfully"
else
    echo "✅ Keyword database already exists"
fi

# Ollama setup check
echo ""
echo "🤖 Checking Ollama setup..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    
    # Check if Ollama service is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama service is running"
        
        # Check if model is available
        if ollama list | grep -q "gemma3:4b"; then
            echo "✅ Default model (gemma3:4b) is available"
        else
            echo "⚠️  Default model not found. Please run:"
            echo "   ollama pull gemma3:4b"
        fi
    else
        echo "⚠️  Ollama service not running. Please start it with:"
        echo "   ollama serve"
    fi
else
    echo "⚠️  Ollama not found. Please install it:"
    echo ""
    echo "   macOS:   brew install ollama"
    echo "   Linux:   curl -fsSL https://ollama.ai/install.sh | sh"
    echo "   Windows: Download from https://ollama.ai"
    echo ""
    echo "   Then run: ollama pull gemma3:4b"
fi

# Test basic functionality
echo ""
echo "🧪 Testing basic functionality..."
echo "   Testing keyword database..."
python3 -c "
from keyword_db import KeywordDB
db = KeywordDB()
results = db.get_top_keywords('garbage bags', limit=3)
print(f'   ✅ KeywordDB working - Found {len(results)} results')
" 2>/dev/null || echo "   ❌ KeywordDB test failed"

echo "   Testing embedding model..."
python3 -c "
from embedder import get_embedder
model = get_embedder()
print('   ✅ Embedding model working')
" 2>/dev/null || echo "   ❌ Embedding model test failed"

echo ""
echo "🎉 Setup Complete!"
echo "================================================================"
echo ""
echo "Next steps:"
echo "1. If Ollama is not running: ollama serve"
echo "2. If model not downloaded: ollama pull gemma3:4b"
echo "3. Start optimizing titles: python3 main.py"
echo ""
echo "For detailed instructions, see README.md"
echo ""
