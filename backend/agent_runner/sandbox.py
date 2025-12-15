import asyncio
import logging
import os
import json
from uuid import UUID
from datetime import datetime, timezone

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    Sandbox = None

from models import AgentJob, CodingPlan, IssueCluster
from store import update_job
from agent_runner import AgentRunner, register_runner

logger = logging.getLogger(__name__)

# Template ID for the Kilocode sandbox.
KILOCODE_TEMPLATE_ID = os.getenv("KILOCODE_TEMPLATE_ID", "base") 

AGENT_SCRIPT = r"""
import os
import sys
import json
import subprocess
import time
from pathlib import Path

def log(msg):
    print(msg)
    sys.stdout.flush()

def run_command(cmd, cwd=None, env=None):
    log(f"Running: {cmd}")
    try:
        subprocess.check_call(cmd, shell=True, cwd=cwd, env=env)
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {e}")
        raise

def setup_kilo_config():
    # Configure Kilo CLI
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        log("WARN: No GEMINI_API_KEY found")
        return

    config_dir = Path.home() / ".kilocode" / "cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    
    config_data = {
        "version": "1.0.0",
        "mode": "code",
        "provider": "default",
        "providers": [{
            "id": "default",
            "provider": "gemini",
            "geminiApiKey": gemini_key,
            "apiModelId": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
            "enableUrlContext": True
        }],
        "autoApproval": {
            "enabled": True,
            "execute": {"enabled": True},
            "read": {"enabled": True},
            "write": {"enabled": True}
        }
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    log("Kilo config written.")

def main():
    # 1. Read Plan
    with open("/tmp/plan.json", "r") as f:
        plan = json.load(f)
    
    repo_url = os.getenv("REPO_URL")
    if not repo_url:
        raise Exception("REPO_URL env var missing")

    # 2. Extract owner/repo
    # https://github.com/owner/repo.git or https://github.com/owner/repo
    parts = repo_url.strip("/").replace(".git", "").split("/")
    repo_name = parts[-1]
    owner = parts[-2]
    
    # 3. Clone
    # We use GH_TOKEN from env implicitly with gh cli or git
    # But for simplicity, let's use git with token if needed, or assume ssh/https helper is set up
    # The sandbox usually has gh installed.
    # Let's try gh repo clone
    log(f"Cloning {owner}/{repo_name}...")
    run_command(f"gh repo clone {owner}/{repo_name} repo")
    cwd = os.path.abspath("repo")

    # 4. Git Config
    run_command('git config user.email "agent@soulcaster.dev"', cwd=cwd)
    run_command('git config user.name "Soulcaster Agent"', cwd=cwd)

    # 5. Branch
    branch_name = f"fix/soulcaster-{int(time.time())}"
    run_command(f"git checkout -b {branch_name}", cwd=cwd)

    # 6. Run Kilocode
    setup_kilo_config()
    
    prompt = f"Executing Coding Plan: {plan['title']}\n\n"
    prompt += f"Description: {plan['description']}\n\n"
    prompt += f"Tasks:\n"
    for task in plan.get('tasks', []):
        prompt += f"- {task}\n"
    
    log("Starting Kilocode...")
    # Escape quotes for shell safety - simple version
    safe_prompt = prompt.replace('"', '\\"')
    run_command(f'kilocode --auto "{safe_prompt}"', cwd=cwd)

    # 7. Push and PR
    run_command(f"git add .", cwd=cwd)
    # Check if anything to commit
    try:
        run_command(f"git commit -m 'Fix: {plan['title']}'", cwd=cwd)
        run_command(f"git push -u origin {branch_name}", cwd=cwd)
        
        pr_title = f"Fix: {plan['title']}"
        pr_body = f"Automated fix based on plan.\n\n{plan['description']}"
        
        # gh pr create
        # Ensure GH_TOKEN is available to gh cli
        run_command(f"gh pr create --title \"{pr_title}\" --body \"{pr_body}\" --head {branch_name}", cwd=cwd)
        log("PR Created Successfully.")
    except Exception as e:
        log(f"Git/PR step failed (maybe no changes?): {e}")

if __name__ == "__main__":
    main()
"""

class SandboxKilocodeRunner(AgentRunner):
    async def start(self, job: AgentJob, plan: CodingPlan, cluster: IssueCluster) -> None:
        if not Sandbox:
            logger.error("e2b SDK not installed. Cannot run SandboxKilocodeRunner.")
            await self._fail_job(job.id, "e2b SDK missing")
            return

        try:
             logger.info(f"Starting sandbox job {job.id} for plan {plan.id}")
             try:
                 update_job(job.id, status="running", logs="Initializing sandbox environment...")
             except Exception as update_err:
                 logger.error(f"Failed to update job status: {update_err}")
                 raise update_err

             # Prepare Environment Variables
             env_vars = {
                 "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                 "GH_TOKEN": os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", "")),
                 "REPO_URL": cluster.github_repo_url or "",
                 "KILO_API_MODEL_ID": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
             }
             
             if not env_vars["REPO_URL"]:
                  # Fallback if repo url not on cluster, try to construct? or fail
                  await self._fail_job(job.id, "Cluster missing github_repo_url")
                  return

             logger.info(f"Preparing environment for job {job.id}...")
             # Create Sandbox
             # We assume the template (KILOCODE_TEMPLATE_ID) already has 'kilocode' installed via e2b.Dockerfile.
             # If not, the script execution might fail or we'd need to add 'pip install' here.
             logger.info(f"Creating sandbox with template ID: {KILOCODE_TEMPLATE_ID}")
             sandbox = Sandbox.create(template=KILOCODE_TEMPLATE_ID, envs=env_vars)
             try:
                await self._log(job.id, "Sandbox created.")
                logger.info(f"Sandbox created: {sandbox.sandbox_id}")

                # Upload Agent Script and Plan
                await self._log(job.id, "Uploading context...")
                logger.info("Uploading agent script and plan...")
                sandbox.files.write("/tmp/agent_script.py", AGENT_SCRIPT)
                sandbox.files.write("/tmp/plan.json", plan.model_dump_json())
                logger.info("Context uploaded.")

                # Execute Script
                await self._log(job.id, "Executing agent script...")
                logger.info("Starting execution of agent script...")
                
                # Run and stream logs
                # In sync mode, on_stdout might be called synchronously? 
                # We need to adapt handle_stdout/stderr to be sync or wrap them?
                # E2B sync client typically expects sync callbacks.
                # But our _log method is async! verify later.
                # If we pass async func to sync callback, it might return a coroutine and not await it.
                # We might need to run_coroutine_threadsafe if we are in a loop.
                # Or just use print for now? 
                # Ideally, we define sync wrappers that call async_to_sync or similar.
                # Given we are in an async start() method, we have a running loop.
                
                def handle_stdout(output):
                    # Trying to schedule async log on existing loop
                    try:
                        loop = asyncio.get_running_loop()
                        if loop.is_running():
                             asyncio.run_coroutine_threadsafe(self._log(job.id, output.line), loop)
                    except:
                        pass

                def handle_stderr(output):
                    try:
                        loop = asyncio.get_running_loop()
                        if loop.is_running():
                             asyncio.run_coroutine_threadsafe(self._log(job.id, f"[ERR] {output.line}"), loop)
                    except:
                        pass

                proc = sandbox.commands.run(
                    "python3 /tmp/agent_script.py",
                    on_stdout=handle_stdout,
                    on_stderr=handle_stderr,
                    timeout=600 # 10 mins timeout
                )

                if proc.exit_code == 0:
                    # Success
                     # We might want to parse the PR URL from logs if not explicitly returned?
                     # The script logs "PR Created Successfully."
                     # For now, mark success.
                     update_job(job.id, status="success", logs=f"{job.logs}\nSuccess.")
                else:
                     await self._fail_job(job.id, f"Agent script exited with code {proc.exit_code}")
            
             finally:
                if sandbox:
                    sandbox.kill()

        except Exception as e:
            logger.exception(f"Job {job.id} failed in sandbox")
            await self._fail_job(job.id, str(e))

    async def _log(self, job_id: UUID, message: str):
        from store import get_job, update_job
        job = get_job(job_id)
        if job:
            # Append log line
            # In high freq, this is bad, but acceptable for prototype
            current_logs = job.logs or ""
            new_log = f"{message}\n"
            update_job(job_id, logs=current_logs + new_log)

    async def _fail_job(self, job_id: UUID, error: str):
        update_job(job_id, status="failed", logs=f"Error: {error}")

register_runner("sandbox_kilo", SandboxKilocodeRunner)
