import json
import ollama
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from tools import run_terminal_command, write_local_file

class SquadState(TypedDict):
    messages: Annotated[list, add_messages]
    code_diff: str
    security_report: str
    performance_report: str
    janitor_report: str
    is_ready_to_push: bool

def security_agent(state: SquadState):
    print("\n[Security Expert] Scanning for vulnerabilities...")
    prompt = (
        f"You are an expert Security Researcher. Analyze this code diff for vulnerabilities:\n\n"
        f"{state['code_diff']}\n\nProvide a clear, concise summary of your security findings."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"security_report": response['message']['content']}

def performance_agent(state: SquadState):
    print("[Performance Expert] Evaluating efficiency...")
    prompt = (
        f"You are a performance optimization engineer. Analyze this code diff for bottlenecks:\n\n"
        f"{state['code_diff']}\n\nProvide a clear, concise summary of your performance findings."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"performance_report": response['message']['content']}

def janitor_agent(state: SquadState):
    print("[Janitor Expert] Checking code style and debt...")
    prompt = (
        f"You are a Tech Debt Janitor. Analyze this code diff for structural irregularities:\n\n"
        f"{state['code_diff']}\n\nProvide a clear, concise summary of structural/formatting issues."
    )
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[{'role': 'user', 'content': prompt}])
    return {"janitor_report": response['message']['content']}

def lead_engineer_agent(state: SquadState):
    print("\n[Lead Engineer] Aggregating squad findings...")
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
    
    try:
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        data = json.loads(content[start_idx:end_idx])
        is_approved = data.get("status") == "APPROVED"
    except Exception:
        print("[Warning] Lead Engineer output formatting issue. Parsing text directly...")
        is_approved = "APPROVED" in content.upper() and "CRITICAL" not in content.upper()

    print(f"[Decision] Lead Engineer status: {'APPROVED' if is_approved else 'CRITICAL (Requires Fixes)'}")
    return {"is_ready_to_push": is_approved}

def fixer_agent(state: SquadState):
    print("\n[Fixer Agent] Resolving issues identified by the squad...")
    system_instruction = (
        "You are an autonomous repair engineer on a WINDOWS machine using PowerShell. "
        "Your mission is to fix files in the directory based on review complaints.\n"
        "Rules:\n"
        "1. To change code or rewrite a file completely, use 'write_local_file'.\n"
        "2. To run scripts or check syntax, use 'run_terminal_command' (e.g., 'python script.py').\n"
        "Do not write conversational commentary when executing tools."
    )
    tools_config = [
        {
            'type': 'function',
            'function': {
                'name': 'run_terminal_command',
                'description': 'Run syntax tests or execution checks via PowerShell.',
                'parameters': {
                    'type': 'object',
                    'properties': {'command': {'type': 'string'}},
                    'required': ['command']
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'write_local_file',
                'description': 'Writes clean code content directly to a file path.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'filepath': {'type': 'string', 'description': 'Relative file path like .\\math_utils.py'},
                        'content': {'type': 'string', 'description': 'The complete code text to write.'}
                    },
                    'required': ['filepath', 'content']
                }
            }
        }
    ]
    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': f"Fix errors here:\n{state['security_report']}\n{state['performance_report']}"}
    ]
    
    for turn in range(4):
        response = ollama.chat(model='qwen2.5-coder:7b', messages=messages, tools=tools_config)
        msg = response['message']
        messages.append(msg)
        
        tool_calls = msg.get('tool_calls', [])
        if not tool_calls:
            break
            
        for call in tool_calls:
            name = call['function']['name']
            args = call['function']['arguments']
            
            if name == 'write_local_file':
                print(f"   [File Write] Writing to {args['filepath']}")
                obs = write_local_file(args['filepath'], args['content'])
            elif name == 'run_terminal_command':
                print(f"   [Shell Command] Executing -> {args['command']}")
                obs = run_terminal_command(args['command'])
                
            messages.append({'role': 'tool', 'content': obs['output'], 'name': name})
                
    return {"messages": ["Fixer changes applied."]}

def conditional_router(state: SquadState):
    if state["is_ready_to_push"]:
        return "approved_path"
    return "fix_path"

builder = StateGraph(SquadState)
builder.add_node("security_node", security_agent)
builder.add_node("performance_node", performance_agent)
builder.add_node("janitor_node", janitor_agent)
builder.add_node("lead_engineer_node", lead_engineer_agent)
builder.add_node("fixer_node", fixer_agent)

builder.add_edge(START, "security_node")
builder.add_edge(START, "performance_node")
builder.add_edge(START, "janitor_node")

builder.add_edge("security_node", "lead_engineer_node")
builder.add_edge("performance_node", "lead_engineer_node")
builder.add_edge("janitor_node", "lead_engineer_node")

builder.add_conditional_edges(
    "lead_engineer_node",
    conditional_router,
    {
        "approved_path": END,
        "fix_path": "fixer_node"
    }
)
builder.add_edge("fixer_node", "security_node")
squad_app = builder.compile()