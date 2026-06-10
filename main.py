import os
import time
from github import Github, Auth
from dotenv import load_dotenv
from squad_logic import squad_app

# Force-load environment variables from the current working directory
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")

# --- DIAGNOSTIC SECURITY VERIFICATION LOGS ---
print("==================================================")
print("[Diag] Checking environment initialization...")
if not GITHUB_TOKEN:
    print("[Diag ERROR] GITHUB_TOKEN is completely EMPTY or None! Check your .env file placement.")
else:
    # Safely print just the prefix to verify it is loading without exposing it
    print(f"[Diag] GITHUB_TOKEN loaded successfully. Begins with: {GITHUB_TOKEN[:12]}...")

if not REPO_NAME:
    print("[Diag ERROR] REPO_NAME is missing from your environment setup.")
else:
    print(f"[Diag] Target Repository registered: {REPO_NAME}")
print("==================================================")

# Initialize the credential handshake configuration
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)

def analyze_pr_with_squad(pr):
    print(f"\n==================================================")
    print(f"[Orchestrator] Ingesting PR #{pr.number}: '{pr.title}'")
    print(f"==================================================")
    
    files = pr.get_files()
    diff_text = ""
    
    for file in files:
        diff_text += f"\nFile: {file.filename}\n{file.patch}\n"
        try:
            file_content = repo.get_contents(file.filename, ref=pr.head.sha).decoded_content.decode('utf-8')
            with open(file.filename, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"[Workspace] Cached local file copy: {file.filename}")
        except Exception as e:
            print(f"[Warning] Could not cache local copy of {file.filename}: {e}")

    initial_state = {
        "messages": [],
        "code_diff": diff_text,
        "security_report": "Pending scan...",
        "performance_report": "Pending scan...",
        "janitor_report": "Pending scan...",
        "is_ready_to_push": False
    }

    print("[Orchestrator] Handing execution to LangGraph Squad...")
    final_state = squad_app.invoke(initial_state)
    print("[Orchestrator] LangGraph execution cycle complete.")

    comment_body = (
        f"## Autonomous Engineering Squad Report\n\n"
        f"Our specialized agents have processed the proposed changes locally on an AMD Ryzen 7 host system.\n\n"
        f"### Security Audit\n{final_state.get('security_report', 'No report generated.')}\n\n"
        f"### Performance Review\n{final_state.get('performance_report', 'No report generated.')}\n\n"
        f"### Code Style & Tech Debt\n{final_state.get('janitor_report', 'No report generated.')}\n\n"
        f"---\n"
        f"### Final Evaluation Status\n"
    )

    if final_state.get("is_ready_to_push"):
        comment_body += "**APPROVED:** The code satisfies safety, performance, and structural guidelines. Ready to merge."
    else:
        comment_body += "**CORRECTIONS APPLIED:** Critical defects were found. The local Fixer Agent was deployed to rewrite files."

    print("[Orchestrator] Posting feedback to GitHub...")
    pr.create_issue_comment(comment_body)
    print("[Success] Feedback successfully published.")

def main():
    print(f"[Start] Monitoring repository: {REPO_NAME} for open Pull Requests...")
    processed_prs = set()

    while True:
        try:
            pulls = repo.get_pulls(state='open', sort='created')
            for pr in pulls:
                if pr.id not in processed_prs:
                    analyze_pr_with_squad(pr)
                    processed_prs.add(pr.id)
        except Exception as e:
            print(f"[Error] Connection or runtime issue: {e}")
        
        print("[Idle] Sleeping for 60 seconds before next repository scan...")
        time.sleep(60)

if __name__ == "__main__":
    main()