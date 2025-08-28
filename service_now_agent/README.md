# ServiceNow Ticket Automation

An intelligent, agentic AI-powered system that automatically creates ServiceNow tickets from Gmail emails using FastAPI, LangChain, LangGraph, and Gemini 2.5 Flash.

## Features

### 🤖 Agentic AI Workflow
- **Multi-agent architecture** using LangGraph for orchestrated workflow
- **Privacy-focused**: Reads email subjects only, with minimal body preview fallback
- **Intelligent classification** using Gemini 2.5 Flash
- **Automatic categorization** and priority assignment
- **Dynamic user/group lookup** with fallback defaults

### 📧 Email Processing
- **IMAP integration** with Gmail
- **10-minute intervals** for checking new emails
- **Auto-reply detection** and filtering
- **Privacy-conscious** content extraction

### 🎯 ServiceNow Integration
- **REST API integration** for ticket creation
- **Dynamic user/group assignment** based on categories
- **Fallback configuration** for unknown users/categories
- **Ticket tracking** and status monitoring

### 📬 Notification System
- **Confirmation emails** upon ticket creation
- **Closure notifications** when tickets are resolved
- **Customizable email templates**

### 🚀 Production Ready
- **FastAPI backend** with background scheduling
- **Comprehensive logging** with rotation
- **Error handling** and retry mechanisms
- **Configuration management** via .env and YAML

## Architecture

```
┌─────────────────┐    ┌──────────────────┐              │
│     SMTP        │◄───┤  Notification    │              │
│    Server       │    │     Agent        │              │
└─────────────────┘    └──────────────────┘              │
                                │                        │
                                ▼                        │
                       ┌──────────────────┐              │
                       │    Tracker       │◄─────────────┘
                       │     Agent        │
                       └──────────────────┘
```

## Quick Start

### 1. Prerequisites

- Python 3.9+
- Gmail account with App Password enabled
- ServiceNow instance with API access
- Google Gemini API key

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd servicenow-ticket-automation

# Install dependencies
pip install -r requirements.txt

# Create configuration files
cp .env.sample .env
# Edit .env with your credentials
```

### 3. Configuration

#### Environment Variables (.env)
```bash
# Gmail Configuration
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password

# ServiceNow Configuration
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password

# Gemini AI Configuration
GEMINI_API_KEY=your-gemini-api-key

# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=support@yourcompany.com
```

#### YAML Configuration (config/config.yaml)
The YAML file contains fallback settings, category mappings, and email templates. Customize as needed for your organization.

### 4. Run the Application

```bash
# Development
python main.py

# Production with Gunicorn
gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

The application will:
- Start the FastAPI server on port 8000
- Begin checking emails every 10 minutes
- Process support-related emails automatically
- Create ServiceNow tickets and send notifications

## API Endpoints

### Health Check
```http
GET /
GET /health
```

### Manual Trigger (for testing)
```http
POST /trigger-manual
```

## Workflow Details

### 1. Scheduler Agent
- Triggers every 10 minutes
- Orchestrates the entire workflow using LangGraph
- Manages agent coordination and error handling

### 2. Mail Fetcher Agent
- Connects to Gmail via IMAP
- Fetches unread emails from the last 10 minutes
- Privacy-focused: reads subject only, minimal body preview if needed
- Filters out auto-replies and delivery reports

### 3. Classifier Agent (Gemini 2.5 Flash)
- Analyzes email content to determine if it's support-related
- Uses AI to distinguish between support requests and other emails
- Filters out promotional, social, and non-support content

### 4. Summary Agent (Gemini 2.5 Flash)
- Generates concise problem summaries
- Creates appropriate ticket titles and descriptions
- Suggests priority and urgency levels

### 5. Category Extractor Agent (Gemini 2.5 Flash)
- Categorizes issues (IT, HR, Finance, Facilities, General)
- Extracts subcategories for more specific routing
- Provides confidence levels and reasoning

### 6. ServiceNow Agent
- Creates incidents via REST API
- Performs dynamic user/group lookups
- Falls back to configured defaults when lookups fail
- Handles ticket assignments and routing

### 7. Notification Agent
- Sends confirmation emails upon ticket creation
- Uses customizable email templates
- Handles SMTP authentication and delivery

### 8. Tracker Agent
- Monitors ticket status changes
- Sends closure notifications when tickets are resolved
- Maintains tracking state for active tickets
- Performs periodic cleanup of old tracking data

## Configuration Options

### Category Mapping
Customize how email categories map to ServiceNow groups:

```yaml
category_to_group:
  IT: "IT Support Team"
  HR: "Human Resources"
  Finance: "Finance Team"
  Facilities: "Facilities Management"
  General: "General Support"
```

### Email Templates
Customize notification email templates:

```yaml
email_templates:
  ticket_created:
    subject: "Support Ticket Created - {ticket_number}"
    body: |
      Your ticket {ticket_number} has been created...
```

### Fallback Settings
Configure defaults when dynamic lookups fail:

```yaml
servicenow_fallbacks:
  default_caller:
    name: "Unknown Caller"
    email: "unknown@company.com"
  default_assignment_group:
    name: "General Support"
```

## Monitoring and Logging

### Log Files
- `logs/app.log` - Main application log
- `logs/error.log` - Errors and critical issues only  
- `logs/structured.log` - JSON structured logs for analysis

### Monitoring Endpoints
```http
GET /health          # Application health status
GET /              # Basic status check
```

### Log Levels
- `DEBUG` - Detailed debugging information
- `INFO` - General operational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical system errors

## Security Considerations

### Privacy
- **Subject-only processing**: Email bodies are only read if subjects are too vague
- **Minimal data retention**: No permanent storage of email content
- **Secure credential handling**: All secrets in environment variables

### Authentication
- **App Passwords**: Uses Gmail App Passwords, not regular passwords
- **ServiceNow API**: Basic authentication with dedicated service account
- **API Keys**: Secure storage of Gemini API credentials

### Data Protection
- **No persistent storage**: All processing happens in memory
- **Automatic cleanup**: Old tracking data is automatically purged
- **Sanitized logging**: Sensitive data is not logged

## Troubleshooting

### Common Issues

#### Gmail Connection Issues
```bash
# Check Gmail credentials
# Ensure App Password is enabled
# Verify IMAP is enabled in Gmail settings
```

#### ServiceNow API Issues
```bash
# Verify instance URL format
# Check user permissions for incident creation
# Test API connectivity
```

#### Gemini API Issues
```bash
# Verify API key is valid
# Check quota limits
# Monitor API responses
```

### Debug Mode
```bash
# Run with debug logging
LOG_LEVEL=DEBUG python main.py
```

### Manual Testing
```bash
# Trigger workflow manually
curl -X POST http://localhost:8000/trigger-manual
```

## Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "main:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### Systemd Service
```ini
[Unit]
Description=ServiceNow Ticket Automation
After=network.target

[Service]
Type=simple
User=servicenow-automation
WorkingDirectory=/opt/servicenow-automation
ExecStart=/opt/servicenow-automation/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Environment-Specific Configuration
- **Development**: Direct Python execution
- **Staging**: Docker with external configuration
- **Production**: Kubernetes or systemd service

## Performance and Scaling

### Current Limitations
- **Single instance**: Designed for single-instance deployment
- **Memory-based tracking**: Ticket tracking is not persistent
- **10-minute intervals**: Fixed processing interval

### Optimization Tips
- **Adjust check intervals** based on email volume
- **Configure log rotation** to manage disk space  
- **Monitor Gemini API quotas** and implement backoff
- **Use database** for persistent tracking in high-volume scenarios

## Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Code formatting
black .
flake8 .
```

### Code Structure
```
app/
├── main.py                 # FastAPI application entry point
├── agents/                 # All agent implementations
│   ├── scheduler.py        # Main workflow orchestrator
│   ├── mail_fetcher.py     # Gmail IMAP integration
│   ├── classifier.py       # AI email classification
│   ├── summary.py          # AI summary generation
│   ├── category_extractor.py # AI category extraction
│   ├── servicenow.py       # ServiceNow API integration
│   ├── notification.py     # Email notifications
│   └── tracker.py          # Ticket status tracking
├── tools/                  # Utility modules
│   ├── email_utils.py      # Email processing utilities
│   ├── servicenow_api.py   # ServiceNow REST API client
│   └── config_loader.py    # Configuration management
├── config/                 # Configuration files
│   └── config.yaml         # Application settings
└── utils/                  # Common utilities
    └── logger.py           # Logging configuration
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review application logs
3. Create an issue with detailed information

---
