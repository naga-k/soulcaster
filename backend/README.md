# FeedbackAgent Backend - Data Ingestion Layer

This is the data ingestion layer for FeedbackAgent, built with FastAPI and following TDD principles.

## Features

- **Multi-source ingestion**: Reddit, Sentry, and manual text feedback
- **In-memory storage**: Simple dict-based storage for MVP (will be replaced with database)
- **Reddit polling**: Background service that monitors subreddits for feedback keywords
- **Full test coverage**: Comprehensive test suite with edge cases

## Project Structure

```
backend/
├── __init__.py
├── models.py           # Pydantic data models (FeedbackItem)
├── store.py           # In-memory storage layer
├── main.py            # FastAPI application and endpoints
├── reddit_poller.py   # Reddit polling service
├── requirements.txt   # Python dependencies
├── tests/
│   ├── test_ingestion.py      # Tests for API endpoints
│   └── test_reddit_poller.py  # Tests for Reddit poller
└── README.md
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Server

```bash
# Start the FastAPI server
uvicorn backend.main:app --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Running the Reddit Poller

The Reddit poller runs as a separate background process:

```bash
# Set environment variables
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_SUBREDDIT="programming"  # or comma-separated list

# Run the poller
python -m backend.reddit_poller
```

## Running Tests

```bash
# Run all tests
pytest backend/tests -v

# Run specific test file
pytest backend/tests/test_ingestion.py -v

# Run with coverage
pytest backend/tests --cov=backend --cov-report=term-missing
```

## API Endpoints

### Health Check
- **GET** `/` - Returns service status

### Ingestion Endpoints

#### POST /ingest/reddit
Ingest feedback from Reddit (called by reddit_poller).

**Request Body**:
```json
{
  "id": "uuid",
  "source": "reddit",
  "external_id": "t3_12345",
  "title": "Bug found in feature X",
  "body": "Detailed description...",
  "metadata": {
    "subreddit": "programming",
    "permalink": "/r/programming/...",
    "author": "username"
  },
  "created_at": "2023-10-27T10:00:00Z"
}
```

#### POST /ingest/sentry
Ingest error reports from Sentry webhook.

**Request Body**: Standard Sentry webhook payload

#### POST /ingest/manual
Ingest manually submitted text feedback.

**Request Body**:
```json
{
  "text": "The login button doesn't work on mobile"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDDIT_CLIENT_ID` | Reddit API client ID | Required for poller |
| `REDDIT_CLIENT_SECRET` | Reddit API client secret | Required for poller |
| `REDDIT_SUBREDDIT` | Subreddit(s) to monitor | `"all"` |
| `BACKEND_URL` | URL of the ingestion API | `http://localhost:8000` |

## Development Notes

- This is an MVP implementation with in-memory storage
- Follow TDD: write tests before implementation
- All code includes comprehensive docstrings
- Error handling implemented for production resilience

## Next Steps

From the task plan (tasks/data_ingestion.md):
- ✅ Environment & Project Structure
- ✅ Domain Models
- ✅ In-Memory Store
- ✅ API Endpoints (TDD)
- ✅ Reddit Poller (TDD)
- ✅ Integration Verification

Ready to integrate with the Brain layer (clustering and triage)!
