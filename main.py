import os
import time
from github import Github, Auth
from dotenv import load_dotenv

# Import the compiled multi-agent application from your squad file
from squad_logic import squad_app

# Load environment variables securely from the .env file
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")

# Initialize the GitHub Client using the 2026 recommended Auth token structure
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)

def analyze_pr_with_squad(pr):
    print(f"\n==================================================")
    print(f" [Orchestrator] Ingesting PR #{pr.number}: '{pr.title}'")
    print(f"==================================================")
    
    # Extract the code changes (the raw diff data) from the PR
    files = pr.get_files()
    diff_text = ""
    for file in files:
        diff_text += f"\nFile: {file.filename}\n{file.patch}\n"

    # Initialize the universal Shared Memory state for LangGraph
    initial_state = {
        "messages": [],
        "code_diff": diff_text,
        "security_report": "Pending scan...",
        "performance_report": "Pending scan...",
        "janitor_report": "Pending scan...",
        "is_ready_to_push": False
    }

    print(" Handing execution control to the LangGraph Squad...")
    # Invoke the graph. This handles Fan-Out, Fan-In, and Self-Healing loops automatically
    final_state = squad_app.invoke(initial_state)
    print(" LangGraph execution cycle complete.")

    # Synthesize the final consolidated markdown report for GitHub
    comment_body = (
        f"##  Autonomous Engineering Squad Report\n\n"
        f"Our specialized agents have processed the proposed changes locally on an AMD Ryzen 7 host system.\n\n"
        f"###  Security Audit\n{final_state.get('security_report', 'No report generated.')}\n\n"
        f"###  Performance Review\n{final_state.get('performance_report', 'No report generated.')}\n\n"
        f"###  Code Style & Tech Debt\n{final_state.get('janitor_report', 'No report generated.')}\n\n"
        f"---\n"
        f"###  Final Evaluation Status\n"
    )

    if final_state.get("is_ready_to_push"):
        comment_body += " **APPROVED:** The code satisfies all safety, performance, and structural guidelines. Ready to merge!"
    else:
        comment_body += " **CORRECTIONS APPLIED:** Critical defects were found. The local Fixer Agent was deployed to rewrite and patch the filesystem."

    # Post the combined findings as a master comment on the GitHub PR
    print(" Posting compiled multi-agent feedback to GitHub...")
    pr.create_issue_comment(comment_body)
    print(" Feedback successfully published.")

def main():
    print(f" Monitoring repository: {REPO_NAME} for open Pull Requests...")
    processed_prs = set()

    while True:
        try:
            # Safely fetch active proposals from the remote repository
            pulls = repo.get_pulls(state='open', sort='created')
            
            for pr in pulls:
                if pr.id not in processed_prs:
                    analyze_pr_with_squad(pr)
                    processed_prs.add(pr.id)
            
        except Exception as e:
            print(f" Connection or runtime issue encountered: {e}")
        
        # Poll every 60 seconds to manage local processing loops evenly
        print(" Sleeping for 60 seconds before next repository scan...")
        time.sleep(60)

if __name__ == "__main__":
    main()