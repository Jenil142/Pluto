import subprocess
import shlex
from google.genai import types
from ..security.permissions import check_command_permission, CONFIRM, DENY
from ..security.confirmation import request_confirmation

def execute_terminal_command(command):

    if not command.strip():
            return {
                "command": command,
                "stdout": "",
                "stderr": "No command provided",
                "return_code": 1
                }

    permission = check_command_permission(command)
    if permission == DENY:
        return {
            "command": command,
            "stdout": "",
            "stderr": "Command denied by security policy",
            "return_code": 1
        }

    elif permission == CONFIRM:
         
         approve = request_confirmation(command)

         if not approve:
            return{
            "command": command,
            "stdout":"",
            "stderr": "Jenil's confirmation is required but denied",
            "return_code": 1
            }
    

    try:
        arguments = shlex.split(command)

        result = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout = 30
        )

        stdout = result.stdout
        if len(stdout) > 10000:
            stdout = stdout[:10000] + "\n...[OUTPUT TRUNCATED]..."

        stderr = result.stderr
        if len(stderr) > 10000:
            stderr = stderr[:10000] + "\n...[OUTPUT TRUNCATED]..."

        return {
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "stdout": "",
            "stderr": "Command timed out after 30 seconds",
            "return_code": 124  
        }

    except FileNotFoundError:
        return {
            "command": command,
            "stdout": "",
            "stderr": "Command not found",
            "return_code": 127  
        }
    
    except PermissionError:
        return {
            "command": command,
            "stdout": "",
            "stderr": "Permission denied",
            "return_code": 126  
        }
    
    except ValueError as e:
        return {
            "command": command,
            "stdout": "",
            "stderr": f"Invalid command syntax: {e}",
            "return_code": 1  
        }

    except Exception as e:
        return {
            "command": command,
            "stdout": f"Error: {e}",
            "stderr": "",
            "return_code": 1  
        }
    
    



if __name__ == "__main__":  
    command = input("Enter command: ")
    result = execute_terminal_command(command)
    print(result)

terminal_function_declaration = types.FunctionDeclaration(
    name="execute_terminal_command",
    description="Execute a Linux terminal command.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "command": types.Schema(
                type="STRING",
                description="The Linux terminal command to execute."
            )
        },
        required=["command"]
    )
)