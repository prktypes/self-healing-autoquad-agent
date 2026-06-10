import subprocess
import os

def run_terminal_command(command: str):
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            check=False
        )
        output = result.stdout + result.stderr
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "output": str(e)}

def write_local_file(filepath: str, content: str):
    """Safely writes content to a file without PowerShell quoting issues."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "output": f"Successfully updated file: {filepath}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}