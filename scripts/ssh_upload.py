"""Upload file len may Linux qua SFTP (paramiko).

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\ssh_upload.py <local> <remote>
"""
from __future__ import annotations

import os
import sys

import paramiko

HOST = os.getenv("SF_SSH_HOST", "192.168.179.176")
USER = os.getenv("SF_SSH_USER", "dev")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    local, remote = sys.argv[1], sys.argv[2]
    pwd = os.getenv("SF_SSH_PASSWORD")
    if not pwd:
        import getpass
        pwd = getpass.getpass(f"password for {USER}@{HOST}: ")

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=pwd, timeout=20,
                banner_timeout=20, auth_timeout=20,
                look_for_keys=False, allow_agent=False)
    try:
        sftp = cli.open_sftp()
        try:
            sftp.put(local, remote)
            size = sftp.stat(remote).st_size
            print(f"OK  {local} -> {remote}  ({size} bytes)")
        finally:
            sftp.close()
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
