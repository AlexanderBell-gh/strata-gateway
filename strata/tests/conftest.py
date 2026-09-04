import os

os.environ.setdefault("STRATA_UPSTREAM_API_KEY", "sk-test-dummy")

import pytest
from httpx import ASGITransport, AsyncClient

from strata.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
