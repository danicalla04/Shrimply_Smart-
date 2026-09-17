import pandas as pd
import os

file_path = r'c:\wamp64\www\Shrimply_Smart\input\small-aquaculture-fishpond\pond_iot_2023_enhanced.csv'

# Read file
df = pd.read_csv(file_path)

print(f"Original columns: {list(df.columns)}")
print(f"Records: {len(df)}")

# Conversion function
def convert_do_to_turbidity(do_value):
    try:
        do_val = float(do_value)
        turbidity = 4.5 - (0.4 * do_val)
        return max(0.5, min(4.0, round(turbidity, 2)))
    except:
        return None

# Convert
print("Converting dissolved_oxygen to turbidity...")
df['turbidity'] = df['dissolved_oxygen'].apply(convert_do_to_turbidity)
df = df.drop('dissolved_oxygen', axis=1)

print(f"New columns: {list(df.columns)}")
print(f"Turbidity statistics:")
print(f"  Min: {df['turbidity'].min()}")
print(f"  Max: {df['turbidity'].max()}")
print(f"  Mean: {df['turbidity'].mean():.2f}")

# Save
df.to_csv(file_path, index=False)
print(f"\n[OK] File updated: {os.path.basename(file_path)}")
