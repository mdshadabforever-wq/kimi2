import re

spec_path = "scratch/full_spec.txt"

def search():
    with open(spec_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    lines = content.split('\n')
    print("Printing all lines containing 'trend':")
    for idx, line in enumerate(lines):
        if "trend" in line.lower():
            print(f"Line {idx}: {line}")

if __name__ == "__main__":
    search()
