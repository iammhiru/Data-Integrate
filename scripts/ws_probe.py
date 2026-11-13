"""Kiem tra WebSocket /state-api/ws/machines qua proxy cua Vite (127.0.0.1:5173)."""
import asyncio
import json
import sys

import websockets

URL = "ws://127.0.0.1:5173/state-api/ws/machines"


async def main() -> None:
    async with websockets.connect(URL, open_timeout=15, max_size=8 * 1024 * 1024) as ws:
        print(f"CONNECTED {URL}")
        for i in range(3):
            raw = await asyncio.wait_for(ws.recv(), timeout=25)
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "snapshot":
                machines = msg.get("machines") or []
                print(f"  #{i} type=snapshot ready={msg.get('ready')} machines={len(machines)}")
                for m in machines[:3]:
                    print(f"        {m.get('machineId')} state={m.get('state')} tags={m.get('tagCount')}")
                total_tags = sum(m.get("tagCount", 0) for m in machines)
                print(f"        TOTAL tags={total_tags}")
            elif t == "patch":
                machines = msg.get("machines") or []
                print(f"  #{i} type=patch machines={len(machines)}")
                for m in machines[:2]:
                    tags = m.get("tags") or {}
                    print(f"        {m.get('machineId')} changed_tags={list(tags)[:5]}")
            else:
                print(f"  #{i} type={t}")
        print("WS OK")


asyncio.run(main())
