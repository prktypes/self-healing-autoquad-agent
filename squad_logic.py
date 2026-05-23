import json
import ollama
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from tools import run_terminal_command

# ==========================================
#  1. SHARED MEMORY STATE
# ==========================================
class SquadState(TypedDict):
    """The universal state object accessed and altered by all agents."""
    messages: Annotated[list, add_messages]
    code_diff: str
    security_report: str
    performance_report: str
    janitor_report: str
    is_ready_to_push: bool

# ==========================================
# 🛡️ 2. PARALLEL EXPERT AGENTS (FAN-OUT)
# ==========================================
def security_agent(state: SquadState):
    print("\n  [Security Expert] Scanning for vulnerabilities...")
    prompt = (
        f"You are an expert Security Researcher. Analyze this code diff for vulnerabilities "
        f"(e.g., hardcoded secrets, injection flaws, OWASP issues):\n\n{state['code_diff']}\n\n"
        "Provide a clear, concise summary of your security findings."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"security_report": response['message']['content']}

def performance_agent(state: SquadState):
    print(" [Performance Expert] Evaluating efficiency...")
    prompt = (
        f"You are a performance optimization engineer. Analyze this code diff for bottlenecks "
        f"(e.g., inefficient loops, nested database queries, memory leaks):\n\n{state['code_diff']}\n\n"
        "Provide a clear, concise summary of your performance findings."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"performance_report": response['message']['content']}

def janitor_agent(state: SquadState):
    print(" [Janitor Expert] Checking code style and debt...")
    prompt = (
        f"You are a Tech Debt Janitor. Analyze this code diff for structural irregularities, "
        f"anti-patterns, and code style issues:\n\n{state['code_diff']}\n\n"
        "Provide a clear, concise summary of structural/formatting issues."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"janitor_report": response['message']['content']}

# ==========================================
#  3. THE AGGREGATOR (FAN-IN)
# ==========================================
def lead_engineer_agent(state: SquadState):
    print("\n👨‍💼 [Lead Engineer] Aggregating squad findings...")
    
    reports = (
        f"--- SECURITY REPORT ---\n{state['security_report']}\n\n"
        f"--- PERFORMANCE REPORT ---\n{state['performance_report']}\n\n"
        f"--- TECH DEBT REPORT ---\n{state['janitor_report']}\n"
    )
    
    prompt = (
        f"You are the Lead Software Engineer. Review these specialized reports for a proposed code change:\n\n"
        f"{reports}\n\n"
        "Are there any CRITICAL defects, security flaws, or bugs that must be corrected before merge?\n"
        "Respond EXACTLY in this JSON format to issue your engineering decision:\n"
        '{"status": "CRITICAL", "reason": "Brief explanation of major bugs"}\n'
        'or\n'
        '{"status": "APPROVED", "reason": "Code looks production ready"}'
    )
    
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    content = response['message']['content']
    
    # Robust cleanup to capture JSON strings from local model outputs
    try:
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        data = json.loads(content[start_idx:end_idx])
        is_approved = data.get("status") == "APPROVED"
    except Exception:
        # Fallback security check if JSON decoding stumbles
        print("⚠️  Lead Engineer output formatting issue. Parsing text content directly...")
        is_approved = "APPROVED" in content.upper() and "CRITICAL" not in content.upper()

    print(f" [Decision] Lead Engineer status: {'APPROVED' if is_approved else 'CRITICAL (Requires Fixes)'}")
    return {"is_ready_to_push": is_approved, "messages": [f"Lead decision evaluation finalized."]}

# ==========================================
#  4. THE SELF-HEALING FIXER (THE REPAIR EDGE)
# ==========================================
def fixer_agent(state: SquadState):
    print("\n [Fixer Agent] Resolving issues identified by the squad...")
    
    system_instruction = (
        "You are an autonomous repair engineer operating on a WINDOWS machine using PowerShell. "
        "Your mission is to execute local commands to resolve file bugs. You have access to a tool "
        "called 'run_terminal_command' to run shell operations. Execute file fixes directly, "
        "and complete your task when corrections are verified."
    )
    
    context_complaints = (
        f"Security Feedback: {state['security_report']}\n"
        f"Performance Feedback: {state['performance_report']}\n"
        f"Janitor Feedback: {state['janitor_report']}\n"
    )
    
    prompt = (
        f"Correct any critical flaws across code files in the directory based on this feedback:\n"
        f"{context_complaints}\n"
        "Use the terminal function tool to make changes or test scripts as needed. Execute commands sequentially."
    )
    
    # Format the function definitions to instruct Ollama about terminal access
    tools_config = [{
        'type': 'function',
        'function': {
            'name': 'run_terminal_command',
            'description': 'Executes a PowerShell command locally on Windows to edit or check code files.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': 'The PowerShell expression to run.'}
                },
                'required': ['command']
            }
        }
    }]
    
    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': prompt}
    ]
    
    # Allow the agent up to 3 diagnostic script execution loops
    for turn in range(3):
        response = ollama.chat(model='qwen2.5-coder:7b', messages=messages, tools=tools_config)
        msg = response['message']
        messages.append(msg)
        
        tool_calls = msg.get('tool_calls', [])
        
        # Parse text output if model generates a raw string representation of JSON
        if not tool_calls and '{"name":' in (msg.get('content') or ''):
            try:
                s = msg['content'].find('{')
                e = msg['content'].rfind('}') + 1
                tool_calls = [{'function': json.loads(msg['content'][s:e])}]
            except Exception:
                pass
                
        if not tool_calls:
            break
            
        for call in tool_calls:
            if call['function']['name'] == 'run_terminal_command':
                cmd = call['function']['arguments']['command']
                print(f"     Fixer Action: Executing -> {cmd}")
                observation = run_terminal_command(cmd)
                print(f"    Result: {observation['output'].strip()}")
                
                messages.append({
                    'role': 'tool',
                    'content': observation['output'],
                    'name': 'run_terminal_command'
                })
                
    return {"messages": ["Fixer completed an automation turn."]}

# ==========================================
#  5. CONDITIONAL ROUTING MECHANICS
# ==========================================
def conditional_router(state: SquadState):
    """Evaluates state flags to select the next processing path."""
    if state["is_ready_to_push"]:
        return "approved_path"
    return "fix_path"

# ==========================================
# 🕸️ 6. LANGGRAPH ORCHESTRATION COMPILATION
# ==========================================
builder = StateGraph(SquadState)

# Step A: Define Nodes
builder.add_node("security_node", security_agent)
builder.add_node("performance_node", performance_agent)
builder.add_node("janitor_node", janitor_agent)
builder.add_node("lead_engineer_node", lead_engineer_agent)
builder.add_node("fixer_node", fixer_agent)

# Step B: Establish Fan-Out
builder.add_edge(START, "security_node")
builder.add_edge(START, "performance_node")
builder.add_edge(START, "janitor_node")

# Step C: Establish Fan-In
builder.add_edge("security_node", "lead_engineer_node")
builder.add_edge("performance_node", "lead_engineer_node")
builder.add_edge("janitor_node", "lead_engineer_node")

# Step D: Apply Conditional Router Loop
builder.add_conditional_edges(
    "lead_engineer_node",
    conditional_router,
    {
        "approved_path": END,
        "fix_path": "fixer_node"
    }
)

# Step E: Re-Route Fixer modifications back into the Experts for evaluation
builder.add_edge("fixer_node", "security_node")

# Compile into an executable app instance
squad_app = builder.compile()