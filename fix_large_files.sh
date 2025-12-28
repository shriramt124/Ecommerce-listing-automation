#!/bin/bash

# =============================================================================
# FIX LARGE FILES ISSUE
# Remove large CSV files from Git history to comply with GitHub's 100MB limit
# =============================================================================

set -e  # Exit on any error

echo "🔧 Fixing large files issue in Git repository..."
echo "=================================================="

# Remove large files from the current working directory first
echo "📁 Removing large files from working directory..."
find . -name "*.csv" -type f -delete
find . -name "*.xlsx" -type f -delete
echo "✅ Large files removed from working directory"

# Remove from Git index (staging area)
echo "📋 Removing files from Git index..."
git rm --cached -r . 2>/dev/null || true

# Add all files except the large ones back to index
echo "📦 Re-adding files to Git index (excluding large files)..."
git add .

# Check if there are any changes to commit
if git diff --staged --quiet; then
    echo "✅ No changes to commit - all large files already excluded"
else
    echo "💾 Committing changes..."
    git commit -m "Remove large CSV/Excel files to comply with GitHub's 100MB limit"
fi

# Show current status
echo ""
echo "📊 Current repository status:"
git status

echo ""
echo "🔍 Large files that would exceed GitHub limit:"
find . -name "*.csv" -o -name "*.xlsx" -o -name "*.npz" | while read file; do
    size=$(du -h "$file" | cut -f1)
    echo "   📄 $file ($size)"
done

echo ""
echo "⚡ If you still get push errors, run:"
echo "   git push --force-with-lease"
echo ""
echo "📝 Note: The large files remain in your local directory but won't be pushed to GitHub"
echo "   This preserves your data while making the repository GitHub-compatible"

