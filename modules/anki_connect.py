"""
AnkiConnect Client Module
-------------------------
REST client for AnkiConnect (Anki addon #2055492159).
Communicates with Anki over its localhost HTTP API to directly
create decks, store media, and add notes.
"""

import base64
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ANKI_CONNECT_VERSION = 6


class AnkiConnectError(Exception):
    """Raised when AnkiConnect is unreachable or returns an error."""


class AnkiConnectClient:
    """Client for AnkiConnect REST API."""

    def __init__(self, url: str = "http://127.0.0.1:8765"):
        self.url = url

    async def _request(self, action: str, params: dict | None = None) -> any:
        """Send a request to AnkiConnect and return the result.

        Args:
            action: The AnkiConnect action name
            params: Optional parameters for the action

        Returns:
            The result field from AnkiConnect's response

        Raises:
            AnkiConnectError: If AnkiConnect is unreachable or returns an error
        """
        payload = {"action": action, "version": ANKI_CONNECT_VERSION}
        if params:
            payload["params"] = params

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0)
            ) as client:
                response = await client.post(self.url, json=payload)
                response.raise_for_status()
        except httpx.ConnectError:
            raise AnkiConnectError(
                "Cannot connect to AnkiConnect. Is Anki running with AnkiConnect installed?"
            )
        except httpx.TimeoutException:
            raise AnkiConnectError("AnkiConnect request timed out")
        except httpx.HTTPStatusError as e:
            raise AnkiConnectError(f"AnkiConnect HTTP error: {e.response.status_code}")

        data = response.json()
        if data.get("error"):
            raise AnkiConnectError(f"AnkiConnect error: {data['error']}")

        return data.get("result")

    async def is_available(self) -> tuple[bool, int | None]:
        """Check if AnkiConnect is reachable.

        Returns:
            Tuple of (available, version)
        """
        try:
            version = await self._request("version")
            return True, version
        except AnkiConnectError:
            return False, None

    async def get_decks(self) -> list[str]:
        """Get all deck names."""
        return await self._request("deckNames")

    async def create_deck(self, deck_name: str) -> int:
        """Create a deck (idempotent — won't overwrite existing).

        Returns:
            Deck ID
        """
        return await self._request("createDeck", {"deck": deck_name})

    async def store_media_file(self, filename: str, data_b64: str) -> str:
        """Store a media file in Anki's collection.media folder.

        Args:
            filename: Target filename in collection.media
            data_b64: Base64-encoded file content

        Returns:
            The stored filename
        """
        return await self._request(
            "storeMediaFile",
            {"filename": filename, "data": data_b64, "deleteExisting": True},
        )

    async def add_notes(self, notes: list[dict]) -> list[int | None]:
        """Add multiple notes to Anki.

        Each note dict should have: deckName, modelName, fields, tags.

        Args:
            notes: List of note dicts in AnkiConnect format

        Returns:
            List of note IDs (None for failed notes)
        """
        return await self._request("addNotes", {"notes": notes})

    async def store_media_from_path(self, filename: str, file_path: Path) -> str:
        """Read a file from disk and store it in Anki's media folder.

        Args:
            filename: Target filename in collection.media
            file_path: Path to the source file on disk

        Returns:
            The stored filename
        """
        data = file_path.read_bytes()
        data_b64 = base64.b64encode(data).decode("ascii")
        result = await self.store_media_file(filename, data_b64)
        logger.debug(f"Stored media file: {filename}")
        return result
