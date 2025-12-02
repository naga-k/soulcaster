import os
import random
import requests
import time
import subprocess
import shutil
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path="backend/.env") # Try specific path if root .env fails or isn't picked up

# Configuration
# GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def generate_math_code():
    """
    Generate a Python module source string that provides basic arithmetic functions.
    
    The returned source defines functions: add, subtract, multiply, divide, power, sqrt, and factorial. Several functions intentionally omit input validation (for example, divide does not guard against zero, sqrt does not guard against negative input, and factorial does not handle negative values).
    
    Returns:
        str: A multi-line string containing the Python source code for the arithmetic module.
    """
    return """
import math

def add(a, b):
    \"\"\"Adds two numbers.\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"Subtracts b from a.\"\"\"
    return a - b

def multiply(a, b):
    \"\"\"Multiplies two numbers.\"\"\"
    return a * b

def divide(a, b):
    \"\"\"Divides a by b.
    TODO: Add error handling for zero division.
    \"\"\"
    # Bug: No check for b == 0
    return a / b

def power(a, b):
    \"\"\"Returns a raised to the power of b.\"\"\"
    return a ** b

def sqrt(a):
    \"\"\"Returns the square root of a.\"\"\"
    # Bug: No check for negative numbers, will raise ValueError
    return math.sqrt(a)

def factorial(n):
    \"\"\"Calculates factorial of n.\"\"\"
    if n == 0:
        return 1
    # Bug: Infinite recursion for negative numbers
    return n * factorial(n - 1)
"""

def generate_string_code():
    """
    Generate source code for a small string-utilities Python module.
    
    The returned code defines four functions: `reverse_string`, `to_upper`, `is_palindrome`, and `truncate`. The generated module intentionally contains two noteworthy behaviors: `is_palindrome` performs a case-sensitive comparison, and `truncate` raises an `IndexError` when `length` is greater than the input string length.
    
    Returns:
        str: A multi-line string containing the Python source for the string utilities module.
    """
    return """
def reverse_string(s):
    \"\"\"Reverses a string.\"\"\"
    return s[::-1]

def to_upper(s):
    \"\"\"Converts string to uppercase.\"\"\"
    return s.upper()

def is_palindrome(s):
    \"\"\"Checks if a string is a palindrome.\"\"\"
    # Bug: Case sensitive, so 'Racecar' returns False
    return s == s[::-1]

def truncate(s, length):
    \"\"\"Truncates string to length.\"\"\"
    # Bug: Might raise IndexError if length > len(s) depending on implementation, 
    # but python slicing is safe. Let's introduce a manual bug.
    if length > len(s):
        raise IndexError("Length is too large")
    return s[:length]
"""

def generate_user_manager_code():
    """
    Provide source code for a simple UserManager class with intentionally buggy behaviors.
    
    The returned source defines a UserManager that stores users in an internal dictionary and exposes add_user, get_user, and delete_user methods. Observed behaviors in the generated code: add_user stores a user id→name mapping; get_user returns the name or `None` when the id is missing; delete_user checks for membership but does not remove the entry.
    
    Returns:
        str: Python source code as a multi-line string defining the described UserManager class.
    """
    return """
class UserManager:
    def __init__(self):
        self.users = {}

    def add_user(self, user_id, name):
        self.users[user_id] = name

    def get_user(self, user_id):
        # Bug: Returns None but doesn't raise error, caller might expect exception
        return self.users.get(user_id)

    def delete_user(self, user_id):
        # Bug: Does not actually delete the user
        if user_id in self.users:
            pass # Forgot to add 'del self.users[user_id]'
"""

def create_local_files(target_dir="."):
    """
    Create a project directory at the given path and populate it with example modules and a README.
    
    This will remove any existing directory at target_dir, recreate it, and write four files into it:
    - math_ops.py (generated example math module)
    - string_utils.py (generated example string utilities)
    - user_manager.py (generated example user manager)
    - README.md (short project description)
    
    Parameters:
    	target_dir (str): Path where the project directory will be created; an existing directory at this path will be deleted before creation.
    """
    print(f"Creating files in {target_dir}...")
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir)
    
    with open(os.path.join(target_dir, "math_ops.py"), "w") as f:
        f.write(generate_math_code())
        
    with open(os.path.join(target_dir, "string_utils.py"), "w") as f:
        f.write(generate_string_code())

    with open(os.path.join(target_dir, "user_manager.py"), "w") as f:
        f.write(generate_user_manager_code())
    
    with open(os.path.join(target_dir, "README.md"), "w") as f:
        f.write("# Test Project\n\nA project with some intentional bugs for testing clustering.\n")

def push_to_github(repo_url, target_dir="."):
    """
    Initialize a git repository in target_dir and push its contents to the specified remote repository.
    
    Creates a new git repository (or reinitializes one) in target_dir, stages all files, makes an initial commit with message "Initial commit with buggy code", sets the branch to `main`, adds `origin` pointing to repo_url, and force-pushes the `main` branch to the remote. If any git command fails, an error message is printed.
    
    Parameters:
        repo_url (str): The remote repository URL (e.g., "https://github.com/owner/repo.git").
        target_dir (str): Path to the directory to initialize and push (default: current directory).
    """
    print(f"Pushing to {repo_url}...")
    try:
        subprocess.run(["git", "init"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit with buggy code"], cwd=target_dir, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=target_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=target_dir, check=True)
        subprocess.run(["git", "push", "-u", "-f", "origin", "main"], cwd=target_dir, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")

def create_issues(repo_owner, repo_name, token):
    """
    Create a set of GitHub issues on the specified repository.
    
    Posts a curated, shuffled list of issue payloads (clustered bug reports plus additional noise) to the repository's Issues API, creating each issue in sequence. If the API responds with a non-201 status the response text is printed; on HTTP 403 or 429 the function waits 60 seconds before continuing. The function also pauses briefly between requests to help avoid rate limiting.
    
    Parameters:
    	repo_owner (str): GitHub repository owner (user or organization).
    	repo_name (str): Repository name.
    	token (str): Personal access token with permission to create issues on the repository.
    """
    print(f"Creating issues for {repo_owner}/{repo_name}...")
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Define clusters of issues (same bug, different wording)
    issue_clusters = [
        # Cluster 1: Division by zero
        [
            {"title": "Division by zero error in math_ops", "body": "The divide function crashes when the second argument is 0.", "labels": ["bug"]},
            {"title": "App crashes when dividing by 0", "body": "I tried to use the divide function with 0 as the denominator and it raised a ZeroDivisionError.", "labels": ["bug", "critical"]},
            {"title": "Unhandled exception in divide function", "body": "We need to handle the case where b is 0 in the divide function.", "labels": ["enhancement"]},
            {"title": "math_ops.divide needs input validation", "body": "Please add a check to ensure we don't divide by zero.", "labels": ["bug"]},
        ],
        # Cluster 2: Sqrt negative number
        [
            {"title": "ValueError when calculating square root of negative numbers", "body": "sqrt(-1) crashes the program.", "labels": ["bug"]},
            {"title": "sqrt function should handle negative inputs gracefully", "body": "Maybe return None or a complex number instead of crashing?", "labels": ["enhancement"]},
            {"title": "Crash report: math domain error in sqrt", "body": "Got a math domain error when calling sqrt with a negative value.", "labels": ["bug"]},
        ],
        # Cluster 3: Palindrome case sensitivity
        [
            {"title": "is_palindrome should be case insensitive", "body": "is_palindrome('Racecar') returns False, which is unexpected.", "labels": ["bug"]},
            {"title": "Palindrome check fails for mixed case strings", "body": "The function seems to compare raw strings without normalizing case.", "labels": ["bug"]},
            {"title": "String utils palindrome bug with capital letters", "body": "Capital letters cause the palindrome check to fail.", "labels": ["bug"]},
            {"title": "Make is_palindrome robust to case", "body": "It should convert to lowercase before comparing.", "labels": ["enhancement"]},
        ],
        # Cluster 4: Delete user bug
        [
            {"title": "delete_user method doesn't remove the user from the list", "body": "I called delete_user but the user is still there.", "labels": ["bug", "critical"]},
            {"title": "Users still exist after calling delete_user", "body": "The delete_user function seems to do nothing.", "labels": ["bug"]},
            {"title": "UserManager.delete_user seems to be a no-op", "body": "Checked the code, it passes but doesn't delete.", "labels": ["bug"]},
            {"title": "Memory leak? Users not being deleted.", "body": "Our user list keeps growing even though we delete users.", "labels": ["bug"]},
        ],
        # Cluster 5: Truncate index error
        [
            {"title": "IndexError in truncate function for short strings", "body": "If I try to truncate a string to a length larger than the string, it crashes.", "labels": ["bug"]},
            {"title": "truncate throws exception if length is larger than string", "body": "Shouldn't it just return the whole string?", "labels": ["enhancement"]},
            {"title": "String truncation bug with large length", "body": "truncate('abc', 10) raises an error.", "labels": ["bug"]},
        ],
        # Cluster 6: Factorial recursion
        [
            {"title": "Factorial stack overflow on negative numbers", "body": "Calling factorial with a negative number causes infinite recursion.", "labels": ["bug"]},
            {"title": "Infinite loop in factorial", "body": "factorial(-1) never returns.", "labels": ["bug"]},
        ]
    ]

    # Flatten and add some noise
    all_issues = []
    for cluster in issue_clusters:
        all_issues.extend(cluster)

    # Add noise/unrelated issues
    noise_issues = [
        {"title": "Update README", "body": "Add installation instructions.", "labels": ["documentation"]},
        {"title": "Add CI/CD pipeline", "body": "We need GitHub Actions.", "labels": ["devops"]},
        {"title": "Refactor directory structure", "body": "Move files to src/.", "labels": ["refactor"]},
        {"title": "Add license", "body": "MIT License needed.", "labels": ["legal"]},
        {"title": "Support Python 3.12", "body": "Test with latest python.", "labels": ["enhancement"]},
        {"title": "Add logging to UserManager", "body": "We need to see when users are added.", "labels": ["enhancement"]},
        {"title": "Create a CLI interface", "body": "Would be nice to run this from command line.", "labels": ["enhancement"]},
        {"title": "Fix typo in comments", "body": "Some typos in docstrings.", "labels": ["documentation"]},
        {"title": "Add unit tests", "body": "We have 0% coverage.", "labels": ["testing"]},
        {"title": "Performance optimization for large numbers", "body": "Math ops are slow.", "labels": ["enhancement"]},
    ]
    
    all_issues.extend(noise_issues)
    
    # Shuffle to mix them up
    random.shuffle(all_issues)

    print(f"Generated {len(all_issues)} issues to create.")

    for i, issue in enumerate(all_issues):
        print(f"Creating issue {i+1}/{len(all_issues)}: {issue['title']}")
        response = requests.post(url, json=issue, headers=headers)
        if response.status_code != 201:
            print(f"Failed to create issue: {response.text}")
            # If rate limited, wait a bit
            if response.status_code == 403 or response.status_code == 429:
                print("Rate limited, waiting 60s...")
                time.sleep(60)
        
        # Sleep a bit to avoid hitting secondary rate limits
        time.sleep(2)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python generate_test_data.py <repo_url> <token>")
        sys.exit(1)
        
    repo_url = sys.argv[1]
    token = sys.argv[2]
    
    # Extract owner and repo name from URL
    # Expected format: https://github.com/owner/repo.git or https://github.com/owner/repo
    parts = repo_url.rstrip(".git").split("/")
    repo_owner = parts[-2]
    repo_name = parts[-1]

    # Create a temporary directory for the repo
    temp_dir = "temp_test_repo"
    
    create_local_files(temp_dir)
    push_to_github(repo_url, temp_dir)
    create_issues(repo_owner, repo_name, token)
    
    # Cleanup
    # shutil.rmtree(temp_dir)
    print("Done!")