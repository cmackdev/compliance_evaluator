# Government Document Compliance Evaluator

A comprehensive application for evaluating document compliance with General Records Schedule (GRS) retention policies using AWS Bedrock and generative AI.

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Enhanced Knowledge Base Format](#enhanced-knowledge-base-format)
- [Large Document Handling](#large-document-handling)
- [Architecture](#architecture)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Government Document Compliance Evaluator is an AI-powered application that helps government agencies evaluate documents for compliance with General Records Schedule (GRS) retention policies. The application analyzes document content, determines the appropriate GRS category and item number, and provides compliance recommendations based on document date and retention period requirements.

## Technology Stack

### Core Technologies
- **Python 3.9+**: Primary programming language
- **AWS Bedrock**: Foundation model service for generative AI capabilities
- **Streamlit**: Web application framework for the user interface
- **Boto3**: AWS SDK for Python to interact with AWS services

### Document Processing
- **PyPDF2**: PDF parsing and text extraction
- **python-docx**: DOCX parsing and text extraction

### Data Storage and Processing
- **Pandas**: Data manipulation and analysis
- **JSON/JSONL**: Enhanced knowledge base format

### AWS Services
- **AWS Bedrock Agent Runtime**: Powers the compliance agent with generative AI capabilities
- **Amazon SageMaker**: Hosts the application (optional deployment target)
- **AWS IAM**: Manages access permissions to AWS resources

## Features

### Document Analysis
- Upload and process PDF, DOCX, and TXT files
- Automatic document type detection
- Extraction of key metadata (dates, document type, etc.)
- Content analysis for better classification

### Compliance Evaluation
- Identification of applicable GRS item number
- Determination of retention period requirements
- Compliance status assessment (Compliant, Non-Compliant, Needs Review)
- Detailed recommendations for document handling

### User Interface
- Clean, intuitive web interface
- Document preview and editing capabilities
- Chat interface for asking questions about compliance rules
- Visual indicators for compliance status
- Sample documents for demonstration purposes

### Knowledge Base
- Enhanced JSONL format for better document classification
- Structured metadata for improved semantic matching
- Related items linking for comprehensive compliance understanding
- Document type and keyword extraction for better matching

### Large Document Handling
- Automatic truncation of large documents
- PDF processing limited to first 10 pages
- Character limit of 50,000 for all document types
- Clear indication when documents are truncated

## Installation

### Prerequisites
- Python 3.9 or higher
- AWS account with Bedrock access
- AWS CLI configured with appropriate credentials

### Setup

1. Clone the repository:
```bash
git clone https://github.com/cmackdev/compliance_evaluator.git
cd compliance-evaluator
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure AWS credentials:
```bash
aws configure
```

## Configuration

### AWS Bedrock Setup

1. Create an AWS Bedrock agent:
   - Navigate to the AWS Bedrock console
   - Create a new agent with appropriate knowledge base
   - Note the agent ID and agent alias ID

2. Update the agent configuration in `compliance-agent.py`:
```python
# Agent alias ARN
agent_id = "YOUR_AGENT_ID"  # Supervisor agent
agent_alias_id = "YOUR_AGENT_ALIAS_ID"  # alias
```

3. Configure AWS region:
```python
client = boto3.client('bedrock-agent-runtime', region_name='YOUR_REGION')
```

### Knowledge Base Preparation

1. Prepare the GRS data in CSV format (ScheduleItems.csv)
2. Convert to enhanced JSONL format:
```bash
python convert_to_enhanced_jsonl.py
```

## Usage

### Running the Application

1. Start the Streamlit application:
```bash
streamlit run compliance-agent.py
```

2. Access the application in your web browser at `http://localhost:8501`

### Document Evaluation Process

1. **Upload Document**: Use the file uploader to submit a PDF, DOCX, or TXT file
2. **Review Content**: The document text will be displayed in the main area
3. **Evaluate**: Click the "Evaluate Document" button to analyze for compliance
4. **Review Results**: See the compliance status, GRS item, and recommendations
5. **Ask Questions**: Use the chat interface for additional compliance inquiries

### Sample Documents

The application includes sample documents for demonstration:
- Monthly Report
- Budget Proposal
- Meeting Minutes

Select any sample from the sidebar to see how the compliance evaluation works.

## Enhanced Knowledge Base Format

The application uses an enhanced knowledge base format for better document classification and compliance determination:

```json
{
  "grs_item_number": "949",
  "title": "Protest files",
  "description": "These are written protests by owners of property to be assessed in a special improvement district. The governing body hears protests and approves changes or cancels districts.",
  "retention_period": "Retain for 2 years after resolution of issue, and then destroy records.",
  "category": "Special Assessment",
  "status": "Current",
  "approved_date": "1989-03-01",
  "document_types": ["protest", "special assessment document", "file"],
  "keywords": ["improvement", "changes", "files", "governing", "assessed", "body", "protest", "cancels", "written", "hears", "districts", "special", "assessment", "district", "property", "owners", "protests", "approves"],
  "related_items": ["948", "950", "953"]
}
```

### Key Improvements

1. **Structured JSON Format**
   - Clear field names for direct access to information
   - Consistent structure for all GRS items

2. **Enhanced Metadata**
   - `grs_item_number`: Explicit field for the GRS item number
   - `document_types`: List of document types this GRS item applies to
   - `keywords`: Extracted meaningful terms for better semantic matching
   - `related_items`: Cross-references to related GRS items

3. **Benefits for AI Processing**
   - More accurate document classification
   - Better matching of user queries to relevant GRS items
   - Improved compliance determination
   - Reduced need for excessive prompt engineering

## Large Document Handling

The application automatically handles large documents by:

1. **PDF Processing Limits**
   - Processes only the first 10 pages of PDF documents
   - Extracts text up to 50,000 characters
   - Provides metadata about truncation

2. **DOCX Processing Limits**
   - Processes paragraphs up to 50,000 characters
   - Tracks paragraph count and truncation information

3. **Text File Limits**
   - Limits plain text files to 50,000 characters
   - Provides metadata about truncation

4. **User Interface Indicators**
   - Clear visual indicators when documents are truncated
   - Information about how many pages/paragraphs were processed
   - Transparency about document processing limitations

5. **Prompt Engineering**
   - Informs the AI agent when working with truncated documents
   - Focuses analysis on the most relevant portions of documents

This approach ensures that the compliance agent can efficiently process documents of any size while maintaining accuracy in classification and compliance determination.

## Architecture

### Component Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Web Interface  │────▶│  Document       │────▶│  AWS Bedrock    │
│  (Streamlit)    │     │  Processor      │     │  Agent Runtime  │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  User Input     │     │  Document       │     │  Knowledge      │
│  Handler        │     │  Analyzer       │     │  Base (JSONL)   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Data Flow

1. User uploads document through Streamlit interface
2. Document processor extracts and limits text content
3. Document analyzer extracts metadata and key information
4. Enhanced prompt is created with document content and metadata
5. AWS Bedrock agent processes the document and determines compliance
6. Results are parsed and displayed to the user
7. User can ask follow-up questions through the chat interface

## Development

### Project Structure

```
compliance-evaluator/
├── compliance-agent.py       # Main application file
├── convert_to_enhanced_jsonl.py  # Conversion script for original schedule items to enhanced version
├── requirements.txt          # Python dependencies
├── ScheduleItems.csv         # Original GRS data
├── enhanced_compliance_records.jsonl  # Enhanced knowledge base document for embedding and chunking
├── README.md                 # This documentation
```

### Development Workflow

1. **Local Development**:
   - Make changes to the application code
   - Test locally using `streamlit run compliance-agent.py`
   - Verify functionality with sample documents

2. **Knowledge Base Updates**:
   - Update the CSV data as needed
   - Run the conversion script to generate updated JSONL
   - Test with the updated knowledge base

3. **AWS Bedrock Agent Updates**:
   - Make changes to the agent configuration in AWS console
   - Update the agent IDs in the application code
   - Test the integration with the updated agent

## Deployment

### Streamlit Cloud Deployment

1. Push your code to a GitHub repository
2. Connect your repository to Streamlit Cloud
3. Configure the deployment settings
4. Deploy the application

### AWS SageMaker Deployment

1. Package the application as a SageMaker-compatible Docker image
2. Upload the image to Amazon ECR
3. Create a SageMaker endpoint configuration
4. Deploy the endpoint
5. Configure access permissions

### Environment Variables

For production deployments, use environment variables for sensitive configuration:

```python
import os

agent_id = os.environ.get("BEDROCK_AGENT_ID")
agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID")
region = os.environ.get("AWS_REGION", "us-west-2")
```

## Troubleshooting

### Common Issues

1. **AWS Authentication Errors**:
   - Verify AWS credentials are configured correctly
   - Check IAM permissions for Bedrock access
   - Ensure the region is set correctly

2. **Document Processing Errors**:
   - Check if the document is password-protected
   - Verify the document format is supported
   - Try with a smaller document if processing fails

3. **Agent Response Issues**:
   - Check the agent configuration in AWS Bedrock
   - Verify the knowledge base is properly formatted
   - Review the prompt engineering for potential improvements

### Logging

The application includes logging for troubleshooting:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example usage
logger.info("Processing document: %s", file_name)
logger.error("Error processing document: %s", str(e))
```

## Contributing

Contributions to the Document Compliance Evaluator are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Please ensure your code follows the project's style guidelines and includes appropriate tests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---


