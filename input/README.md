# Input Folder
Place your client files here before running the listing generator.

## Required Files

### Client Excel Files
- `lqs-GMR_AE.xlsx` — GMR products for UAE market
- `lqs-Kakks_uk.xlsx` — Kakks products for UK market
- Any other client Excel file with columns: ASIN, Title, Images, Country, etc.

### Browse Node Keyword CSVs (optional)
Create subfolders for each market's keywords:
- `Browse_Node_UK/` — UK market keyword research CSVs
- `Browse_Node_AE/` — UAE market keyword research CSVs

Each folder should contain CSV files from Amazon keyword research tools, e.g.:
```
Browse_Node_UK/
  KeywordResearch_Home_Home Storage & Organization_Waste & Recycling_30_22-12-2025_17-27-42.csv
  KeywordResearch_Automotive_Motorbike Accessories & Parts_Handlebars & Forks_30_22-12-2025_18-56-04.csv
```

## Usage
```bash
cd /path/to/agentic_strategy_2

# Basic run:
python3 listing_generator/run.py --client input/lqs-GMR_AE.xlsx

# With keyword ingestion:
python3 listing_generator/run.py \
    --client input/lqs-Kakks_uk.xlsx \
    --browse-nodes input/Browse_Node_UK/ \
    --ingest-keywords

# Full run with image generation:
python3 listing_generator/run.py \
    --client input/lqs-GMR_AE.xlsx \
    --browse-nodes input/Browse_Node_AE/ \
    --generate-images
```
