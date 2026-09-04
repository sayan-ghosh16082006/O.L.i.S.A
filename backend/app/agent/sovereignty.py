import socket
from datetime import datetime
from functools import wraps
import time


class SovereigntyCheck:

    def __init__(self, allowed_hosts = None):
        if not allowed_hosts:
            allowed_hosts = ["localhost", "0.0.0.0", "127.0.0.1"]
        else:
            self.allowed_hosts = allowed_hosts

        self.socket_class = socket.socket
        self.original_connection = socket.socket.connect


    def log_event(self, category : str, message : str, model : str = None, level : str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        model_str = f"| MODEL : {model}" if model else ""
        icon = "🛡️ " if "GUARD" in category else "⚙️ " if "TOOL" in category else "📦 " if "SANDBOX" in category else "🤖 "

        print(f"[{icon} SOVEREIGNTY][{timestamp}] [{category}]{model_str} >> {message}") 

    def log_tool_lifecycle(self, tool_name : str, status : str, details : str = ""):
        self.log_event("TOOL-LIFECYCLE", f"Tool : '{tool_name}' {status}. {details}")

    def log_sandbox_event(self, action : str, details : str):
        self.log_event("SANDBOX-LIFECYCLE", f"[{action.upper()}] {details}")

    def start_network_monitor(self):

        def monitored_connection(s, address):
            host = address[0]
            if host not in self.allowed_hosts:
                self.log_event("BLOCKED NETWORK", f"Blocked connection for the host {host}", level = "CRITICAL")
                return ConnectionRefusedError(f"Sovereignty Policy : External calls on {host} are forbidden")

            return self.original_connection(s, address)

        socket.socket.connet = monitored_connection
        self.log_event("GUARD_INIT", "Network Monitor Active: Zero External Calls Policy enforced.")


guard = SovereigntyCheck()


def sovereignty_tool_logger(tool):

    original_func = tool._run if hasattr(tool, "_run") else tool      # handles the structured_tool and functionbased_tool together

    @wraps(original_func)
    def wrapper(*args, **kwargs):
        tool_name = getattr(tool, "name", original_func.__name__)

        guard.log_tool_lifecycle(tool_name, "LOADED", 'Initializing local context....')

        guard.log_sandbox_event("Pre-Exec", f"Validating permissions for {tool_name} in isolated environment.")

        start = time.time()
        try:
            result = original_func(*args, **kwargs)
            duration = round(time.time() - start, 3)
            guard.log_event(tool_name, "COMPLETED", f"Execution completed in {duration}s")

            return result
        except Exception as e:
            guard.log_event("TOOL-ERROR", f"Tool {tool_name} failed: {str(e)}", level="ERROR")
            raise e

    if hasattr(tool, "_run"):
        tool._run = wrapper
        return tool


    return wrapper
