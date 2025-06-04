import os
from openai import OpenAI
from utils import get_openai_client, ensure_directory

def read_phase_file(filename):
    """Read entries from a phase file and return them as a list of (date, text) tuples."""
    entries = []
    current_date = None
    current_text = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('Date: '):
                # Save previous entry if exists
                if current_date and current_text:
                    entries.append((current_date, '\n'.join(current_text)))
                # Start new entry
                current_date = line[6:]  # Remove 'Date: ' prefix
                current_text = []
            elif line:  # Non-empty line that's not a date
                current_text.append(line)
    
    # Don't forget the last entry
    if current_date and current_text:
        entries.append((current_date, '\n'.join(current_text)))
    
    return entries

def format_entries_for_gpt(entries, phase_name):
    """Format entries for GPT prompt."""
    formatted = f"### {phase_name} Entries:\n"
    for i, (date, text) in enumerate(entries, 1):
        formatted += f"<entry {i}>\nDate: {date}\n{text}\n</entry>\n\n"
    return formatted

def analyze_with_gpt(early_entries, middle_entries, late_entries):
    """Send formatted entries to GPT for analysis."""
    client = get_openai_client()
    
    # Format the prompt
    prompt = """Analyze the following journal entries split into three phases: Early, Middle, and Late.

Tasks:
1. Identify how the author's relationship to their emotions and self changed over time.
2. Find and list 2–3 specific quotes per phase showing the shift from resistance to alignment and self-acceptance.
3. Summarize the evolution of emotional tone and self-perception over the three phases (in bullet points or timeline format).
4. Based on this evolution, suggest what core beliefs or principles emerged by the Late phase.

Return:
- A short paragraph per phase summarizing the emotional state and mindset.
- Key quotes (2–3 per phase) illustrating the phase.
- A list of "Core Beliefs" that emerged by the Late phase.

"""

    # Add formatted entries to prompt
    prompt += format_entries_for_gpt(early_entries, "Early Phase")
    prompt += format_entries_for_gpt(middle_entries, "Middle Phase")
    prompt += format_entries_for_gpt(late_entries, "Late Phase")
    
    # Get analysis from GPT
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",  # Using GPT-4 for better analysis
        messages=[
            {"role": "system", "content": "You are an insightful analyst of emotional journal entries, focusing on patterns of emotional growth and self-perception."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content

def main():
    # Read entries from each phase file
    early_entries = read_phase_file('early_phase_entries.txt')
    middle_entries = read_phase_file('middle_phase_entries.txt')
    late_entries = read_phase_file('late_phase_entries.txt')
    
    # Get analysis from GPT
    analysis = analyze_with_gpt(early_entries, middle_entries, late_entries)
    
    # Save analysis to file
    with open('phase_analysis.txt', 'w', encoding='utf-8') as f:
        f.write(analysis)
    
    print("Analysis complete! Results saved to phase_analysis.txt")

if __name__ == "__main__":
    main() 