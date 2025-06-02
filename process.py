import os
from pathlib import Path
import markdown
import frontmatter
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import json
import re

class JournalEntry:
    def __init__(self, file_path: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.content = content
        self.metadata = self._process_metadata(metadata) if metadata else {}
        self.date = self._extract_date_from_path(file_path)
        self.tasks = self._extract_tasks(content)
        self.emotional_content = self._extract_emotional_content(content)
        
    def _process_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert date objects in metadata to strings"""
        processed = {}
        for key, value in metadata.items():
            if isinstance(value, (date, datetime)):
                processed[key] = value.isoformat()
            else:
                processed[key] = value
        return processed

    def _extract_date_from_path(self, file_path: str) -> Optional[str]:
        """Extract date from file path (format: YYYY-MM-DD.md or 🧠 Emotional Journal YYYY-MM-DD.md)"""
        try:
            filename = os.path.basename(file_path)
            # Remove .md extension
            name_without_ext = filename.rsplit('.', 1)[0]
            
            # Try to find date pattern YYYY-MM-DD in the filename
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', name_without_ext)
            if date_match:
                date_str = date_match.group(1)
                # Validate date format
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            return None
        except (ValueError, IndexError):
            return None

    def _extract_tasks(self, content: str) -> List[Dict[str, Any]]:
        """Extract tasks from markdown content"""
        tasks = []
        lines = content.split('\n')
        current_task = None
        current_subtasks = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for main task
            if line.startswith('- [') and ']' in line:
                # Save previous task if exists
                if current_task:
                    task_dict = {
                        'task': current_task,
                        'subtasks': current_subtasks,
                        'completed': 'x' in current_task[:4]
                    }
                    # Debug: Check for date objects in task
                    self._debug_check_date_objects(task_dict, f"Task in {self.file_path}: {current_task}")
                    tasks.append(task_dict)
                
                # Start new task
                current_task = line[line.find(']') + 1:].strip()
                current_subtasks = []
                
            # Check for subtask (indented)
            elif line.startswith('\t- [') and ']' in line and current_task:
                subtask = line[line.find(']') + 1:].strip()
                subtask_dict = {
                    'task': subtask,
                    'completed': 'x' in line[:line.find(']') + 1]
                }
                # Debug: Check for date objects in subtask
                self._debug_check_date_objects(subtask_dict, f"Subtask in {self.file_path}: {subtask}")
                current_subtasks.append(subtask_dict)
        
        # Add last task if exists
        if current_task:
            task_dict = {
                'task': current_task,
                'subtasks': current_subtasks,
                'completed': 'x' in current_task[:4]
            }
            # Debug: Check for date objects in last task
            self._debug_check_date_objects(task_dict, f"Last task in {self.file_path}: {current_task}")
            tasks.append(task_dict)
            
        return tasks

    def _debug_check_date_objects(self, obj: Any, context: str) -> None:
        """Helper function to check for date objects in dictionaries"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (date, datetime)):
                    print(f"Found date object in {context}")
                    print(f"Key: {key}, Value: {value}, Type: {type(value)}")
                elif isinstance(value, dict):
                    self._debug_check_date_objects(value, f"{context} -> {key}")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        self._debug_check_date_objects(item, f"{context} -> {key}[{i}]")

    def _extract_emotional_content(self, content: str) -> str:
        """Extract emotional/reflective content based on presence of emotion sections"""
        lines = content.split('\n')
        emotional_lines = []
        non_task_lines = []
        
        # Define section headers
        section_headers = [
            '## 🌀What do I feel right this moment?',
            '## 🔍Where is it coming from?',
            '## 🛤️Do I need to solve it? How?',
            '## emotion dump',
            '### Journal'
        ]
        
        # Track sections and their content
        current_section = None
        section_content = []
        sections = {}
        has_sections = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a section header
            if line in section_headers:
                has_sections = True
                # Save previous section if it had content
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content)
                # Start new section
                current_section = line
                section_content = []
            # Skip task lines
            elif line.startswith('- [') or line.startswith('\t- ['):
                continue
            # Add content to current section if we're in one
            elif current_section:
                section_content.append(line)
            # If no sections found, collect all non-task content
            elif not has_sections and not line.startswith('#'):
                non_task_lines.append(line)
        
        # Save last section if it had content
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content)
        
        # If structured content exists, format it with headers
        if has_sections:
            if sections:
                for header, content in sections.items():
                    if content.strip():  # Only add if there's non-whitespace content
                        emotional_lines.append(header)
                        emotional_lines.append(content)
                        emotional_lines.append('')  # Add blank line between sections
                return '\n'.join(emotional_lines).strip()
            else:
                return ''
        
        # If no structured content, return all non-task content
        return '\n'.join(non_task_lines).strip()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary format"""
        entry_dict = {
            'file_path': self.file_path,
            'date': self.date,
            'tasks': self.tasks,
            'emotional_content': self.emotional_content,
            'content': self.content,
            'metadata': self.metadata
        }
        # Debug: Check for date objects in the entire entry
        self._debug_check_date_objects(entry_dict, f"Entry {self.file_path}")
        return entry_dict

class JournalProcessor:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.entries: List[JournalEntry] = []
        
    def process_directory(self) -> None:
        """Process all markdown files in the directory and subdirectories"""
        for file_path in self.root_dir.rglob('*.md'):
            try:
                # Read and parse the markdown file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Try to parse frontmatter if it exists
                try:
                    post = frontmatter.loads(content)
                    entry = JournalEntry(
                        str(file_path),
                        post.content,
                        post.metadata
                    )
                except:
                    # If no frontmatter, just use the content
                    entry = JournalEntry(str(file_path), content)
                
                self.entries.append(entry)
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
    
    def save_to_json(self, output_file: str) -> None:
        """Save processed entries to a JSON file"""
        entries_dict = [entry.to_dict() for entry in self.entries]
        # Debug: Print the first problematic entry if any
        for i, entry in enumerate(entries_dict):
            try:
                json.dumps(entry)
            except TypeError as e:
                print(f"Problematic entry found at index {i}:")
                print(f"File: {entry.get('file_path')}")
                print(f"Error: {str(e)}")
                raise
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entries_dict, f, ensure_ascii=False, indent=2)

def main():
    # Initialize processor with the journal directory
    processor = JournalProcessor('📁06 - Journal')
    
    # Process all files
    print("Processing journal entries...")
    processor.process_directory()
    
    # Save results
    output_file = 'journal_entries.json'
    processor.save_to_json(output_file)
    print(f"Processed {len(processor.entries)} entries")
    print(f"Results saved to {output_file}")

if __name__ == "__main__":
    main()
