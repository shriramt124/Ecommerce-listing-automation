"""
AGENTIC STRATEGY 2: MAIN ENTRY POINT
=====================================
Runs the AI-powered title optimizer.

Usage:
    python3 agentic_main.py

Environment:
    ADKRUX_USE_AI=true (enable AI - default true)
    ADKRUX_OLLAMA_MODEL=gpt-oss:20b-cloud (Ollama model)
"""

import os
import sys

# Ensure AI is enabled
os.environ.setdefault('ADKRUX_USE_AI', 'true')

from agentic_optimizer import create_agentic_optimizer


def run_test_cases():
    """Run the optimizer on multiple test cases."""
    
    optimizer = create_agentic_optimizer()
    
    # Test cases
    test_cases = [
        {
            'name': 'Shalimar Garbage Bags (Home Storage)',
            'title': 'Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing',
            'truth': {
                'brand': 'Shalimar',
                'product': 'Garbage Bags',
                'size': 'Medium',
                'color': 'Black',
                'count': '120 Bags (30 x 4 Rolls)',
                'dimension': '19 x 21 Inches',
                'features': ['Lavender Fragrance', 'Scented', 'Perforated Box', 'Easy Dispensing']
            }
        },
        {
            'name': 'Bike Shock Absorber (Automotive)',
            'title': 'Universal Shock Absorber Height Increaser for Bikes, Black, Aluminium, Pack of 2',
            'truth': {
                'brand': 'Universal',
                'product': 'Shock Absorber Height Increaser',
                'size': 'Universal',
                'color': 'Black',
                'count': 'Pack of 2',
                'material': 'Aluminium',
                'compatibility': 'for Bikes'
            }
        },
        {
            'name': 'Car Dustbin (Automotive + Home)',
            'title': 'Car Dustbin with Lid - Mini Garbage Bin for Car Interior | Portable Trash Can for Vehicle | Black Plastic | Leak-Proof Design',
            'truth': {
                'brand': '',
                'product': 'Car Dustbin',
                'size': 'Mini',
                'color': 'Black',
                'material': 'Plastic',
                'features': ['with Lid', 'Portable', 'Leak-Proof Design'],
                'compatibility': 'for Car'
            }
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n\n{'#'*80}")
        print(f"TEST CASE {i}: {test['name']}")
        print(f"{'#'*80}")
        
        optimized, report = optimizer.optimize(test['title'], test['truth'])
        
        results.append({
            'name': test['name'],
            'original': test['title'],
            'optimized': optimized,
            'original_len': len(test['title']),
            'optimized_len': len(optimized),
            'report': report
        })
    
    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY OF ALL OPTIMIZATIONS")
    print("="*80)
    
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name']}")
        print(f"   Original ({r['original_len']} chars): {r['original'][:80]}...")
        print(f"   Optimized ({r['optimized_len']} chars): {r['optimized'][:80]}...")
        
        delta = r['original_len'] - r['optimized_len']
        if delta > 0:
            print(f"   ✅ Saved {delta} characters")
        elif delta < 0:
            print(f"   📈 Used {abs(delta)} more characters (for better SEO)")
        else:
            print(f"   ↔️  Same length")
    
    return results


def run_single_title(title: str, truth: dict):
    """Optimize a single title."""
    optimizer = create_agentic_optimizer()
    return optimizer.optimize(title, truth)


if __name__ == "__main__":
    # Check if custom input provided via args
    if len(sys.argv) > 1:
        # Simple mode: just optimize the provided title
        title = sys.argv[1]
        print(f"Optimizing: {title}")
        
        # Minimal truth (AI will infer what it can)
        truth = {'product': 'Product'}
        
        optimized, _ = run_single_title(title, truth)
        print(f"\nResult: {optimized}")
    else:
        # Run all test cases
        run_test_cases()
