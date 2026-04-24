import subprocess

def run_terminal_command(command: str):
    try:
        # Explicitly use PowerShell for Windows compatibility
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            check=False # We want to capture errors, not crash the script
        )
        
        # Combine stdout and stderr so the agent sees the full error trace
        output = result.stdout + result.stderr
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "output": str(e)}