"""
Standalone server entry point for Render.com deployment.
Run locally:  python server_main.py
On Render:    automatically started via render.yaml
"""
import os
import asyncio
import logging
import websockets

# Make sure app package is importable
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.backend.game_state import Room, Player, Chain, ChainEntry, GamePhase
from app.backend import messages as msg
from app.backend.server import GameServer

logging.basicConfig(
    level=logging.INFO,
    format="[SERVER] %(message)s"
)
log = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8765))   # Render injects $PORT automatically


async def main():
    server = GameServer()
    log.info(f"Starting Garlic Phone server on {HOST}:{PORT}")
    async with websockets.serve(server.handle_connection, HOST, PORT):
        log.info(f"Server listening on port {PORT}")
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())