from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages
import ollama

# This is the "Shared Memory" for your squad thats why we using typeddict,
# it defines the structure of the state that all agents will read from
# and write to.
class SquadState(TypedDict):
    # 'add_messages' ensures new reports are appended to the history
    messages: Annotated[list, add_messages]
    code_diff: str
    security_report: str
    performance_report: str
    janitor_report: str
    is_code_safe: bool
    is_ready_to_push: bool

# Security Agent: Focuses on identifying vulnerabilities, secrets, and compliance issues in the code.
def security_agent(state: SquadState):
    print(" Security Researcher is analyzing...")
    prompt = (
        f"Analyze this code for security vulnerabilities (OWASP Top 10, secrets):\n\n"
        f"{state['code_diff']}\n\n"
        "Provide a concise report. If safe, start with 'SAFE'."
    )
    # Using the local Qwen brain
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    report = response['message']['content']
    
    # Update state: Append to messages and update security_report
    return {
        "messages": [f"Security Report: {report}"],
        "security_report": report,
        "is_code_safe": "SAFE" in report.upper()
    }

def performance_agent(state: SquadState):
    print(" Performance Engineer is analyzing...")
    prompt = (
        f"Analyze this code for performance bottlenecks (O(N^2) loops, database N+1):\n\n"
        f"{state['code_diff']}"
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"performance_report": response['message']['content']}


def janitor_agent(state: SquadState):
    print(" The Janitor is checking tech debt...")
    prompt = (
        f"Check this code for naming conventions and architectural debt:\n\n"
        f"{state['code_diff']}"
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"janitor_report": response['message']['content']}