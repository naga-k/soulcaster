"""Reddit poller for FeedbackAgent.

This module polls Reddit submissions and comments for keywords that indicate
user feedback (bugs, errors, feature requests). Matching posts are normalized
and sent to the ingestion API.
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import praw
import requests

# Keywords to filter Reddit posts for potential feedback
KEYWORDS = ["bug", "broken", "error", "crash", "doesn't work", "feature"]

# Default API endpoint for posting feedback
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def process_submission(submission):
    """
    Process a Reddit submission and post it to the ingestion API if it matches keywords.

    Checks submission title and body for feedback-related keywords.
    If found, normalizes the data and posts to the backend API.

    Args:
        submission: PRAW Submission object from Reddit stream
    """
    title = submission.title
    body = submission.selftext
    text_to_check = (title + " " + body).lower()

    # Check if any keyword is present in the post
    if any(keyword in text_to_check for keyword in KEYWORDS):
        payload = {
            "id": str(uuid4()),
            "source": "reddit",
            "external_id": str(submission.id),
            "title": title,
            "body": body[:10000],  # Truncate body if too long (max 10k chars)
            "metadata": {
                "subreddit": str(submission.subreddit),
                "permalink": submission.permalink,
                "author": str(submission.author),
                "created_utc": submission.created_utc
            },
            "created_at": datetime.fromtimestamp(submission.created_utc, timezone.utc).isoformat()
        }
        try:
            response = requests.post(f"{BACKEND_URL}/ingest/reddit", json=payload, timeout=10)
            response.raise_for_status()
            print(f"Posted Reddit feedback: {title[:50]}...")
        except requests.exceptions.RequestException as e:
            print(f"Failed to post to backend: {e}")
        except Exception as e:
            print(f"Unexpected error processing submission: {e}")


def poll_reddit():
    """
    Poll Reddit for new submissions matching feedback keywords.

    Uses PRAW to stream new submissions from configured subreddits.
    Runs indefinitely, processing submissions as they appear.

    Environment variables:
        REDDIT_CLIENT_ID: Reddit API client ID
        REDDIT_CLIENT_SECRET: Reddit API client secret
        REDDIT_SUBREDDIT: Subreddit(s) to monitor (default: "all")
    """
    # Initialize Reddit client
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="FeedbackAgent/0.1"
    )
    subreddit_name = os.getenv("REDDIT_SUBREDDIT", "all")
    subreddit = reddit.subreddit(subreddit_name)

    print(f"Polling r/{subreddit_name} for feedback keywords: {', '.join(KEYWORDS)}")
    try:
        # Stream submissions, skipping existing posts
        for submission in subreddit.stream.submissions(skip_existing=True):
            process_submission(submission)
    except KeyboardInterrupt:
        print("\nStopping Reddit poller...")
    except Exception as e:
        print(f"Error in Reddit polling loop: {e}")
        raise


if __name__ == "__main__":
    poll_reddit()
