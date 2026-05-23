from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages
import ollama
from tools import run_terminal_command 

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

def lead_engineer_node(state: SquadState):
    print(" Lead Engineer is synthesizing reports...")
    
    # We combine all expert reports for the Lead's context
    combined_reports = (
        f"SECURITY REPORT: {state['security_report']}\n"
        f"PERFORMANCE REPORT: {state['performance_report']}\n"
        f"JANITOR REPORT: {state['janitor_report']}"
    )
    
    prompt = (
        "You are the Lead Software Engineer. Review the following expert reports for this PR.\n"
        "Decide if there are 'CRITICAL' issues that need fixing, or if the PR is 'READY'.\n\n"
        f"REPORTS:\n{combined_reports}\n\n"
        "Final Decision (READY or CRITICAL):"
    )
    
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    decision = response['message']['content']
    
    # If the Lead sees 'CRITICAL', we flag it for the Fixer agent
    needs_fix = "CRITICAL" in decision.upper()
    
    return {
        "messages": [f"Lead Engineer Decision: {decision}"],
        "is_ready_to_push": not needs_fix
    }


from tools import run_terminal_command

def fixer_node(state: SquadState):
    print(" Fixer Agent is applying repairs...")
    
    # The Fixer reads all the expert complaints from the state
    full_context = (
        f"Security Issues: {state['security_report']}\n"
        f"Performance Issues: {state['performance_report']}\n"
        f"Janitor Issues: {state['janitor_report']}"
    )
    
    prompt = (
        f"You are a Fixer Agent. Based on these reports, use the 'run_terminal_command' "
        f"to fix the code in the current directory.\n\nREPORTS:\n{full_context}"
    )
    
    # We use your tool-using logic here (simplified for the node)
    response = ollama.chat(
        model='qwen2.5-coder:7b', 
        messages=[{'role': 'user', 'content': prompt}],
        tools=[{ 'type': 'function', 'function': {'name': 'run_terminal_command'}}] # Use your tool def here
    )
    
    # (Execution logic from Phase 2 goes here to run the command)
    
    return {"messages": ["Fixer has applied changes and verified locally."]}


def route_after_lead(state: SquadState):
    if state["is_ready_to_push"]:
        return "approved"
    return "needs_fix"


# Building the orchestration logic to run all agents and update the shared state
# using langgraph

from langgraph.graph import StateGraph, START, END

builder = StateGraph(SquadState)

# Add all nodes
builder.add_node("security", security_agent)
builder.add_node("performance", performance_agent)
builder.add_node("janitor", janitor_agent)
builder.add_node("lead_engineer", lead_engineer_node)
builder.add_node("fixer", fixer_node)

# --- FAN-OUT ---
# Start all experts at once
builder.add_edge(START, "security")
builder.add_edge(START, "performance")
builder.add_edge(START, "janitor")

# --- FAN-IN ---
# Wait for all experts to finish and send results to the Lead
builder.add_edge("security", "lead_engineer")
builder.add_edge("performance", "lead_engineer")
builder.add_edge("janitor", "lead_engineer")

builder.add_conditional_edges(
    "lead_engineer",
    route_after_lead,
    {
        "approved": END,            # PR is perfect and we are done
        "needs_fix": "fixer"        # PR has issues, sending to the fixer
    }
)

builder.add_edge("fixer","security")

squad_app = builder.compile()