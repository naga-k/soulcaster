import argparse
import subprocess
import os
import re
import sys
import time
import json
from pathlib import Path

def run_command(command, cwd=None, capture_output=True, env=None):
    """Runs a shell command and returns the result."""
    try:
        print(f"Running: {command}")
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
            env=env if env else os.environ
        )
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        raise

def parse_issue_url(url):
    """Parses github issue URL to get owner, repo, and issue number."""
    # Format: https://github.com/owner/repo/issues/number
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError("Invalid GitHub issue URL")
    return match.group(1), match.group(2), match.group(3)

from dotenv import load_dotenv

def main():
    load_dotenv()  # Load API keys from .env

    # Configure Kilo for Gemini if GEMINI_API_KEY is present
    if os.getenv("GEMINI_API_KEY"):
        print("Configuring Kilo for Gemini via config file...")
        
        # Define config path - Kilo uses ~/.kilocode/cli/config.json
        config_dir = Path.home() / ".kilocode" / "cli"
        config_path = config_dir / "config.json"
        
        print(f"DEBUG: Config path will be: {config_path}")
        print(f"DEBUG: Home directory is: {Path.home()}")
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create full config with autoApproval settings for autonomous operation
        config_data = {
            "version": "1.0.0",
            "mode": "code",
            "telemetry": True,
            "provider": "default",
            "providers": [
                {
                    "id": "default",
                    "provider": "gemini",
                    "geminiApiKey": os.getenv("GEMINI_API_KEY"),
                    "apiModelId": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
                    "enableUrlContext": True,
                    "enableGrounding": True
                }
            ],
            "autoApproval": {
                "enabled": True,
                "read": {
                    "enabled": True,
                    "outside": True
                },
                "write": {
                    "enabled": True,
                    "outside": True,
                    "protected": False
                },
                "browser": {
                    "enabled": False
                },
                "retry": {
                    "enabled": False,
                    "delay": 10
                },
                "mcp": {
                    "enabled": True
                },
                "mode": {
                    "enabled": True
                },
                "subtasks": {
                    "enabled": True
                },
                "execute": {
                    "enabled": True,
                    "allowed": [
                        "ls",
                        "cat",
                        "echo",
                        "pwd",
                        "npm",
                        "node",
                        "yarn",
                        "pnpm",
                        "pip",
                        "python",
                        "python3",
                        "pytest",
                        "go",
                        "cargo",
                        "make"
                    ],
                    "denied": [
                        "rm -rf",
                        "sudo rm",
                        "mkfs",
                        "dd if="
                    ]
                },
                "question": {
                    "enabled": False,
                    "timeout": 60
                },
                "todo": {
                    "enabled": True
                }
            },
            "theme": "dark",
            "customThemes": {}
        }
        
        # Write config file
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            print(f"Wrote Kilo config to {config_path}")
        except Exception as e:
            print(f"Failed to write Kilo config: {e}")
    
    parser = argparse.ArgumentParser(description="Fix a GitHub issue using Kilo CLI")
    parser.add_argument("issue_url", help="URL of the GitHub issue to fix")
    args = parser.parse_args()

    try:
        owner, repo, issue_num = parse_issue_url(args.issue_url)
        print(f"Processing Issue #{issue_num} for {owner}/{repo}")

        # 1. Clone the repo
        repo_url = f"https://github.com/{owner}/{repo}.git"
        repo_dir = repo
        
        if os.path.exists(repo_dir):
            print(f"Directory {repo_dir} already exists. Using existing directory.")
        else:
            print(f"Cloning {repo_url}...")
            run_command(f"gh repo clone {owner}/{repo}")

        cwd = os.path.abspath(repo_dir)

        # Configure git user identity (required for commits)
        print("Configuring git user identity...")
        git_email = os.getenv("GIT_USER_EMAIL")
        git_name = os.getenv("GIT_USER_NAME")
        
        if not git_email or not git_name:
            raise Exception("GIT_USER_EMAIL and GIT_USER_NAME environment variables are required")
        
        run_command(f'git config user.email "{git_email}"', cwd=cwd)
        run_command(f'git config user.name "{git_name}"', cwd=cwd)
        
        # Configure git to use GH_TOKEN for authentication
        if os.getenv("GH_TOKEN"):
            print("Configuring git credentials with GH_TOKEN...")
            # Set up git credential helper to use the token
            gh_token = os.getenv("GH_TOKEN")
            # Configure git to use the token for GitHub
            run_command(f'git config credential.helper "!f() {{ echo username=x-access-token; echo password={gh_token}; }}; f"', cwd=cwd)

        # 2. Get Issue Details
        print("Fetching issue details...")
        issue_body = run_command(f"gh issue view {issue_num} --json title,body --template 'Title: {{{{ .title }}}}\n\n{{{{ .body }}}}'", cwd=cwd)
        
        # 3. Create Branch
        branch_name = f"fix/issue-{issue_num}"
        print(f"Creating branch {branch_name}...")
        try:
            run_command(f"git checkout -b {branch_name}", cwd=cwd)
        except:
            print(f"Branch {branch_name} might already exist, switching to it...")
            run_command(f"git checkout {branch_name}", cwd=cwd)

        # 4. Run Kilo
        print("Running Kilo to fix the issue...")
        # Escape double quotes in issue body for the command line
        safe_issue_body = issue_body.replace('"', '\\"')
        prompt = f"Fix the following issue: {safe_issue_body}"
        
        # We use kilocode --auto for autonomous, non-interactive execution
        print(f"Running Kilo on {cwd}...")
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Use subprocess.call instead of subprocess.run for better output streaming
        # subprocess.call inherits stdout/stderr by default, allowing Kilo's output to appear in real-time
        # Do NOT use --nosplash flag as it can interfere with Kilo's interactive prompts
        exit_code = subprocess.call(
            f'kilocode --auto "{prompt}"',
            cwd=cwd,
            shell=True,
            env=os.environ
        )
        
        # DEBUG: Uncomment below to verify subprocess.call is returning
        # print(f"DEBUG: subprocess.call returned with exit code: {exit_code}")
        # sys.stdout.flush()
        
        if exit_code != 0:
            raise Exception(f"Kilo exited with code {exit_code}")
        
        print("kilo finished.")
        sys.stdout.flush()

        # 5. Check for changes
        status = run_command("git status --porcelain", cwd=cwd)
        
        if not status:
            print("No changes detected via file system.")

        # 6. Commit and Push
        print("Changes detected. Committing...")
        run_command("git add .", cwd=cwd)
        # Get a safe commit message
        commit_msg = f"Fix issue #{issue_num}"
        run_command(f"git commit -m '{commit_msg}'", cwd=cwd)
        
        print("Pushing branch...")
        run_command(f"git push -u origin {branch_name}", cwd=cwd)

        # 7. Create PR
        print("Creating Pull Request...")
        pr_url = run_command(f"gh pr create --title 'Fix issue #{issue_num}' --body 'Fixes #{issue_num}\n\nAutomated fix by Kilo.'", cwd=cwd)
        print(f"PR Created: {pr_url}")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

def apply_patches_from_markdown(markdown_text, cwd):
    """Parses markdown code blocks and writes them to files."""
    # Regex to find code blocks with filenames
    # Format:
    # ```python:filename.py
    # code
    # ```
    # or
    # ```
    # # filename.py
    # code
    # ```
    
    # Pattern 1: ```lang:filename
    pattern1 = r"```\w+:([^\n]+)\n(.*?)```"
    matches1 = re.findall(pattern1, markdown_text, re.DOTALL)
    
    applied_count = 0
    
    for filename, content in matches1:
        filename = filename.strip()
        filepath = os.path.join(cwd, filename)
        print(f"Applying patch to {filename}...")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            applied_count += 1
        except Exception as e:
            print(f"Failed to write {filename}: {e}")

    # Pattern 2: Filename in comment or just implied?
    # This is harder to guess. We'll stick to explicit patterns or maybe look for "File: filename" lines before blocks.
    
    return applied_count > 0

if __name__ == "__main__":
    main()
