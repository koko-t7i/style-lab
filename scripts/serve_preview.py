#!/usr/bin/env python3
"""
Serve a style-lab output directory over HTTP and print the SSH port-forward
command the user pastes locally to view it from their laptop browser.

Usage:
    python3 serve_preview.py <output-dir> [--port PORT] [--host USER@HOST]
    python3 serve_preview.py <output-dir> --kill       # stop the server
    python3 serve_preview.py <output-dir> --no-regen   # don't rebuild index.html

Behavior:
- Regenerates <output-dir>/index.html via generate_index.py (skip with --no-regen)
- Picks a free port starting at 8765 (or honors --port)
- Cleans up any stale server from a prior run on this directory
- Starts `python3 -m http.server` detached in the background, serving the dir
- Writes <output-dir>/.preview-server.pid
- Prints a paste-ready ssh -L command (works in PowerShell, macOS Terminal, Linux)

The HTTP server stays up after this script exits. Stop it with --kill, or by
killing the PID in .preview-server.pid.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATE_INDEX = SCRIPT_DIR / "generate_index.py"
GENERATE_ROOT_INDEX = SCRIPT_DIR / "generate_root_index.py"
PORT_RANGE = (8765, 9000)


def find_free_port(preferred: int | None = None) -> int:
    if preferred is not None:
        if _port_is_free(preferred):
            return preferred
        print(f"  port {preferred} is in use; falling back to auto-pick", file=sys.stderr)
    for p in range(*PORT_RANGE):
        if _port_is_free(p):
            return p
    raise RuntimeError(f"no free port in {PORT_RANGE}")


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def kill_existing(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return
    if pid_alive(pid):
        try:
            os.kill(pid, 15)  # SIGTERM
            for _ in range(20):
                time.sleep(0.1)
                if not pid_alive(pid):
                    break
            else:
                os.kill(pid, 9)  # SIGKILL
        except OSError:
            pass
    pid_file.unlink(missing_ok=True)


def _run(cmd: list[str], label: str) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"warn: {label} failed:\n{res.stderr}", file=sys.stderr)
        return False
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if lines:
        print("  " + lines[0])
    return True


def regenerate_index(output_dir: Path, title: str) -> None:
    """Regenerate the per-batch comparison index for a directory of variants."""
    if not GENERATE_INDEX.exists():
        print(f"warn: {GENERATE_INDEX} missing, skipping index regeneration", file=sys.stderr)
        return
    cmd = ["python3", str(GENERATE_INDEX), str(output_dir)]
    if title:
        cmd += ["--title", title]
    _run(cmd, "generate_index.py")


def regenerate_root_with_batches(output_dir: Path, title: str) -> None:
    """For an output root with state.json: refresh every batch's index, then build the tabbed root."""
    state_path = output_dir / "state.json"
    if not state_path.exists():
        return
    try:
        import json as _json
        state = _json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"warn: state.json unreadable: {e}", file=sys.stderr)
        return
    product_name = state.get("product", {}).get("name") or title or output_dir.name
    for i, batch in enumerate(state.get("batches", [])):
        n = batch.get("n", i + 1)
        batch_dir = output_dir / batch.get("dir", f"batch-{n}")
        if not batch_dir.is_dir():
            print(f"  skip batch {n}: {batch_dir} missing", file=sys.stderr)
            continue
        batch_title = f"{product_name} · batch {n}"
        cmd = ["python3", str(GENERATE_INDEX), str(batch_dir), "--title", batch_title]
        _run(cmd, f"generate_index.py for batch-{n}")
    if GENERATE_ROOT_INDEX.exists():
        cmd = ["python3", str(GENERATE_ROOT_INDEX), str(output_dir)]
        if title:
            cmd += ["--title", title]
        _run(cmd, "generate_root_index.py")


def detect_ssh_host() -> str:
    """Best-effort guess of the host token for the ssh -L command.

    Priority:
      1. $STYLE_LAB_SSH_HOST                        (e.g. "dev-koko" — an ssh-config alias)
      2. ~/.style-lab-host                          (single-line file with the same)
      3. $SSH_CONNECTION-derived "<user>@<server-ip>"
      4. "<user>@<hostname>"
    """
    explicit = os.environ.get("STYLE_LAB_SSH_HOST", "").strip()
    if explicit:
        return explicit

    host_file = Path.home() / ".style-lab-host"
    if host_file.exists():
        try:
            saved = host_file.read_text().strip().splitlines()[0].strip()
            if saved:
                return saved
        except OSError:
            pass

    user = os.environ.get("USER") or os.environ.get("USERNAME") or "<user>"
    ssh_conn = os.environ.get("SSH_CONNECTION", "")
    server_ip = ""
    if ssh_conn:
        parts = ssh_conn.split()
        if len(parts) >= 3:
            server_ip = parts[2]
    host = server_ip or socket.gethostname() or "<host>"
    return f"{user}@{host}"


def start_server(output_dir: Path, port: int, pid_file: Path) -> int:
    log_file = output_dir / ".preview-server.log"
    log = open(log_file, "ab")
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "0.0.0.0"],
        cwd=str(output_dir),
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_file.write_text(str(proc.pid))
    # wait a moment to confirm it didn't immediately die
    time.sleep(0.4)
    if proc.poll() is not None:
        raise RuntimeError(f"server exited immediately; see {log_file}")
    return proc.pid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", help="Directory containing variant subdirectories + index.html")
    parser.add_argument("--port", type=int, help="Preferred port (default: auto-pick from 8765+)")
    parser.add_argument("--host", help="Override the user@host shown in the ssh command")
    parser.add_argument("--title", default="", help="Title for the regenerated comparison index")
    parser.add_argument("--no-regen", action="store_true", help="Don't regenerate index.html before serving")
    parser.add_argument("--kill", action="store_true", help="Kill the server for this directory and exit")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        print(f"error: {output_dir} is not a directory", file=sys.stderr)
        return 1

    pid_file = output_dir / ".preview-server.pid"

    if args.kill:
        kill_existing(pid_file)
        print(f"stopped any preview server for {output_dir}")
        return 0

    title = args.title or output_dir.name.replace("-", " ").title()
    has_state = (output_dir / "state.json").exists()

    if not args.no_regen:
        if has_state:
            # Multi-batch root: refresh every batch's index AND build the tabbed root.
            regenerate_root_with_batches(output_dir, title)
        else:
            # Single batch / flat dir: standard per-directory comparison page.
            regenerate_index(output_dir, title)

    if not (output_dir / "index.html").exists():
        print(f"error: no index.html in {output_dir} — did generate_index.py fail?", file=sys.stderr)
        return 1

    kill_existing(pid_file)
    port = find_free_port(args.port)
    pid = start_server(output_dir, port, pid_file)
    host = args.host or detect_ssh_host()

    bar = "─" * 64
    print()
    print(bar)
    print(f"  style-lab preview server up — pid {pid}, port {port}")
    print(bar)
    print()
    print(f"  Serving:  {output_dir}")
    print()
    print(f"  ▶ Paste this in your local PowerShell / Terminal:")
    print()
    print(f"      ssh -N -L {port}:localhost:{port} {host}")
    print()
    print(f"      (The -N flag means: just open the tunnel, do NOT log into the")
    print(f"       server. The window will appear to hang with no shell prompt —")
    print(f"       that is correct. Press Ctrl+C in that window to close the tunnel.)")
    print()
    print(f"  ▶ Then open in your browser:")
    print()
    print(f"      http://localhost:{port}/index.html")
    print()
    print(f"  ▶ When you're done previewing:")
    print()
    print(f"      · Ctrl+C in the ssh window to drop the tunnel")
    print(f"      · Stop the remote server: python3 {Path(__file__).name} {output_dir} --kill")
    print()
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
