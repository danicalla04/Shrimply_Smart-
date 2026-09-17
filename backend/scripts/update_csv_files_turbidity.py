import os
import sys
import pandas as pd

# Conversion formula
def convert_do_to_turbidity(do_value):
    """Convert dissolved oxygen to turbidity using inverse formula"""
    try:
        do_val = float(do_value)
        turbidity = 4.5 - (0.4 * do_val)
        # Clamp between 0.5 and 4.0 NTU
        return max(0.5, min(4.0, round(turbidity, 2)))
    except:
        return None

# Set up paths
input_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'input', 'small-aquaculture-fishpond')
dataset_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'dataset', 'data')

files = [
    ('pond_iot_2023.csv', input_dir),
    ('pond_iot_2023_enhanced.csv', input_dir),
]

for filename, file_dir in files:
    input_file = os.path.join(file_dir, filename)
    output_file = os.path.join(file_dir, filename)  # Overwrite original
    
    if not os.path.exists(input_file):
        print(f"[SKIP] {filename} - File not found")
        continue
    
    print(f"\nProcessing: {filename}")
    print("=" * 60)
    
    # Read CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} records")
    print(f"Columns: {list(df.columns)}")
    
    # Check if dissolved_oxygen column exists
    if 'dissolved_oxygen' not in df.columns:
        print("[SKIP] dissolved_oxygen column not found")
        continue
    
    # Convert DO to turbidity
    print("Converting dissolved_oxygen to turbidity...")
    df['turbidity'] = df['dissolved_oxygen'].apply(convert_do_to_turbidity)
    
    # Drop the old column
    df = df.drop('dissolved_oxygen', axis=1)
    
    # Show statistics
    print(f"\nTurbidity Statistics:")
    print(f"  Min:    {df['turbidity'].min()}")
    print(f"  Max:    {df['turbidity'].max()}")
    print(f"  Mean:   {df['turbidity'].mean():.2f}")
    print(f"  StDev:  {df['turbidity'].std():.2f}")
    
    # Save updated CSV
    df.to_csv(output_file, index=False)
    print(f"\n[OK] Updated file saved: {filename}")
    print(f"Records: {len(df)}")

print("\n" + "=" * 60)
print("[SUCCESS] All CSV files updated!")
