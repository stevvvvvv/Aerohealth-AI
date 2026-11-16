import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from aerohealth.api.main import app
    from aerohealth.api.seed import seed

    seed("FD001", limit=3, reset=True)
    with TestClient(app) as c:
        yield c
