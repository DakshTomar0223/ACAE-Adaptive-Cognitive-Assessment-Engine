import os
import sys
import subprocess
import argparse
import threading
import time

# Enable ANSI colors in Windows terminal
os.system('')

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'

def stream_output(process, prefix):
    """Reads process stdout line-by-line and prints it with a prefix."""
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"{prefix} {line.strip()}")
    process.stdout.close()

def main():
    parser = argparse.ArgumentParser(description="Starts ACAE's Flask API and Next.js frontend together.")
    parser.add_argument("--no-new-windows", action="store_true", help="Run in current window and stream logs inline.")
    parser.add_argument("--skip-install", action="store_true", help="Skip the npm install check in frontend/.")
    args = parser.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root, "frontend")
    backend_dir = os.path.join(root, "backend")
    api_path = os.path.join(backend_dir, "api.py")

    # --- sanity checks -----------------------------------------------------
    if not os.path.exists(api_path):
        print(f"{Colors.RED}api.py not found in {backend_dir} — check your project structure.{Colors.END}", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.isdir(frontend_dir):
        print(f"{Colors.RED}frontend/ not found in {root} — check your project structure.{Colors.END}", file=sys.stderr)
        sys.exit(1)

    node_modules = os.path.join(frontend_dir, "node_modules")
    if not args.skip_install and not os.path.exists(node_modules):
        print(f"{Colors.YELLOW}frontend/node_modules not found — running 'npm install' first (one-time)...{Colors.END}")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True)

    # --- launch --------------------------------------------------------------
    if args.no_new_windows:
        print(f"{Colors.CYAN}Starting backend and frontend as background jobs (this window)...{Colors.END}")
        
        backend_proc = subprocess.Popen(
            [sys.executable, "api.py"], 
            cwd=backend_dir,  # Fixed: Run from the backend directory
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True
        )
        
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"], 
            cwd=frontend_dir, 
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True
        )

        print(f"{Colors.GREEN}Backend  -> http://127.0.0.1:5000{Colors.END}")
        print(f"{Colors.GREEN}Frontend -> http://localhost:3000{Colors.END}")
        print(f"{Colors.YELLOW}Streaming combined output below. Ctrl+C stops watching and ends the servers.{Colors.END}\n")

        # Use threads to read both streams concurrently without blocking
        t_backend = threading.Thread(target=stream_output, args=(backend_proc, "[backend] "))
        t_frontend = threading.Thread(target=stream_output, args=(frontend_proc, "[frontend]"))
        
        t_backend.daemon = True
        t_frontend.daemon = True
        
        t_backend.start()
        t_frontend.start()

        try:
            # Keep main thread alive to catch KeyboardInterrupt
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Shutting down servers...{Colors.END}")
            backend_proc.terminate()
            frontend_proc.terminate()
            print("Done.")

    else:
        print(f"{Colors.CYAN}Starting backend in a new window...{Colors.END}")
        # Fixed: Navigate to backend_dir before running api.py
        backend_cmd = f"Set-Location -LiteralPath '{backend_dir}'; Write-Host 'ACAE backend  ->  http://127.0.0.1:5000' -ForegroundColor Green; {sys.executable} api.py"
        subprocess.Popen(["powershell", "-NoExit", "-Command", backend_cmd])

        print(f"{Colors.CYAN}Starting frontend in a new window...{Colors.END}")
        frontend_cmd = f"Set-Location -LiteralPath '{frontend_dir}'; Write-Host 'ACAE frontend ->  http://localhost:3000' -ForegroundColor Green; npm run dev"
        subprocess.Popen(["powershell", "-NoExit", "-Command", frontend_cmd])

        print(f"\n{Colors.GREEN}Both started in separate windows.{Colors.END}")
        print("Backend:  http://127.0.0.1:5000")
        print("Frontend: http://localhost:3000")
        print("Close a window (or Ctrl+C inside it) to stop that process.")

if __name__ == "__main__":
    main()