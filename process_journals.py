import json
import os
from pathlib import Path
import shutil
from datetime import datetime
import frontmatter
import re
from typing import Dict, List, Optional, Tuple

def find_first_section_occurrence(entries: List[Dict], section_name: str) -> Optional[str]:
    """Find the first occurrence of a section across all entries"""
    earliest_date = None
    earliest_datetime = None
    
    for entry in entries:
        content = entry.get('content', '')
        date = entry.get('date')
        
        if not date or not content:
            continue
            
        # Look for the section in the content
        if section_name in content:
            try:
                entry_date = datetime.strptime(date, '%Y-%m-%d')
                if earliest_datetime is None or entry_date < earliest_datetime:
                    earliest_datetime = entry_date
                    earliest_date = date
            except ValueError:
                continue
    
    return earliest_date

def get_section_name(content: str) -> Optional[str]:
    """Extract the first section name from content"""

    section_headers = [
        '## 🌀What do I feel right this moment?',
        '## 🔍Where is it coming from?',
        '## 🛤️Do I need to solve it? How?',
        '## emotion dump',
        '### Journal'
    ]
    lines = content.split('\n')
    for line in reversed(lines):
        line = line.strip()
        if line.startswith('##'):
            if line in section_headers:
                return line
            else:
                return None
    return None

def clean_emotional_content(content: str) -> str:
    """Clean up emotional content by removing section headers and extra whitespace"""
    lines = content.split('\n')
    cleaned_lines = []
    skip_next = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip section headers and their descriptions
        if line.startswith('## ') or line.startswith('### '):
            skip_next = True
            continue
        if skip_next and line.startswith('>'):
            continue
        skip_next = False
        
        # Skip task lines
        if line.startswith('- [') or line.startswith('\t- ['):
            continue
            
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()

def process_journals():
    # Load the processed journal entries
    with open('journal_entries.json', 'r', encoding='utf-8') as f:
        entries = json.load(f)
    
    # Create output directory for emotional journals
    output_dir = "📁06 - Emotional Journals"
    os.makedirs(output_dir, exist_ok=True)
    
    # Track statistics
    created_count = 0
    skipped_count = 0
    
    for entry in entries:
        file_path = entry['file_path']
        emotional_content = entry['emotional_content']
        date = entry['date']
        content = entry.get('content', '')
        
        # Skip if no date (can't process)
        if not date:
            print(f"Skipping {file_path}: No date found")
            skipped_count += 1
            continue
            
        # Skip if no emotional content
        if not emotional_content.strip():
            print(f"Skipping {file_path}: No emotional content")
            skipped_count += 1
            continue
            
        # If file is already an emotional journal, copy it to target dir
        if "🧠 Emotional Journal" in os.path.basename(file_path):
            new_path = os.path.join(output_dir, os.path.basename(file_path))
            shutil.copy2(file_path, new_path)
            print(f"Copied existing emotional journal: {new_path}")
            created_count += 1
            continue
        # Get the section name from the content
        section_name = get_section_name(content)
            
        # Find the first occurrence of this section across all entries
        version_date = find_first_section_occurrence(entries, section_name or "")
        if not version_date:
            version_date = date  # Fallback to file date if no section found
        
        # Clean up the emotional content
        cleaned_content = clean_emotional_content(emotional_content)
        
        # Create new metadata
        metadata = {
            'tags': ['daily', 'mental-health', 'journal'],
            'version': version_date,
            'section': section_name,  # Add section name to metadata for reference
            'source_file': file_path  # Add reference to original file
        }
        
        # Create new content with frontmatter
        new_content = frontmatter.dumps(frontmatter.Post(cleaned_content, **metadata))
        
        # New filename includes the prefix
        new_filename = f"🧠 Emotional Journal {date}.md"
        new_path = os.path.join(output_dir, new_filename)
        
        # Check if target file already exists
        if os.path.exists(new_path):
            print(f"Cannot create {new_path}: File already exists")
            skipped_count += 1
            continue
            
        try:
            # Write new content
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"Created emotional journal: {new_path}")
            print(f"  Section: {section_name}")
            print(f"  Version date: {version_date}")
            created_count += 1
            
        except Exception as e:
            print(f"Error creating {new_path}: {str(e)}")
            skipped_count += 1
    
    # Print summary
    print("\nProcessing Summary:")
    print(f"Created emotional journals: {created_count}")
    print(f"Skipped files: {skipped_count}")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    process_journals() 