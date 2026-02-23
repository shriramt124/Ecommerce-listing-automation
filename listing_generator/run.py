#!/usr/bin/env python3
"""
LISTING GENERATOR — CLI ENTRY POINT
====================================

Usage:
    # Basic run (title + content only):
    python3 listing_generator/run.py --client input/lqs-GMR_AE.xlsx

    # With browse-node keyword ingestion:
    python3 listing_generator/run.py \\
        --client input/lqs-Kakks_uk.xlsx \\
        --browse-nodes input/Browse_Node_UK/ \\
        --ingest-keywords

    # Full run with image generation:
    python3 listing_generator/run.py \\
        --client input/lqs-GMR_AE.xlsx \\
        --browse-nodes input/Browse_Node_AE/ \\
        --generate-images \\
        --output output/gmr_ae_listing.xlsx

    # Override Gemini model:
    python3 listing_generator/run.py \\
        --client input/lqs-GMR_AE.xlsx \\
        --gemini-model gemini-2.5-flash
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure parent directory is importable
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

# Load .env from the project root
from dotenv import load_dotenv
load_dotenv(os.path.join(_PARENT_DIR, ".env"))

from listing_generator.master_pipeline import ListingPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Amazon Listing Generator — generate optimized titles, "
                    "bullet points, descriptions, search terms, and images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --client input/lqs-GMR_AE.xlsx
  %(prog)s --client input/lqs-Kakks_uk.xlsx --browse-nodes input/Browse_Node_UK/ --ingest-keywords
  %(prog)s --client input/lqs-GMR_AE.xlsx --generate-images --output output/results.xlsx
        """,
    )

    parser.add_argument(
        "--client",
        required=True,
        help="Path to client Excel file (lqs-GMR_AE.xlsx, lqs-Kakks_uk.xlsx, etc.)",
    )
    parser.add_argument(
        "--browse-nodes",
        default=None,
        help="Path to browse-node keyword CSV directory",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: listing_output/run_YYYYMMDD_HHMMSS/)",
    )
    parser.add_argument(
        "--ingest-keywords",
        action="store_true",
        help="Ingest browse-node keyword CSVs into vector DB before running",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="Generate product images (main, lifestyle, why-choose-us) via Gemini AI",
    )
    parser.add_argument(
        "--images-only",
        action="store_true",
        help="Skip text optimization and only generate images (uses original title/bullets)",
    )
    parser.add_argument(
        "--gemini-key",
        default=None,
        help="Gemini API key override (default: from GEMINI_API_KEY env var)",
    )
    parser.add_argument(
        "--gemini-model",
        default=None,
        help="Gemini model override (default: from GEMINI_TEXT_MODEL env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N products from the Excel file",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Skip the first N products (for resume after crash)",
    )

    parser.add_argument(
        "--keyword-index",
        default=None,
        help="Path to a specific keyword index file (.npz) to use",
    )
    parser.add_argument(
        "--search-terms-only",
        action="store_true",
        help="Only regenerate search terms (skips image analysis, title, bullets, description, images). "
             "Requires --analysis-dir pointing to cached analysis JSONs.",
    )
    parser.add_argument(
        "--analysis-dir",
        default=None,
        help="Path to directory with cached {ASIN}_analysis.json files (from a previous run)",
    )
    parser.add_argument(
        "--banner-image-only",
        action="store_true",
        help="Only generate the 1200x628px Sponsored Brand Ad banner (skip all other images)",
    )
    parser.add_argument(
        "--lifestyle-image-only",
        action="store_true",
        help="Only generate the 4 lifestyle images (skip main/banner/infographic)",
    )
    parser.add_argument(
        "--main-image-only",
        action="store_true",
        help="Only generate the main studio product image (skip lifestyle/banner/infographic)",
    )
    parser.add_argument(
        "--why-choose-us-only",
        action="store_true",
        help="Only generate the Why Choose Us infographic (skip main/lifestyle/banner)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.client):
        print(f"❌ Client Excel not found: {args.client}")
        sys.exit(1)

    if args.browse_nodes and not os.path.exists(args.browse_nodes):
        print(f"❌ Browse-node directory not found: {args.browse_nodes}")
        sys.exit(1)

    if args.ingest_keywords and not args.browse_nodes:
        print("❌ --ingest-keywords requires --browse-nodes")
        sys.exit(1)

    if args.search_terms_only and not args.analysis_dir:
        print("❌ --search-terms-only requires --analysis-dir pointing to cached analysis JSONs.")
        sys.exit(1)

    if args.analysis_dir and not os.path.isdir(args.analysis_dir):
        print(f"❌ Analysis directory not found: {args.analysis_dir}")
        sys.exit(1)

    if args.skip > 0 and not args.output:
        print("⚠️  --skip without --output will create a new folder — previous rows won't be loaded.")
        print("   Use --output <same_dir_as_first_run> to append to the existing Excel.")

    # Validate: only one image-type flag at a time
    image_only_flags = [args.banner_image_only, args.lifestyle_image_only, args.main_image_only, args.why_choose_us_only]
    if sum(bool(f) for f in image_only_flags) > 1:
        print("❌ Only one of --banner-image-only / --lifestyle-image-only / --main-image-only / --why-choose-us-only can be used at a time.")
        sys.exit(1)

    # Run pipeline
    pipeline = ListingPipeline(
        client_excel=args.client,
        browse_node_dir=args.browse_nodes,
        output_dir=args.output,
        generate_images=args.generate_images,
        images_only=args.images_only,
        ingest_keywords=args.ingest_keywords,
        gemini_api_key=args.gemini_key,
        gemini_model=args.gemini_model,
        limit=args.limit,
        skip=args.skip,
        keyword_index_path=args.keyword_index,
        search_terms_only=args.search_terms_only,
        analysis_dir=args.analysis_dir,
        banner_image_only=args.banner_image_only,
        lifestyle_image_only=args.lifestyle_image_only,
        main_image_only=args.main_image_only,
        why_choose_us_only=args.why_choose_us_only,
    )

    output_path = pipeline.run()

    if output_path:
        print(f"\n✅ Done! Output at: {output_path}")
    else:
        print("\n❌ Pipeline completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
