#!/usr/bin/env python3
import csv
import json
import re

def extract_keywords_from_text(text):
    """Extract meaningful keywords from text"""
    if not text:
        return []
    
    # Convert to lowercase and remove punctuation
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Filter out short words and common stop words
    stop_words = {'and', 'the', 'for', 'are', 'this', 'that', 'with', 'from', 'these', 'those', 'they', 'their'}
    keywords = [word for word in words if len(word) > 3 and word not in stop_words]
    
    return list(set(keywords))

def extract_document_types(title, description):
    """Extract document types from title and description"""
    document_types = []
    
    # Check for common document type indicators in title
    title_lower = title.lower()
    if 'report' in title_lower:
        document_types.append('report')
    if 'form' in title_lower:
        document_types.append('form')
    if 'file' in title_lower or 'files' in title_lower:
        document_types.append('file')
    if 'record' in title_lower or 'records' in title_lower:
        document_types.append('record')
    if 'list' in title_lower:
        document_types.append('list')
    if 'log' in title_lower or 'logs' in title_lower:
        document_types.append('log')
    if 'book' in title_lower or 'books' in title_lower:
        document_types.append('book')
    if 'card' in title_lower or 'cards' in title_lower:
        document_types.append('card')
    if 'application' in title_lower:
        document_types.append('application')
    if 'permit' in title_lower:
        document_types.append('permit')
    if 'license' in title_lower:
        document_types.append('license')
    if 'certificate' in title_lower:
        document_types.append('certificate')
    if 'plan' in title_lower:
        document_types.append('plan')
    if 'schedule' in title_lower:
        document_types.append('schedule')
    if 'calendar' in title_lower:
        document_types.append('calendar')
    if 'index' in title_lower:
        document_types.append('index')
    if 'register' in title_lower:
        document_types.append('register')
    if 'protest' in title_lower:
        document_types.append('protest')
    
    # Extract additional document types from description
    desc_lower = description.lower()
    if 'protest' in desc_lower and 'protest' not in document_types:
        document_types.append('protest')
    if 'assessment' in desc_lower and 'assessment' not in document_types:
        document_types.append('assessment')
    
    return document_types

def find_related_items(grs_number, title, description, category, all_items):
    """Find related GRS items based on category and keywords"""
    related_items = []
    
    # Find items in the same category
    same_category_items = [item for item in all_items 
                          if item['grsItemDispAuth'] != f'GRS-{grs_number}' 
                          and item['grsItemCategories'] == category]
    
    # Take up to 3 items from the same category
    for item in same_category_items[:3]:
        related_item_number = item['grsItemDispAuth'].replace('GRS-', '')
        related_items.append(related_item_number)
    
    # Special case handling for known relationships
    if grs_number == '949':  # Protest files
        related_items = ['948', '950', '953']
    
    return related_items[:5]  # Limit to 5 related items

def main():
    print('Creating enhanced JSONL file...')
    
    input_file = '/Users/cademc/Applications/SageMaker-Monitoring/ScheduleItems.csv'
    output_file = '/Users/cademc/Applications/SageMaker-Monitoring/enhanced_compliance_records.jsonl'
    
    # First pass to collect all items for relationship building
    all_items = []
    with open(input_file, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            all_items.append(row)
    
    # Second pass to create enhanced records
    with open(input_file, 'r') as csvfile, open(output_file, 'w') as jsonlfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            grs_item_number = row['grsItemDispAuth'].replace('GRS-', '')
            
            # Extract keywords from title and description
            title_keywords = extract_keywords_from_text(row['grsItemTitle'])
            desc_keywords = extract_keywords_from_text(row['grsItemDescription'])
            
            # Combine keywords
            keywords = list(set(title_keywords + desc_keywords))
            
            # Add category as keyword
            if row['grsItemCategories']:
                category_keywords = extract_keywords_from_text(row['grsItemCategories'])
                keywords.extend(category_keywords)
            
            # Extract document types
            document_types = extract_document_types(row['grsItemTitle'], row['grsItemDescription'])
            
            # Add category-based document type
            if row['grsItemCategories']:
                document_types.append(f"{row['grsItemCategories'].lower()} document")
            
            # Find related items
            related_items = find_related_items(grs_item_number, row['grsItemTitle'], 
                                              row['grsItemDescription'], row['grsItemCategories'], 
                                              all_items)
            
            # Create enhanced record
            enhanced_record = {
                'grs_item_number': grs_item_number,
                'title': row['grsItemTitle'],
                'description': row['grsItemDescription'],
                'retention_period': row['grsItemRetention'],
                'category': row['grsItemCategories'],
                'status': row['grsItemRevision'],
                'approved_date': row['grsItemDateApproved'],
                'document_types': list(set(document_types)),
                'keywords': list(set(keywords)),
                'related_items': related_items
            }
            
            # Write to JSONL file
            jsonlfile.write(json.dumps(enhanced_record) + '\n')
    
    print('Enhanced JSONL file created successfully!')

if __name__ == "__main__":
    main()
