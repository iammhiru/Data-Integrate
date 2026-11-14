"""Chay lenh tren may Linux qua SSH (paramiko) - dung de deploy/verify tu may Windows.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\ssh_exec.py "ls -la"
    .\\.venv\\Scripts\\python.exe scripts\\ssh_exec.py --long "docker compose -f x.yml build"

Password lay tu bien moi truong SF_SSH_PASSWORD (fallback: prompt).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time

import paramiko

HOST = os.getenv("SF_SSH_HOST", "192.168.179.176")
USER = os.getenv("SF_SSH_USER", "dev")
DEFAULT_DIR = os.getenv("SF_SSH_DIR", "/home/dev/smart-factory")


def connect(host: str, user: str, password: str, timeout: int = 20):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(host, username=user, password=password, timeout=timeout,
                banner_timeout=timeout, auth_timeout=timeout,
                look_for_keys=False, allow_agent=False)
    return cli


def run(cli, cmd: str, cwd: str | None = None, timeout: int = 3600,
        stream: bool = False) -> int:
    full = f"cd {cwd} && {cmd}" if cwd else cmd
    print(f"$ {full}", flush=True)
    if not stream:
        _, out, err = cli.exec_command(full, timeout=timeout)
        rc = out.channel.recv_exit_status()
        so = out.read().decode("utf-8", "replace")
        se = err.read().decode("utf-8", "replace")
        if so:
            print(so, end="", flush=True)
        if se:
            print(se, end="", file=sys.stderr, flush=True)
        print(f"[exit={rc}]", flush=True)
        return rc

    # streaming: doc stdout theo dong de theo doi build
    _, out, err = cli.exec_command(full, timeout=timeout)
    chan = out.channel
    chan.settimeout(1.0)
    buf = ""
    while True:
        if chan.recv_ready():
            data = chan.recv(65536).decode("utf-8", "replace")
            buf += data
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                print(line, flush=True)
        elif chan.exit_status_ready() and not chan.recv_ready():
            break
        else:
            time.sleep(0.2)
    if buf:
        print(buf, flush=True)
    rc = chan.recv_exit_status()
    print(f"[exit={rc}]", flush=True)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="+")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--user", default=USER)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--long", action="store_true", help="stream output theo dong")
    args = ap.parse_args()

    pwd = os.getenv("SF_SSH_PASSWORD") or getpass.getpass(f"password for {args.user}@{args.host}: ")
    cmd = " ".join(args.command)

    cli = connect(args.host, args.user, pwd)
    try:
        rc = run(cli, cmd, cwd=args.cwd, timeout=args.timeout, stream=args.long)
    finally:
        cli.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
