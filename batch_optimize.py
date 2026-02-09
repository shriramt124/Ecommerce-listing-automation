"""
BATCH TITLE OPTIMIZER
=====================
Processes multiple titles from a file in chunks of 10 and writes results to CSV.

Usage:
    python3 batch_optimize.py batch_titles.txt

Output:
    optimized_results_TIMESTAMP.csv
"""

import os
import sys
import csv
import time
from datetime import datetime
from typing import List, Tuple

os.environ.setdefault('ADKRUX_USE_AI', 'true')

from agentic_optimizer import create_agentic_optimizer


def chunk_list(items: List[str], chunk_size: int = 10) -> List[List[str]]:
    """Split list into chunks of specified size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def process_title(optimizer, title: str, index: int) -> dict:
    """Process a single title and return results."""
    print(f"\n{'='*70}")
    print(f"Processing [{index}]: {title[:80]}...")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Minimal truth - AI will extract from title
        truth = {'product': 'Product'}
        
        # Optimize
        optimized, report = optimizer.optimize(title, truth)
        
        elapsed = time.time() - start_time
        
        result = {
            'index': index,
            'original_title': title,
            'original_length': len(title),
            'optimized_title': optimized,
            'optimized_length': len(optimized),
            'char_change': len(optimized) - len(title),
            'validation_status': 'PASS' if 180 <= len(optimized) <= 200 else 'WARNING',
            'processing_time_sec': round(elapsed, 2),
            'status': 'SUCCESS'
        }
        
        print(f"\n✅ SUCCESS")
        print(f"   Original:  {len(title)} chars")
        print(f"   Optimized: {len(optimized)} chars")
        print(f"   Time: {elapsed:.2f}s")
        
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return {
            'index': index,
            'original_title': title,
            'original_length': len(title),
            'optimized_title': '',
            'optimized_length': 0,
            'char_change': 0,
            'validation_status': 'ERROR',
            'processing_time_sec': 0,
            'status': f'ERROR: {str(e)}'
        }


def process_chunk(optimizer, chunk: List[Tuple[int, str]], chunk_num: int, total_chunks: int) -> List[dict]:
    """Process a chunk of titles."""
    print(f"\n{'#'*70}")
    print(f"# CHUNK {chunk_num}/{total_chunks} - Processing {len(chunk)} titles")
    print(f"{'#'*70}")
    
    results = []
    for index, title in chunk:
        result = process_title(optimizer, title, index)
        results.append(result)
        
        # Brief pause between titles to avoid overwhelming the LLM
        time.sleep(0.5)
    
    return results


def write_results_to_csv(results: List[dict], output_file: str):
    """Write results to CSV file."""
    fieldnames = [
        'index',
        'original_title',
        'original_length',
        'optimized_title',
        'optimized_length',
        'char_change',
        'validation_status',
        'processing_time_sec',
        'status'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Results written to: {output_file}")


def main():
    """Main batch processing function."""
    if len(sys.argv) < 2:
        print("Usage: python3 batch_optimize.py <input_file.txt>")
        print("\nExample:")
        print("  python3 batch_optimize.py batch_titles.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)
    
    # Read titles from file
    print(f"\n📂 Reading titles from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        titles = [line.strip() for line in f if line.strip()]
    
    print(f"   Found {len(titles)} titles to process")
    
    # Create chunks
    chunk_size = 10
    indexed_titles = list(enumerate(titles, start=1))
    chunks = chunk_list(indexed_titles, chunk_size)
    total_chunks = len(chunks)
    
    print(f"   Split into {total_chunks} chunks of {chunk_size} titles each")
    
    # Initialize optimizer once
    print(f"\n🤖 Initializing AI optimizer...")
    optimizer = create_agentic_optimizer()
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"optimized_results_{timestamp}.csv"
    
    # Process all chunks
    all_results = []
    start_time = time.time()
    
    for chunk_num, chunk in enumerate(chunks, start=1):
        chunk_results = process_chunk(optimizer, chunk, chunk_num, total_chunks)
        all_results.extend(chunk_results)
        
        # Write intermediate results after each chunk (in case of failure)
        temp_output = f"optimized_results_{timestamp}_chunk{chunk_num}.csv"
        write_results_to_csv(chunk_results, temp_output)
        
        print(f"\n💾 Chunk {chunk_num} results saved to: {temp_output}")
        
        # Pause between chunks
        if chunk_num < total_chunks:
            print(f"\n⏸️  Pausing 2 seconds before next chunk...")
            time.sleep(2)
    
    # Write final combined results
    write_results_to_csv(all_results, output_file)
    
    # Summary
    total_time = time.time() - start_time
    success_count = sum(1 for r in all_results if r['status'] == 'SUCCESS')
    error_count = len(all_results) - success_count
    
    print(f"\n{'='*70}")
    print(f"  BATCH PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"\n📊 SUMMARY:")
    print(f"   Total Titles: {len(titles)}")
    print(f"   Successful: {success_count}")
    print(f"   Errors: {error_count}")
    print(f"   Total Time: {total_time/60:.2f} minutes")
    print(f"   Avg Time per Title: {total_time/len(titles):.2f} seconds")
    print(f"\n📄 Final Results: {output_file}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
