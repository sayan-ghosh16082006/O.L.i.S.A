import docker
import time
import json
import hashlib
from pathlib import Path
from app.agent.sovereignty import guard



class SovereignSandbox:

    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None

        cwd = Path().cwd()
        self.project_workspace_path = cwd / "project_workspace"
        self.workspace_root = self.project_workspace_path / "sandbox_internal"
        self.image = "sovereign-sandbox:latest"
        self.audit_log_path = self.workspace_root / "sovereignty_audit.log"

    def log_audit(self, job_id, code, status, duration):
        entry = {
            "timestamp" : time.time(),
            "job_id" : job_id,
            "code_hash" : hashlib.sha256(code.encode()).hexdigest(),
            "network_status" : "DISABLED",
            "status" : status,
            "duration_seconds" : round(duration, 3)
        }

        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def run_code(self, code : str, timeout : int = 30):

        self.project_workspace_path.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        job_id = f"job_{int(time.time())}"
        job_dir = self.workspace_root / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"

        input_dir.mkdir(parents = True)
        output_dir.mkdir(parents = True)

        (input_dir / "main.py").write_text(code, encoding="utf-8")

        guard.log_sandbox_event("PREPARE", f"Creating isolated workspace for Job: {job_id}")
        container = None
        start_time = time.time()
        status = "PENDING" 

        try:

            guard.log_sandbox_event("INIT", f"Spawning container from image: {self.image}")
            guard.log_sandbox_event("INJECT", "Mounting read-only code volume.")
            container = self.client.containers.run(
                image = self.image,
                command = ["python", "/workspace/input/main.py"],
                volumes = {
                    str(input_dir) : {"bind" : "/workspace/input", "mode" : "ro"},
                    str(output_dir) : {"bind" : "/workspace/output", "mode" : "rw"},
                },
                network_disabled=True,
                mem_limit="512m",
                nano_cpus=1000000000,
                cap_drop = ["ALL"],
                security_opt=["no-new-privileges"],
                user="sandboxuser",
                working_dir="/workspace",
                detach = True
            )

            guard.log_sandbox_event("EXECUTE", "Starting code verification loop...")

            try:
                res = container.wait(timeout = timeout)
                exit_code = res["StatusCode"]
            except:
                container.kill()
                exit_code = -1
                status = "TIMEOUT"

            stdout = container.logs(stdout = True, stderr = False).decode()
            stderr = container.logs(stdout = False, stderr = True).decode()

            if status != "TIMEOUT":
                status = "SUCCESS" if exit_code == 0 else "FAILED"

            duration = time.time() - start_time
            self.log_audit(job_id, code, status, duration)

            generated_files = [f.name for f in output_dir.iterdir() if f.is_file()]

            return {
                "status" : status,
                "stdout" : stdout,
                "stderr" : stderr,
                "files" : generated_files,
                "job_dir" : str(job_dir)
            }

        finally:
            if container:
                guard.log_sandbox_event("CLEANUP", "Destroying container and wiping temporary memory.")
                container.remove(force = True)


sandbox = SovereignSandbox()