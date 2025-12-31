#!/usr/bin/env python3
"""Test script to demonstrate improved query generation."""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from agentic_agents import QueryPlannerAgent
from agentic_llm import OllamaConfig, OllamaLLM

def test_query_generation():
    """Test the improved query generation with the Shalimar example."""
    
    # Example product from user's request
    title = "Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing"
    
    truth = {
        "brand": "shalimar",
        "product": "garbage bags",
        "color": "black",
        "size": "medium",
        "dimension": "19 X 21 inches",
        "count": "120 bags",
        "material": "",
        "compatibility": "",
        "features": ["scented", "lavender fragrance", "perforated box"]
    }
    
    category_info = {
        "category": "home_storage",
        "subcategory": "garbage_bags", 
        "search_priorities": ["garbage bags", "trash bags", "kitchen bags"],
        "key_attributes": ["scented", "medium size", "black"]
    }
    
    # Initialize agent (with or without LLM for testing)
    try:
        config = OllamaConfig(model="gemma3:4b", base_url="http://localhost:11434")
        llm = OllamaLLM(config)
        if llm.test_connection():
            agent = QueryPlannerAgent(llm)
            print("✅ Using AI-enhanced query generation")
        else:
            agent = QueryPlannerAgent(None)
            print("⚠️ AI not available, using systematic generation only")
    except:
        agent = QueryPlannerAgent(None)
        print("⚠️ AI not available, using systematic generation only")
    
    # Generate queries
    print("\n" + "="*80)
    print("IMPROVED QUERY GENERATION TEST")
    print("="*80)
    print(f"\nProduct: {truth.get('brand', 'N/A').title()} {truth.get('product', 'N/A')}")
    print(f"Color: {truth.get('color', 'N/A')}")
    print(f"Size: {truth.get('size', 'N/A')}")
    print(f"Attributes: {[attr for attr in truth.get('features', []) if attr != 'lavender fragrance']}")
    print(f"Category: {category_info.get('category', 'N/A')} > {category_info.get('subcategory', 'N/A')}")
    
    print(f"\n🎯 EXPECTED QUERIES (from user request):")
    print("1. shalimar garbage bags")
    print("2. shalimar black garbage bags")
    print("3. garbage bags medium size")
    print("4. black garbage bags medium size")
    print("5. shalimar scented garbage bags")
    print("6. black garbage bags medium")
    
    # Extract attributes manually for testing
    attrs = agent._extract_product_attributes(title, truth, category_info)
    
    print(f"\n🔍 EXTRACTED ATTRIBUTES:")
    for key, value in attrs.items():
        if value:
            print(f"  {key}: {value}")
    
    # Generate systematic queries
    systematic_queries = agent._generate_systematic_queries(attrs, [])
    
    print(f"\n✅ GENERATED QUERIES ({len(systematic_queries)} total):")
    print("-" * 60)
    
    # Group queries by type for better visualization
    brand_queries = [q for q in systematic_queries if 'shalimar' in q]
    color_queries = [q for q in systematic_queries if 'black' in q and 'shalimar' not in q]
    size_queries = [q for q in systematic_queries if 'medium' in q]
    comprehensive_queries = [q for q in systematic_queries if 'shalimar' in q and 'black' in q and 'medium' in q]
    
    print("🏷️ BRAND + CATEGORY:")
    for i, q in enumerate(brand_queries[:5], 1):
        print(f"  {i:2d}. {q}")
    
    print("\n🟫 COLOR + CATEGORY:")
    for i, q in enumerate(color_queries[:5], 1):
        print(f"  {i:2d}. {q}")
    
    print("\n📏 SIZE + CATEGORY:")
    for i, q in enumerate(size_queries[:5], 1):
        print(f"  {i:2d}. {q}")
    
    print("\n🎯 COMPREHENSIVE (Brand + Color + Size):")
    for i, q in enumerate(comprehensive_queries[:3], 1):
        print(f"  {i:2d}. {q}")
    
    print("\n📋 ALL GENERATED QUERIES:")
    for i, q in enumerate(systematic_queries, 1):
        print(f"  {i:2d}. {q}")
    
    # Check if expected queries are generated
    print(f"\n🎯 VALIDATION - Expected queries found:")
    expected = [
        "shalimar garbage bags",
        "shalimar black garbage bags", 
        "garbage bags medium size",
        "black garbage bags medium size",
        "shalimar scented garbage bags"
    ]
    
    found_count = 0
    for expected_query in expected:
        if expected_query in systematic_queries:
            print(f"  ✅ {expected_query}")
            found_count += 1
        else:
            print(f"  ❌ {expected_query}")
    
    print(f"\n📊 SUMMARY:")
    print(f"  • Total queries generated: {len(systematic_queries)}")
    print(f"  • Expected queries found: {found_count}/{len(expected)}")
    print(f"  • Coverage: {(found_count/len(expected)*100):.1f}%")
    
    # Test with different product types
    print(f"\n" + "="*80)
    print("GENERALIZATION TEST - Different Product Categories")
    print("="*80)
    
    test_products = [
        {
            "name": "Phone Case",
            "title": "Apple iPhone 15 Pro Clear Case | Slim | Transparent | (Clear)",
            "truth": {"brand": "apple", "product": "phone case", "color": "clear", "size": "slim"},
            "category": {"category": "electronics", "subcategory": "phone_cases"}
        },
        {
            "name": "Car Part", 
            "title": "Honda Civic Front Brake Pad Set | Heavy Duty | (Black) | for Honda Civic 2016-2021",
            "truth": {"brand": "honda", "product": "brake pad", "color": "black", "size": "front"},
            "category": {"category": "automotive", "subcategory": "car_parts"}
        }
    ]
    
    for product in test_products:
        print(f"\n📱 Testing: {product['name']}")
        attrs_test = agent._extract_product_attributes(
            product['title'], 
            product['truth'], 
            product['category']
        )
        queries_test = agent._generate_systematic_queries(attrs_test, [])
        
        print(f"  Generated {len(queries_test)} queries:")
        for q in queries_test[:5]:
            print(f"    • {q}")
    
    return systematic_queries

if __name__ == "__main__":
    test_query_generation()
