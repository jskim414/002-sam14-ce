"""Serve synthetic data for DOM tests; CE_TEST_DATABASE opts into real data."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support import make_fixture, REAL_DATABASE
from web.server import create_server

with tempfile.TemporaryDirectory() as temp:
    database = REAL_DATABASE or make_fixture(Path(temp)/'fixture.db')
    server = create_server('127.0.0.1',0,database)
    print(server.server_port,flush=True)
    try:server.serve_forever()
    finally:server.server_close()
