import unittest
from unittest.mock import MagicMock, patch
from backend.reddit_poller import poll_reddit

class TestRedditPoller(unittest.TestCase):
    @patch('backend.reddit_poller.praw.Reddit')
    @patch('backend.reddit_poller.requests.post')
    def test_poll_reddit(self, mock_post, mock_reddit):
        # Mock Reddit instance and subreddit
        mock_reddit_instance = MagicMock()
        mock_reddit.return_value = mock_reddit_instance
        mock_subreddit = MagicMock()
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        
        # Mock submissions
        mock_submission = MagicMock()
        mock_submission.title = "Bug in the app"
        mock_submission.selftext = "It crashes."
        mock_submission.id = "12345"
        mock_submission.author.name = "user1"
        mock_submission.created_utc = 1698400800.0
        mock_submission.permalink = "/r/test/12345"
        
        # Mock stream to return one submission then raise StopIteration (or just return list)
        # Since stream is a generator, we can mock it to yield items
        mock_subreddit.stream.submissions.return_value = [mock_submission]
        
        # Run poller (we need to modify poller to accept a limit or run once for testing)
        # For this test, we'll assume poll_reddit processes the stream. 
        # To avoid infinite loop, we might need to inject a way to stop, or mock stream to end.
        
        # Let's assume poll_reddit takes a 'run_once' arg or similar, or we just test the processing logic.
        # Better: extract processing logic to a function `process_submission`.
        
        from backend.reddit_poller import process_submission
        process_submission(mock_submission)
        
        # Verify POST called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:8000/ingest/reddit"
        payload = kwargs['json']
        assert payload['title'] == "Bug in the app"
        assert payload['source'] == "reddit"
        assert payload['external_id'] == "12345"

    @patch('backend.reddit_poller.requests.post')
    def test_filter_keywords(self, mock_post):
        """Test that posts without keywords are filtered out."""
        from backend.reddit_poller import process_submission
        mock_submission = MagicMock()
        mock_submission.title = "Just a discussion"
        mock_submission.selftext = "Everything is fine."

        process_submission(mock_submission)

        mock_post.assert_not_called()

    @patch('backend.reddit_poller.requests.post')
    def test_multiple_keywords(self, mock_post):
        """Test that posts with multiple keywords are still processed once."""
        from backend.reddit_poller import process_submission
        mock_submission = MagicMock()
        mock_submission.title = "Bug with error and crash"
        mock_submission.selftext = "It's broken."
        mock_submission.id = "multi_kw"
        mock_submission.author.name = "user2"
        mock_submission.created_utc = 1698400800.0
        mock_submission.permalink = "/r/test/multi"

        process_submission(mock_submission)

        mock_post.assert_called_once()

    @patch('backend.reddit_poller.requests.post')
    def test_keyword_case_insensitive(self, mock_post):
        """Test that keyword matching is case-insensitive."""
        from backend.reddit_poller import process_submission
        mock_submission = MagicMock()
        mock_submission.title = "BUG REPORT"
        mock_submission.selftext = "CRASH on startup"
        mock_submission.id = "uppercase"
        mock_submission.author.name = "user3"
        mock_submission.created_utc = 1698400800.0
        mock_submission.permalink = "/r/test/upper"

        process_submission(mock_submission)

        mock_post.assert_called_once()

    @patch('backend.reddit_poller.requests.post')
    def test_empty_body(self, mock_post):
        """Test processing submission with empty body but keyword in title."""
        from backend.reddit_poller import process_submission
        mock_submission = MagicMock()
        mock_submission.title = "Bug found"
        mock_submission.selftext = ""
        mock_submission.id = "empty_body"
        mock_submission.author.name = "user4"
        mock_submission.created_utc = 1698400800.0
        mock_submission.permalink = "/r/test/empty"

        process_submission(mock_submission)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        assert payload['body'] == ""

    @patch('backend.reddit_poller.requests.post')
    def test_api_failure(self, mock_post):
        """Test that API failures are handled gracefully."""
        from backend.reddit_poller import process_submission
        mock_post.side_effect = Exception("API Error")

        mock_submission = MagicMock()
        mock_submission.title = "Bug found"
        mock_submission.selftext = "Details here"

        # Should not raise exception
        process_submission(mock_submission)
