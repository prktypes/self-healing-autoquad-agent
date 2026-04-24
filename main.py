import os
import time
import json
import re
from github import Github, Auth
from dotenv import load_dotenv
import ollama

from tools import run_terminal_command

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")

# Initialize GitHub Client
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)


def analyze_pr(pr):
    print(f"--- Analyzing PR #{pr.number}: {pr.title} ---")
    
    files = pr.get_files()
    diff_text = ""
    for file in files:
        diff_text += f"\nFile: {file.filename}\n{file.patch}\n"

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

    comment_body = f"AI Agent Review\n\n{analysis}"
    pr.create_issue_comment(comment_body)
    
    print("ANALYSIS POSTED TO GITHUB.")


def autonomous_agent_loop(user_prompt):
    system_prompt = (
        "You are an autonomous AI engineer on WINDOWS. You use PowerShell. "
        "To perform actions, you MUST use the 'run_terminal_command' tool. "
        "If you need to run multiple commands, do them one by one. "
        "Wait for the output of each command before moving to the next step."
    )
    
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ]

    # Define the tool configuration
    tools = [{
        'type': 'function',
        'function': {
            'name': 'run_terminal_command',
            'description': 'Execute a PowerShell command locally.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': 'The PowerShell command'}
                },
                'required': ['command']
            }
        }
    }]

    for turn in range(10):  # Increased turns to allow for more fixing
        print(f"\n--- Turn {turn + 1} ---")
        response = ollama.chat(model='qwen2.5-coder:7b', messages=messages, tools=tools)
        msg = response['message']
        messages.append(msg)

        # 1. Check for official tool calls
        tool_calls = msg.get('tool_calls', [])
        
        # 2. Backup: If model wrote JSON as text, try to extract it
        if not tool_calls and '{"name":' in (msg.get('content') or ''):
            try:
                # Basic extraction of JSON from text
                start = msg['content'].find('{')
                end = msg['content'].rfind('}') + 1
                json_data = json.loads(msg['content'][start:end])
                # Format it like a real tool call for the logic below
                tool_calls = [{'function': json_data}]
            except:
                pass

        # If absolutely no tool calls, we are finished
        if not tool_calls:
            print(f" Final Response: {msg['content']}")
            break

        # 3. Execute the tools
        for tool in tool_calls:
            name = tool['function']['name']
            args = tool['function']['arguments']
            
            if name == 'run_terminal_command':
                cmd = args['command']
                print(f"  Executing: {cmd}")
                obs = run_terminal_command(cmd)
                
                print(f" Observation: {obs['output']}")
                
                # Feedback loop: Tell the agent what happened
                messages.append({
                    'role': 'tool',
                    'content': obs['output'],
                    'name': name
                })


def main():
    print(f"Monitoring repository: {REPO_NAME}...")
    processed_prs = set()

    while True:
        pulls = repo.get_pulls(state='open', sort='created')
        
        for pr in pulls:
            if pr.id not in processed_prs:
                analyze_pr(pr)
                processed_prs.add(pr.id)
        
        time.sleep(60)


if __name__ == "__main__":
    # main()  # Uncomment if you want PR monitoring

    while True:
        user_input = input("Enter a command for the agent (or 'exit' to quit): ")
        if user_input.lower() == 'exit':
            break
        autonomous_agent_loop(user_input)