#!/bin/bash

# =============================================================================
# COMPLETE FIX FOR LARGE FILES ISSUE
# This script will completely remove large files from Git history
# =============================================================================

set -e  # Exit on any error

echo "🚨 COMPLETE FIX FOR LARGE FILES ISSUE"
echo "======================================"
echo ""
echo "This will completely remove large CSV/Excel files from your Git history."
echo "Your local files will be preserved, but they won't be tracked by Git."
echo ""

# Confirm with user
read -p "Do you want to proceed? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

echo ""
echo "🔍 Finding large files in Git history..."

# Remove large files from entire Git history
echo "🗑️  Removing large files from Git history..."
git filter-branch --force --index-filter '
git rm --cached --ignore-unmatch "KeywordResearch_Home_Home Storage & Organization_Waste & Recycling_30_22-12-2025_17-27-42.csv"
git rm --cached --ignore-unmatch "KeywordResearch_Automotive_Motorbike Accessories & Parts_Handlebars & Forks_30_22-12-2025_18-56-04.csv"
' --tag-name-filter cat -- --all

echo "✅ Large files removed from Git history"

# Clean up the filter-branch references
echo "🧹 Cleaning up Git references..."
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ Git references cleaned"

# Show current status
echo ""
echo "📊 Current repository status:"
git status

echo ""
echo "💾 Committing the cleanup..."
git add .
git commit -m "Remove large CSV files from Git history to comply with GitHub's 100MB limit"

echo ""
echo "🚀 Ready to push!"
echo "Run the following command to push to GitHub:"
echo ""
echo "git push --force-with-lease"
echo ""
echo "⚠️  Note: This will rewrite Git history, so coordinate with any collaborators."

