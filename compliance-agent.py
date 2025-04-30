#!/usr/bin/env python3
import boto3
import json
import streamlit as st
import time
from datetime import datetime
import pandas as pd
import PyPDF2
import io
import docx

# Initialize the Bedrock Agent Runtime client
client = boto3.client('bedrock-agent-runtime', region_name='us-west-2')

# Agent alias ARN
agent_id = "<agent_id>  # Supervisor agent
agent_alias_id = "<alias_id>"  # agent alias

# Function to extract text from PDF with size limiting
def extract_text_from_pdf(pdf_file, max_pages=10, max_chars=50000):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        total_pages = len(pdf_reader.pages)
        
        # Get metadata about the document
        metadata = {
            "total_pages": total_pages,
            "processed_pages": min(max_pages, total_pages),
            "truncated": total_pages > max_pages
        }
        
        # Extract text from the first max_pages pages
        for page_num in range(min(max_pages, total_pages)):
            page_text = pdf_reader.pages[page_num].extract_text() + "\n"
            text += page_text
            
            # Check if we've exceeded the character limit
            if len(text) > max_chars:
                text = text[:max_chars]
                metadata["truncated"] = True
                metadata["truncation_reason"] = "character_limit"
                break
        
        return text, metadata
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return "Error extracting text from PDF. The file may be corrupted or password-protected.", {"error": str(e)}

# Function to extract text from DOCX with size limiting
def extract_text_from_docx(docx_file, max_chars=50000):
    try:
        doc = docx.Document(docx_file)
        text = ""
        metadata = {
            "total_paragraphs": len(doc.paragraphs),
            "processed_paragraphs": 0,
            "truncated": False
        }
        
        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
            metadata["processed_paragraphs"] += 1
            
            # Check if we've exceeded the character limit
            if len(text) > max_chars:
                text = text[:max_chars]
                metadata["truncated"] = True
                metadata["truncation_reason"] = "character_limit"
                break
        
        return text, metadata
    except Exception as e:
        st.error(f"Error extracting text from DOCX: {str(e)}")
        return "Error extracting text from DOCX. The file may be corrupted.", {"error": str(e)}

# Function to clear chat history
def clear_chat_history():
    st.session_state.chat_history = []

# Function to reset document and evaluation
def reset_document():
    st.session_state.document_text = ""
    st.session_state.evaluation_results = None
    st.session_state.chat_history = []

# Function to analyze document content for better classification
def analyze_document_content(document_text):
    """
    Pre-process and analyze document content to extract key metadata
    that will help with classification and compliance determination based on
    Utah's General Records Schedule (GRS) categories
    """
    metadata = {
        "detected_date": None,
        "detected_grs_category": None,
        "detected_document_type": None,
        "word_count": len(document_text.split()),
        "contains_financial_data": any(term in document_text.lower() for term in ["budget", "cost", "expense", "financial", "dollar", "$"]),
        "contains_meeting_terms": any(term in document_text.lower() for term in ["meeting", "minutes", "attendees", "agenda"]),
        "contains_report_terms": any(term in document_text.lower() for term in ["report", "summary", "quarterly", "monthly", "annual"]),
        "contains_policy_terms": any(term in document_text.lower() for term in ["policy", "regulation", "guideline", "procedure", "standard"]),
        "contains_legal_terms": any(term in document_text.lower() for term in ["legal", "law", "statute", "compliance", "requirement"]),
        "contains_administrative_terms": any(term in document_text.lower() for term in ["administrative", "administration", "management", "operations"]),
        "contains_personnel_terms": any(term in document_text.lower() for term in ["personnel", "employee", "staff", "hiring", "recruitment"])
    }
    
    # Extract potential date
    import re
    from datetime import datetime
    
    date_patterns = [
        r'(\w+\s+\d{1,2},\s+\d{4})',  # January 1, 2025
        r'(\d{1,2}/\d{1,2}/\d{4})',   # 1/1/2025
        r'(\d{4}-\d{2}-\d{2})',       # 2025-01-01
        r'Date:\s*(.+?\d{4})'         # Date: April 15, 2025
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, document_text)
        if matches:
            metadata["detected_date"] = matches[0]
            # Try to parse the date into a datetime object
            try:
                # Try different date formats
                date_formats = [
                    "%Y-%m-%d",           # 2025-01-01
                    "%m/%d/%Y",           # 1/1/2025
                    "%B %d, %Y",          # January 1, 2025
                    "%b %d, %Y"           # Jan 1, 2025
                ]
                
                parsed_date = None
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(matches[0], fmt)
                        break
                    except ValueError:
                        continue
                
                if parsed_date:
                    metadata["parsed_document_date"] = parsed_date
            except Exception:
                # If parsing fails, we'll just use the string version
                pass
            break
    
    # Try to detect GRS category based on content
    grs_categories = {
        "administrative": ["administrative", "operations", "management", "office", "general"],
        "budget_finance": ["budget", "finance", "financial", "accounting", "fiscal", "expenditure", "revenue"],
        "legal": ["legal", "contract", "agreement", "lawsuit", "litigation", "attorney", "counsel"],
        "personnel": ["personnel", "employee", "staff", "human resources", "hr", "recruitment", "hiring"],
        "policy": ["policy", "procedure", "guideline", "regulation", "standard", "rule"],
        "program_management": ["program", "project", "initiative", "implementation", "oversight"],
        "property_management": ["property", "asset", "inventory", "equipment", "facility", "building"],
        "public_relations": ["public", "media", "press", "communication", "outreach", "publicity"],
        "aging_services": ["aging", "senior", "elderly", "meal", "nutrition", "adult services"]
    }
    
    # Count occurrences of terms in each category
    category_scores = {category: 0 for category in grs_categories}
    for category, terms in grs_categories.items():
        for term in terms:
            term_count = document_text.lower().count(term)
            category_scores[category] += term_count
    
    # Get the category with the highest score
    if any(category_scores.values()):
        top_category = max(category_scores.items(), key=lambda x: x[1])
        if top_category[1] > 0:  # Only assign if we have at least one match
            metadata["detected_grs_category"] = top_category[0].replace("_", " ").title()
    
    # Try to detect document type
    document_types = {
        "minutes": "Meeting Minutes",
        "agenda": "Meeting Agenda",
        "report": "Report",
        "proposal": "Proposal",
        "budget": "Budget Document",
        "policy": "Policy Document",
        "memo": "Memorandum",
        "letter": "Letter",
        "contract": "Contract",
        "agreement": "Agreement",
        "plan": "Plan/Planning Document",
        "schedule": "Schedule",
        "form": "Form",
        "application": "Application",
        "correspondence": "Correspondence",
        "meal": "Meal Report",
        "food delivery": "Food Delivery Report",
        "senior center": "Senior Center Report"
    }
    
    for keyword, doc_type in document_types.items():
        if keyword.lower() in document_text.lower():
            metadata["detected_document_type"] = doc_type
            break
    
    return metadata

# Function to create enhanced prompt for the Bedrock agent
def create_enhanced_prompt(document_text, metadata):
    """
    Create a more detailed prompt for the Bedrock agent that includes
    extracted metadata and specific instructions for compliance evaluation
    based on Utah's General Records Schedule (GRS)
    """
    # Get current date for compliance checking
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Check if document was truncated
    truncation_note = ""
    if 'truncated' in metadata and metadata['truncated']:
        truncation_note = "\nNOTE: This document was truncated for processing. Analysis is based on the first portion of the document only."
    
    prompt = f"""I need you to evaluate this document for compliance with Utah's General Records Schedule (GRS) retention policies.
Please analyze the document carefully and provide the following information in a structured format:

1. Document Type: [Identify the specific document type, such as Meeting Minutes, Financial Report, Policy Document, etc.]
2. GRS Category: [Identify the appropriate Utah GRS category this document belongs to, such as Administrative Records, Budget/Finance, Legal, Personnel, etc.]
3. GRS Item Number: [Provide the specific GRS item number that applies to this document]
4. Document Date: [Extract the date of the document if available]
5. Compliance Status: [Determine if the document is "Compliant", "Non-Compliant", or "Needs Review"]
6. Retention Period: [Specify the retention period for this type of document according to Utah GRS]
7. Recommendations: [Provide specific recommendations for handling this document]

IMPORTANT COMPLIANCE VERIFICATION INSTRUCTIONS:
- Today's date is {current_date}
- If the document's retention period has expired based on its date, mark it as "Non-Compliant"
- If the document is still within its retention period, mark it as "Compliant"
- If you cannot determine the document date or exact retention period, mark it as "Needs Review"
- Be precise about the retention period as specified in the GRS item
- Double-check your compliance determination by comparing the document date + retention period against today's date
{truncation_note}

Additional metadata detected:
- Word count: {metadata['word_count']}
- Contains financial terms: {'Yes' if metadata['contains_financial_data'] else 'No'}
- Contains meeting terms: {'Yes' if metadata['contains_meeting_terms'] else 'No'}
- Contains report terms: {'Yes' if metadata['contains_report_terms'] else 'No'}
- Contains policy terms: {'Yes' if metadata['contains_policy_terms'] else 'No'}
- Contains legal terms: {'Yes' if metadata['contains_legal_terms'] else 'No'}
- Contains administrative terms: {'Yes' if metadata['contains_administrative_terms'] else 'No'}
- Contains personnel terms: {'Yes' if metadata['contains_personnel_terms'] else 'No'}
- Detected date: {metadata['detected_date'] if metadata['detected_date'] else 'None'}
- Suggested GRS category: {metadata['detected_grs_category'] if metadata['detected_grs_category'] else 'Unknown'}
- Suggested document type: {metadata['detected_document_type'] if metadata['detected_document_type'] else 'Unknown'}

Document content:
{document_text}
"""
    return prompt

# Function to create a prompt for chat questions
def create_chat_prompt(user_question, document_text=None, evaluation_results=None):
    """
    Create a prompt for chat questions that emphasizes accuracy and
    encourages asking for clarification when needed
    """
    prompt = f"""You are an assistant specializing in Utah's General Records Schedule (GRS) retention policies.

IMPORTANT INSTRUCTIONS:
1. Provide information from Utah's GRS knowledge base that directly answers the user's question.
2. If the question is about a specific document type or retention period, identify the EXACT GRS item number that applies.
3. Only ask for clarification if the question is genuinely ambiguous and could refer to multiple different GRS items.
4. When you know the relevant GRS item, provide it immediately rather than asking unnecessary follow-up questions.
5. Always include the GRS item number, retention period, and a brief description of the record type.
6. If you're not certain about a specific detail, acknowledge that uncertainty rather than making up information.

User question: {user_question}
"""

    # Add context from document if available
    if document_text:
        prompt += f"\n\nContext from current document (first 500 chars):\n{document_text[:500]}..."
    
    # Add context from evaluation if available
    if evaluation_results:
        prompt += "\n\nPrevious evaluation results:"
        if evaluation_results.get("document_type"):
            prompt += f"\n- Document Type: {evaluation_results['document_type']}"
        if evaluation_results.get("grs_category"):
            prompt += f"\n- GRS Category: {evaluation_results['grs_category']}"
        if evaluation_results.get("grs_item_number"):
            prompt += f"\n- GRS Item Number: {evaluation_results['grs_item_number']}"
        if evaluation_results.get("retention_period"):
            prompt += f"\n- Retention Period: {evaluation_results['retention_period']}"
    
    return prompt

# Improved parsing function for the agent's response
def parse_compliance_response(response_text):
    """
    More robust parsing of the agent's response to extract structured data
    even with variations in formatting
    """
    results = {
        "raw_response": response_text,
        "document_type": None,
        "grs_category": None,
        "grs_item_number": None,
        "document_date": None,
        "evaluation": None,
        "retention_period": None,
        "recommended_action": None
    }
    
    # Try different parsing approaches
    
    # Approach 1: Look for specific labels with colons
    labels = {
        "Document Type:": "document_type",
        "GRS Category:": "grs_category", 
        "GRS Item Number:": "grs_item_number",
        "Document Date:": "document_date",
        "Compliance Status:": "evaluation",
        "Retention Period:": "retention_period",
        "Recommendations:": "recommended_action"
    }
    
    for line in response_text.strip().split('\n'):
        for label, key in labels.items():
            if label in line:
                results[key] = line.split(label)[1].strip()
    
    # Approach 2: Try to find sections with markdown headers
    import re
    headers = {
        r"#+\s*Document Type\s*:?\s*(.+)": "document_type",
        r"#+\s*GRS Category\s*:?\s*(.+)": "grs_category",
        r"#+\s*GRS Item Number\s*:?\s*(.+)": "grs_item_number",
        r"#+\s*Document Date\s*:?\s*(.+)": "document_date",
        r"#+\s*Compliance Status\s*:?\s*(.+)": "evaluation",
        r"#+\s*Retention Period\s*:?\s*(.+)": "retention_period",
        r"#+\s*Recommendations\s*:?\s*(.+)": "recommended_action"
    }
    
    for pattern, key in headers.items():
        match = re.search(pattern, response_text)
        if match and not results[key]:
            results[key] = match.group(1).strip()
    
    # Approach 3: Look for key terms in the response if still missing
    if not results["evaluation"]:
        if "compliant" in response_text.lower():
            if "non-compliant" in response_text.lower() or "not compliant" in response_text.lower():
                results["evaluation"] = "Non-Compliant"
            else:
                results["evaluation"] = "Compliant"
        elif "review" in response_text.lower():
            results["evaluation"] = "Needs Review"
    
    # Look for GRS item number patterns if not found by the above methods
    if not results["grs_item_number"]:
        # Look for patterns like "GRS-1-2", "GRS 1-2", "Item 1-2", etc.
        grs_patterns = [
            r"GRS[- ](\d+[-]\d+)",
            r"GRS[- ](\d+)",
            r"GRS Item[: ]+(\d+[-]\d+)",
            r"GRS Item[: ]+(\d+)",
            r"Item[: ]+(\d+[-]\d+)",
            r"Item[: ]+(\d+)",
            r"Item Number[: ]+(\d+[-]\d+)",
            r"Item Number[: ]+(\d+)"
        ]
        
        for pattern in grs_patterns:
            match = re.search(pattern, response_text)
            if match:
                results["grs_item_number"] = match.group(1)
                break
    
    # Try to extract recommendations if not found by the above methods
    if not results["recommended_action"]:
        # Look for recommendations section
        recommendation_patterns = [
            r"Recommendations?:(.*?)(?:\n\n|\n[A-Z]|$)",
            r"Recommendations?[^:]*\n(.*?)(?:\n\n|\n[A-Z]|$)",
            r"recommend[^:]*:(.*?)(?:\n\n|\n[A-Z]|$)"
        ]
        
        for pattern in recommendation_patterns:
            match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            if match:
                # Clean up the extracted text
                rec_text = match.group(1).strip()
                if rec_text:
                    results["recommended_action"] = rec_text
                    break
        
        # If still not found, look for sentences containing recommendation keywords
        if not results["recommended_action"]:
            recommendation_keywords = ["recommend", "should", "must", "need to", "advised to"]
            sentences = re.split(r'(?<=[.!?])\s+', response_text)
            
            rec_sentences = []
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in recommendation_keywords):
                    rec_sentences.append(sentence.strip())
            
            if rec_sentences:
                results["recommended_action"] = " ".join(rec_sentences)
    
    # Set default values for missing fields
    if not results["evaluation"]:
        results["evaluation"] = "Needs Review"
    
    if not results["recommended_action"]:
        if results["evaluation"] == "Compliant":
            results["recommended_action"] = "Document is compliant with retention policies. Continue to maintain according to GRS requirements."
        elif results["evaluation"] == "Non-Compliant":
            results["recommended_action"] = "Document has exceeded its retention period. Consider proper disposal according to GRS guidelines."
        else:
            results["recommended_action"] = "Further review needed to determine compliance status."
    
    # Check for Department field as fallback for GRS Category (for backward compatibility)
    if not results["grs_category"] and "Department:" in response_text:
        for line in response_text.strip().split('\n'):
            if "Department:" in line:
                results["grs_category"] = line.split("Department:")[1].strip()
    
    # Verify compliance status based on document date and retention period
    from datetime import datetime
    current_date = datetime.now()
    
    # Try to parse the document date
    doc_date = None
    if results["document_date"]:
        try:
            # Try different date formats
            date_formats = [
                "%Y-%m-%d",           # 2025-01-01
                "%m/%d/%Y",           # 1/1/2025
                "%B %d, %Y",          # January 1, 2025
                "%b %d, %Y",          # Jan 1, 2025
                "%d %B %Y",           # 1 January 2025
                "%d %b %Y"            # 1 Jan 2025
            ]
            
            for fmt in date_formats:
                try:
                    doc_date = datetime.strptime(results["document_date"], fmt)
                    break
                except ValueError:
                    continue
        except Exception:
            # If parsing fails, we'll rely on the agent's determination
            pass
    
    # Try to interpret retention period
    if doc_date and results["retention_period"]:
        retention_text = results["retention_period"].lower()
        
        # Check for specific retention periods
        if "until completion" in retention_text or "until superseded" in retention_text:
            # These are special cases that need human review
            results["evaluation"] = "Needs Review"
            results["retention_notes"] = "Special retention condition requires human verification"
        else:
            # Look for year patterns in retention period
            year_patterns = [
                r"(\d+)\s*years?",
                r"(\d+)\s*yr",
                r"for\s*(\d+)\s*years?"
            ]
            
            retention_years = None
            for pattern in year_patterns:
                match = re.search(pattern, retention_text)
                if match:
                    try:
                        retention_years = int(match.group(1))
                        break
                    except ValueError:
                        pass
            
            if retention_years:
                # Calculate expiration date
                import datetime as dt
                expiration_date = doc_date + dt.timedelta(days=retention_years*365)
                
                # Compare with current date
                if current_date > expiration_date:
                    # Document retention period has expired
                    results["evaluation"] = "Non-Compliant"
                    results["retention_notes"] = f"Retention period of {retention_years} years expired on {expiration_date.strftime('%Y-%m-%d')}"
                else:
                    # Document is still within retention period
                    results["evaluation"] = "Compliant"
                    results["retention_notes"] = f"Retention period of {retention_years} years expires on {expiration_date.strftime('%Y-%m-%d')}"
    
    return results
# Set page configuration
st.set_page_config(
    page_title="Government Document Compliance Evaluator",
    page_icon="📑",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #f5f5f5;
    }
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .compliance-tag {
        background-color: #e6f3ff;
        border-radius: 4px;
        padding: 2px 8px;
        margin-right: 5px;
        font-size: 0.9em;
    }
    .compliant {
        background-color: #d4edda;
        color: #155724;
        padding: 5px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .review {
        background-color: #fff3cd;
        color: #856404;
        padding: 5px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .non-compliant {
        background-color: #f8d7da;
        color: #721c24;
        padding: 5px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .grs-item {
        background-color: #e6f3ff;
        color: #0c5460;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
        margin-left: 5px;
    }
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .header-text {
        flex-grow: 1;
    }
    .logo {
        width: 80px;
        margin-right: 20px;
    }
    .file-info {
        background-color: #e9ecef;
        padding: 10px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-container">
    <div class="header-text">
        <h1>Utah Government Document Compliance Evaluator</h1>
        <p>Upload government documents to evaluate compliance with Utah General Records Schedule (GRS) retention policies</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Initialize session state for chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'document_text' not in st.session_state:
    st.session_state.document_text = ""

if 'evaluation_results' not in st.session_state:
    st.session_state.evaluation_results = None

if 'file_info' not in st.session_state:
    st.session_state.file_info = None

# Sidebar
with st.sidebar:
    st.header("Options")
    
    # Reset buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Chat"):
            clear_chat_history()
    with col2:
        if st.button("Reset All"):
            reset_document()
            st.rerun()
    
    # Document upload
    uploaded_file = st.file_uploader("Upload Document", type=["txt", "pdf", "docx"])
    
    if uploaded_file is not None:
        # Reset evaluation results when uploading a new file
        st.session_state.evaluation_results = None
        
        # Handle different file types
        if uploaded_file.type == "application/pdf":
            # Extract text from PDF with size limiting
            pdf_bytes = uploaded_file.getvalue()
            pdf_file = io.BytesIO(pdf_bytes)
            
            # Set limits for document processing
            max_pages = 10  # Process only first 10 pages
            max_chars = 50000  # Limit to 50,000 characters
            
            st.session_state.document_text, doc_metadata = extract_text_from_pdf(pdf_file, max_pages, max_chars)
            
            # Store file info with metadata about truncation
            st.session_state.file_info = {
                "name": uploaded_file.name,
                "type": "PDF",
                "size": f"{len(pdf_bytes)/1024:.1f} KB",
                "metadata": doc_metadata
            }
            
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Extract text from DOCX with size limiting
            docx_bytes = uploaded_file.getvalue()
            docx_file = io.BytesIO(docx_bytes)
            
            # Set limit for document processing
            max_chars = 50000  # Limit to 50,000 characters
            
            st.session_state.document_text, doc_metadata = extract_text_from_docx(docx_file, max_chars)
            
            # Store file info with metadata about truncation
            st.session_state.file_info = {
                "name": uploaded_file.name,
                "type": "DOCX",
                "size": f"{len(docx_bytes)/1024:.1f} KB",
                "metadata": doc_metadata
            }
            
        else:
            # For text files with size limiting
            text_content = uploaded_file.getvalue().decode("utf-8")
            
            # Limit text content size
            max_chars = 50000
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars]
                doc_metadata = {
                    "truncated": True,
                    "truncation_reason": "character_limit",
                    "total_chars": len(text_content),
                    "processed_chars": max_chars
                }
            else:
                doc_metadata = {
                    "truncated": False,
                    "total_chars": len(text_content),
                    "processed_chars": len(text_content)
                }
                
            st.session_state.document_text = text_content
            
            # Store file info with metadata about truncation
            st.session_state.file_info = {
                "name": uploaded_file.name,
                "type": "Text",
                "size": f"{len(text_content.encode('utf-8'))/1024:.1f} KB",
                "metadata": doc_metadata
            }
    
    # Sample document selection
    st.subheader("Or use a sample document")
    sample_option = st.selectbox(
        "Select sample document",
        ["None", "Monthly Report", "Budget Proposal", "Meeting Minutes"]
    )
    
    if sample_option == "None":
        # Do nothing
        pass
    elif sample_option == "Monthly Report":
        # Reset evaluation results when changing sample documents
        st.session_state.evaluation_results = None
        st.session_state.document_text = """
MONTHLY REPORT: AGING SERVICES DIVISION
Date: April 15, 2025
Department: Health and Human Services
Division: Aging Services
Author: Jane Smith, Division Director

EXECUTIVE SUMMARY:
This monthly report provides an overview of the Aging Services Division's activities, 
accomplishments, and challenges for April 2025. The division continues to provide essential 
services to Utah's aging population while implementing new initiatives to improve service delivery.

KEY METRICS:
- Clients served: 1,245 (up 3% from previous month)
- Home visits conducted: 532
- Meals delivered: 8,750
- Transportation services provided: 423 trips
- Wellness checks completed: 875

PROGRAM UPDATES:
1. The new online application portal for senior services launched on April 5, 2025, with 127 applications received through the system.
2. Staff training on the updated case management system was completed for all regional offices.
3. The division's annual satisfaction survey was distributed to 2,000 clients with a current response rate of 45%.

BUDGET SUMMARY:
- Monthly allocation: $425,000
- Expenditures: $412,750
- Remaining balance: $12,250

UPCOMING INITIATIVES:
- May 10: Senior Health Fair at Salt Lake Convention Center
- May 15: Launch of expanded transportation services in rural counties
- May 22: Quarterly meeting with county aging services coordinators

CHALLENGES AND SOLUTIONS:
The division continues to face staffing shortages in the northern region. We have implemented a 
recruitment campaign targeting social work graduates from state universities and expect to fill 
four vacant positions by the end of May.

CONCLUSION:
The Aging Services Division remains on track to meet its annual performance goals. The new 
online portal has improved accessibility for clients and reduced processing time for applications.
"""
        # Set file info for sample
        st.session_state.file_info = {
            "name": "monthly_report_sample.txt",
            "type": "Sample",
            "size": "2.1 KB"
        }
        
    elif sample_option == "Budget Proposal":
        # Reset evaluation results when changing sample documents
        st.session_state.evaluation_results = None
        st.session_state.document_text = """
BUDGET PROPOSAL: FISCAL YEAR 2026
Department: Transportation
Division: Highway Maintenance
Date: April 28, 2025

OVERVIEW:
This budget proposal outlines the projected expenses and resource allocations for the Highway Maintenance Division for the fiscal year 2026. The proposal reflects an increase of 3.5% from the previous fiscal year to account for inflation and expanded maintenance needs.

BUDGET SUMMARY:
Total Requested Budget: $24,750,000

BUDGET BREAKDOWN:
1. Personnel Costs: $12,500,000
   - Salaries: $10,200,000
   - Benefits: $2,300,000

2. Equipment and Materials: $7,850,000
   - Road Salt and De-icing Materials: $2,100,000
   - Asphalt and Concrete: $3,250,000
   - Equipment Replacement: $1,500,000
   - Tools and Supplies: $1,000,000

3. Contracted Services: $3,400,000
   - Snow Removal Contracts: $1,800,000
   - Specialized Repairs: $1,600,000

4. Administrative Costs: $1,000,000
   - Training and Certification: $350,000
   - Software and Technology: $450,000
   - Office Expenses: $200,000

JUSTIFICATION:
The requested budget increase is necessary to address the following:
1. Rising costs of materials (7% increase in asphalt prices)
2. Addition of 45 lane-miles to maintenance responsibility
3. Replacement of 5 snowplows that have exceeded their service life
4. Implementation of new road maintenance tracking software

PERFORMANCE METRICS:
1. Response time to road hazards: Target of <45 minutes
2. Pothole repair completion: Target of <72 hours from report
3. Winter storm road clearance: Target of 95% of priority routes within 4 hours

CONCLUSION:
This budget proposal represents the minimum funding required to maintain Utah's highways at the safety and quality standards expected by the public and mandated by state regulations.

Submitted by:
Robert Johnson
Director, Highway Maintenance Division
"""
        # Set file info for sample
        st.session_state.file_info = {
            "name": "budget_proposal_sample.txt",
            "type": "Sample",
            "size": "2.3 KB"
        }
        
    elif sample_option == "Meeting Minutes":
        # Reset evaluation results when changing sample documents
        st.session_state.evaluation_results = None
        st.session_state.document_text = """
MEETING MINUTES
Utah Department of Environmental Quality
Water Quality Board
Date: April 25, 2025
Time: 10:00 AM - 12:30 PM
Location: DEQ Main Conference Room, Salt Lake City

ATTENDEES:
- Sarah Williams, Board Chair
- Michael Chen, Vice Chair
- Dr. Elizabeth Taylor, Board Member
- James Rodriguez, Board Member
- Patricia Nelson, Board Member
- Thomas Wright, Director of Water Quality Division
- Jennifer Lopez, Secretary

ABSENT:
- Robert Anderson, Board Member (excused)

AGENDA ITEMS:

1. CALL TO ORDER AND APPROVAL OF PREVIOUS MINUTES
Chair Williams called the meeting to order at 10:05 AM.
The minutes from the March 28, 2025 meeting were reviewed and approved unanimously.

2. PUBLIC COMMENTS
Three members of the public provided comments regarding the proposed changes to wastewater treatment regulations:
- John Davis, Sierra Club Utah Chapter
- Maria Gonzalez, Utah Association of Industries
- Professor Alan Smith, University of Utah Environmental Engineering Department

3. DIRECTOR'S REPORT
Director Wright presented the quarterly water quality monitoring results for Q1 2025:
- 94% of monitored water bodies met quality standards (up 2% from Q4 2024)
- 12 violation notices issued to industrial facilities
- 3 enforcement actions initiated

4. NEW BUSINESS
a) Proposed Amendments to Regulation R317-3
The board reviewed the proposed amendments to Wastewater Treatment and Disposal Systems regulation.
After discussion, the board voted 4-1 to approve the amendments with modifications to Section 3.4.
Member Nelson voted against, citing concerns about implementation timelines.

b) Grant Approvals
The board unanimously approved $1.2 million in grants for five community water quality improvement projects.

5. OLD BUSINESS
a) Update on Jordan River Restoration Project
Director Wright provided an update on the project timeline and budget. The project is currently 15% under budget and on schedule for completion in October 2025.

b) Compliance Report on 2024 Enforcement Actions
The board reviewed the annual compliance report. Discussion focused on repeat violators and potential changes to penalty structures.

6. COMMITTEE REPORTS
a) Technical Advisory Committee
Dr. Taylor reported on the committee's review of new testing methodologies for PFAS compounds.

b) Public Outreach Committee
Member Rodriguez presented the draft 2026 public education campaign materials for board feedback.

7. NEXT MEETING
The next meeting is scheduled for May 30, 2025, at 10:00 AM.

8. ADJOURNMENT
The meeting was adjourned at 12:25 PM.

Minutes prepared by Jennifer Lopez, Board Secretary
Approved by: [Pending approval at next meeting]
"""
        # Set file info for sample
        st.session_state.file_info = {
            "name": "meeting_minutes_sample.txt",
            "type": "Sample",
            "size": "2.5 KB"
        }

# Main content area
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Document Content")
    
    # Display file info if available
    if st.session_state.file_info:
        file_info = st.session_state.file_info
        file_info_html = f"""
        <div class="file-info">
            <strong>File:</strong> {file_info['name']} ({file_info['type']}, {file_info['size']})
        """
        
        # Add truncation warning if document was truncated
        if 'metadata' in file_info and file_info['metadata'].get('truncated', False):
            file_info_html += """
            <div style="margin-top: 5px; color: #856404; background-color: #fff3cd; padding: 5px; border-radius: 4px;">
                <strong>Note:</strong> Document was truncated for processing.
            """
            
            if file_info['type'] == 'PDF':
                file_info_html += f" Showing {file_info['metadata'].get('processed_pages', 0)} of {file_info['metadata'].get('total_pages', 0)} pages."
            elif file_info['type'] == 'DOCX':
                file_info_html += f" Showing {file_info['metadata'].get('processed_paragraphs', 0)} of {file_info['metadata'].get('total_paragraphs', 0)} paragraphs."
            
            file_info_html += "</div>"
        
        file_info_html += "</div>"
        st.markdown(file_info_html, unsafe_allow_html=True)
    
    # Text area for document content
    document_text = st.text_area(
        "Enter or edit document text",
        value=st.session_state.document_text,
        height=400
    )
    
    # Update session state
    st.session_state.document_text = document_text
    
    # Evaluate button
    if st.button("Evaluate Document"):
        if st.session_state.document_text:
            # Reset previous evaluation results when evaluating a new document
            st.session_state.evaluation_results = None
            
            with st.spinner("Evaluating document for compliance..."):
                try:
                    # First analyze the document to extract metadata
                    document_metadata = analyze_document_content(st.session_state.document_text)
                    
                    # Create an enhanced prompt with the metadata
                    enhanced_prompt = create_enhanced_prompt(st.session_state.document_text, document_metadata)
                    
                    # Call the Bedrock agent with the enhanced prompt
                    response = client.invoke_agent(
                        agentId=agent_id,
                        agentAliasId=agent_alias_id,
                        # Generate a unique session ID for each evaluation to prevent context bleed
                        sessionId=f"eval-{int(time.time())}",
                        inputText=enhanced_prompt
                    )
                    
                    # Process the streaming response
                    event_stream = response['completion']
                    full_response = ""
                    
                    # Process each event in the stream
                    for event in event_stream:
                        if 'chunk' in event:
                            chunk = event['chunk']
                            if 'bytes' in chunk:
                                # Decode the bytes to get the text
                                text = chunk['bytes'].decode('utf-8')
                                full_response += text
                    
                    # Use the improved parsing function
                    st.session_state.evaluation_results = parse_compliance_response(full_response)
                    
                    # Add document metadata to the results
                    st.session_state.evaluation_results["metadata"] = document_metadata
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": f"Please evaluate this document for compliance."
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": full_response
                    })
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.warning("Please enter or upload a document first.")

with col2:
    st.subheader("Compliance Evaluation")
    
    if st.session_state.evaluation_results:
        results = st.session_state.evaluation_results
        
        # Display evaluation status with appropriate styling
        if "evaluation" in results:
            status_class = ""
            if results["evaluation"] == "Compliant":
                status_class = "compliant"
            elif "Review" in results["evaluation"]:
                status_class = "review"
            else:
                status_class = "non-compliant"
            
            st.markdown(f"<div class='{status_class}'>{results['evaluation']}</div>", unsafe_allow_html=True)
        
        # Display document type with confidence indicator
        if "document_type" in results:
            st.markdown("### Document Type")
            st.markdown(results["document_type"])
        
        # Display GRS category and item number if available
        if "grs_category" in results and results["grs_category"]:
            st.markdown("### GRS Category")
            grs_text = results["grs_category"]
            if "grs_item_number" in results and results["grs_item_number"]:
                grs_text += f" (Item {results['grs_item_number']})"
            st.markdown(grs_text)
            
            # Show metadata that helped with classification
            with st.expander("Document Classification Details"):
                if "metadata" in results:
                    metadata = results["metadata"]
                    st.markdown("**Document Analysis:**")
                    st.markdown(f"- Word count: {metadata['word_count']}")
                    st.markdown(f"- Contains financial terms: {'Yes' if metadata['contains_financial_data'] else 'No'}")
                    st.markdown(f"- Contains meeting terms: {'Yes' if metadata['contains_meeting_terms'] else 'No'}")
                    st.markdown(f"- Contains report terms: {'Yes' if metadata['contains_report_terms'] else 'No'}")
                    st.markdown(f"- Contains policy terms: {'Yes' if metadata['contains_policy_terms'] else 'No'}")
                    st.markdown(f"- Contains legal terms: {'Yes' if metadata['contains_legal_terms'] else 'No'}")
                    st.markdown(f"- Contains administrative terms: {'Yes' if metadata['contains_administrative_terms'] else 'No'}")
                    st.markdown(f"- Contains personnel terms: {'Yes' if metadata['contains_personnel_terms'] else 'No'}")
                    if metadata['detected_grs_category']:
                        st.markdown(f"- AI suggested GRS category: {metadata['detected_grs_category']}")
                    if metadata['detected_document_type']:
                        st.markdown(f"- AI suggested document type: {metadata['detected_document_type']}")
        # Display GRS item number separately if not shown with category
        elif "grs_item_number" in results and results["grs_item_number"]:
            st.markdown("### GRS Item Number")
            st.markdown(results["grs_item_number"])
        
        # Display document date if available
        if "document_date" in results and results["document_date"]:
            st.markdown("### Document Date")
            st.markdown(results["document_date"])
        
        # Display retention period
        if "retention_period" in results:
            st.markdown("### Retention Period")
            st.markdown(results["retention_period"])
            
            # Display retention notes if available
            if "retention_notes" in results and results["retention_notes"]:
                if results["evaluation"] == "Compliant":
                    st.success(results["retention_notes"])
                elif results["evaluation"] == "Non-Compliant":
                    st.error(results["retention_notes"])
                else:
                    st.warning(results["retention_notes"])
        
        # Display recommended action
        if "recommended_action" in results:
            st.markdown("### Recommendations")
            st.info(results["recommended_action"])
        
        # Raw response (collapsible)
        with st.expander("View Raw Response"):
            st.text(results.get("raw_response", "No raw response available"))
    else:
        st.info("No evaluation results yet. Click 'Evaluate Document' to analyze the document.")

# Chat interface
st.subheader("Chat with Compliance Agent")
st.markdown("Ask questions about the document or compliance rules")

# Display chat history
for message in st.session_state.chat_history:
    if message["role"] == "user":
        st.markdown(f"**You:** {message['content']}")
    else:
        st.markdown(f"**Agent:** {message['content']}")

# Initialize the chat input key in session state if it doesn't exist
if "chat_input_key" not in st.session_state:
    st.session_state.chat_input_key = 0

# Function to handle sending a message
def send_message():
    if st.session_state.current_chat_input:
        user_message = st.session_state.current_chat_input
        
        # Add user message to chat history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Call the agent
        try:
            with st.spinner("Getting response..."):
                # Create a specialized prompt for chat questions
                chat_prompt = create_chat_prompt(
                    user_message, 
                    document_text=st.session_state.document_text if st.session_state.document_text else None,
                    evaluation_results=st.session_state.evaluation_results if 'evaluation_results' in st.session_state and st.session_state.evaluation_results else None
                )
                
                # Call the Bedrock agent
                response = client.invoke_agent(
                    agentId=agent_id,
                    agentAliasId=agent_alias_id,
                    # Generate a unique session ID for each chat to prevent context bleed
                    sessionId=f"chat-{int(time.time())}",
                    inputText=chat_prompt
                )
                
                # Process the streaming response
                event_stream = response['completion']
                full_response = ""
                
                # Process each event in the stream
                for event in event_stream:
                    if 'chunk' in event:
                        chunk = event['chunk']
                        if 'bytes' in chunk:
                            # Decode the bytes to get the text
                            text = chunk['bytes'].decode('utf-8')
                            full_response += text
                
                # Add assistant response to chat history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": full_response
                })
                
                # Increment the key to force a new input widget
                st.session_state.chat_input_key += 1
                
                # Force a rerun to display the new messages
                st.rerun()
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Chat input with Enter key functionality
chat_input = st.text_input(
    "Type your question here",
    key=f"chat_input_{st.session_state.chat_input_key}",
    on_change=send_message,
    args=(),
    kwargs={},
    placeholder="Press Enter to send"
)

# Store the current input value in session state
st.session_state.current_chat_input = chat_input

# Add a send button as an alternative to pressing Enter
if st.button("Send"):
    send_message()

# Footer
st.markdown("---")
st.markdown("© 2025 Utah Government Document Compliance Evaluator | Powered by AWS Bedrock")
