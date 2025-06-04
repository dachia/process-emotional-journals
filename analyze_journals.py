import json
from collections import defaultdict
from datetime import datetime
import re
import csv
from utils import load_json, save_json

def save_daily_stats_to_csv(entries_per_day, words_per_day, filename='daily_journal_stats.csv'):
    """Save daily statistics to a CSV file."""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['Date', 'Entries', 'Words'])
        # Write data rows
        for date in sorted(entries_per_day.keys()):
            writer.writerow([
                date,
                entries_per_day[date],
                words_per_day[date]
            ])
    print(f"\nDaily statistics have been saved to {filename}")

def analyze_journals():
    # Read the journal entries
    entries = load_json('journal_entries.json')
    
    # Initialize counters and data structures
    total_entries = len(entries)
    total_words = 0
    entries_per_day = defaultdict(int)
    words_per_day = defaultdict(int)
    entries_per_month = defaultdict(int)
    words_per_month = defaultdict(int)
    
    # Process each entry
    for entry in entries:
        # Get the date from the entry
        date_str = entry.get('date', '')
        if not date_str:
            continue
            
        # Clean and parse the date
        try:
            # Remove any time component if present
            date_str = date_str.split()[0]
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            date_key = date.isoformat()
            month_key = date.strftime('%Y-%m')  # Format: YYYY-MM
            
            # Count entries per day and month
            entries_per_day[date_key] += 1
            entries_per_month[month_key] += 1
            
            # Count words in the content
            content = entry.get('content', '')
            # Split on whitespace and filter out empty strings
            words = [word for word in re.findall(r'\b\w+\b', content.lower())]
            word_count = len(words)
            
            total_words += word_count
            words_per_day[date_key] += word_count
            words_per_month[month_key] += word_count
            
        except (ValueError, AttributeError) as e:
            print(f"Error processing date {date_str}: {e}")
            continue
    
    # Calculate and print statistics
    print("\nJournal Analysis Results:")
    print("-" * 50)
    print(f"Total number of entries: {total_entries}")
    print(f"Total number of words: {total_words}")
    print(f"Average words per entry: {total_words/total_entries:.2f}")
    
    print("\nMonthly Statistics:")
    print("-" * 50)
    print(f"{'Month':<10} {'Entries':<10} {'Total Words':<15} {'Avg Words/Entry':<20}")
    print("-" * 50)
    for month in sorted(entries_per_month.keys()):
        entries = entries_per_month[month]
        words = words_per_month[month]
        avg_words = words / entries if entries > 0 else 0
        print(f"{month:<10} {entries:<10} {words:<15} {avg_words:.2f}")
    
    print("\nDaily Statistics:")
    print("-" * 50)
    for date in sorted(entries_per_day.keys()):
        print(f"{date}: {entries_per_day[date]} entries, {words_per_day[date]} words")
    
    # Save daily statistics to CSV
    save_daily_stats_to_csv(entries_per_day, words_per_day)
    
    # Calculate some additional statistics
    days_with_entries = len(entries_per_day)
    months_with_entries = len(entries_per_month)
    print(f"\nSummary Statistics:")
    print("-" * 50)
    print(f"Number of days with entries: {days_with_entries}")
    print(f"Number of months with entries: {months_with_entries}")
    print(f"Average entries per day: {total_entries/days_with_entries:.2f}")
    print(f"Average words per day: {total_words/days_with_entries:.2f}")
    print(f"Average entries per month: {total_entries/months_with_entries:.2f}")
    print(f"Average words per month: {total_words/months_with_entries:.2f}")

if __name__ == "__main__":
    analyze_journals() 