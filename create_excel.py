
import pandas as pd

# Columns from the reference file
columns = [
    'client_id', 'country', 'asin', 'title_x', 'Brand', 'rating', 'browse node',
    'bullet_1', 'bullet_2', 'bullet_3', 'bullet_4', 'bullet_5', 'bullet_6', 'bullet_7',
    'title_y', 'child_category', 'child_rank', 'parent_category', 'parent_rank',
    'image_MAIN', 'image_PT01', 'image_PT02', 'image_PT03', 'image_PT04',
    'image_PT05', 'image_PT06', 'image_PT07', 'image_PT08'
]

# Create an empty dataframe with these columns
df = pd.DataFrame(columns=columns)

# Data for the new row
new_row = {col: None for col in columns}
new_row['asin'] = 'B0TESTIMAGE1'  # Placeholder ASIN
new_row['image_MAIN'] = 'https://m.media-amazon.com/images/I/61mTcNG6TIL._AC_SL1500_.jpg'
new_row['image_PT01'] = 'https://m.media-amazon.com/images/I/71aT2k2KufL._AC_SL1500_.jpg'
new_row['image_PT02'] = 'https://m.media-amazon.com/images/I/61INLkYWnxL._AC_SL1500_.jpg'
new_row['image_PT03'] = 'https://m.media-amazon.com/images/I/71Ln42UpqCL._AC_SL1500_.jpg'

# Append row
df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Save to Excel
output_file = '/Users/shriramtiwari/adkrux/agentic_strategy_2/image_only_input.xlsx'
df.to_excel(output_file, index=False)
print(f"Created {output_file}")
