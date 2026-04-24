import os
import time
from github import Github
from dotenv import load_dotenv
import ollama

# Load environment variables (The "Secure Vault")
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")

# Initialize GitHub Client
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

def analyze_pr(pr):
    print(f"--- Analyzing PR #{pr.number}: {pr.title} ---")
    
    files = pr.get_files()
    diff_text = ""
    for file in files:
        diff_text += f"\nFile: {file.filename}\n{file.patch}\n"

    # Refined Prompt for better GitHub formatting
    prompt = f"""
    You are an AI Code Reviewer. Analyze this PR diff and provide a concise review.
    Focus on logic errors, security, and performance.
    
    Format your response in Markdown. Use bold for headers.
    
    PR Title: {pr.title}
    Diff Content:
    {diff_text}
    """

    response = ollama.generate(model='qwen2.5-coder:7b', prompt=prompt)
    analysis = response['response']

    # --- NEW: Post the comment to GitHub ---
    comment_body = f"AI Agent Review\n\n{analysis}"
    pr.create_issue_comment(comment_body)
    
    print("ANALYSIS POSTED TO GITHUB.")

def main():
    print(f"Monitoring repository: {REPO_NAME}...")
    processed_prs = set()

    while True:
        # Fetch only 'open' pull requests
        pulls = repo.get_pulls(state='open', sort='created')
        
        for pr in pulls:
            if pr.id not in processed_prs:
                analyze_pr(pr)
                processed_prs.add(pr.id)
        
        # Wait 60 seconds before checking again (Polling)
        time.sleep(60)

if __name__ == "__main__":
    main()