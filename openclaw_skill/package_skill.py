#!/usr/bin/env python3
import sys
import os
import zipfile

def package_skill(target_dir):
    # Remove trailing slash if present
    target_dir = target_dir.rstrip('/\\')
    
    if not os.path.isdir(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.")
        sys.exit(1)
        
    skill_name = os.path.basename(os.path.abspath(target_dir))
    output_filename = f"{skill_name}.skill"
    
    # Check for required SKILL.md
    if not os.path.isfile(os.path.join(target_dir, 'SKILL.md')):
        print(f"Error: {target_dir}/SKILL.md is missing. A valid skill must contain this file.")
        sys.exit(1)

    print(f"Packaging {target_dir} into {output_filename}...")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(target_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate relative path to keep structure inside the zip clean
                arcname = os.path.relpath(file_path, os.path.dirname(target_dir))
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
                
    print(f"\nSuccess! Created: {output_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 package_skill.py <skill_directory>")
        sys.exit(1)
        
    package_skill(sys.argv[1])
