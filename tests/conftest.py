import os

from aiohttp import web
from aiohttp_xmlrpc.client import ServerProxy
import aiohttp_jinja2
import jinja2

import pytest
from tortoise.contrib.test import finalizer, initializer

from denyhosts_server import config
from denyhosts_server import main
from denyhosts_server import views
from denyhosts_server import stats

pytest_plugins = (
    'aiohttp.pytest_plugin',
)

@pytest.fixture(scope="function", autouse=True)
def initialize_tests(loop, request):
    db_url = os.environ.get("TORTOISE_TEST_DB", "sqlite://:memory:")
    print(f"db_url: {db_url}")
    initializer(["denyhosts_server.models"], db_url=db_url, app_label="models",
            loop=loop)

    configfile = os.path.join(os.path.dirname(__file__), "test.conf")

    config.read_config(configfile)

    request.addfinalizer(finalizer)

@pytest.fixture
async def rpc_client(aiohttp_client):
    app = web.Application()
    app.router.add_route('*', '/', views.AppView)

    test_client = await aiohttp_client(app)

    client = ServerProxy('', test_client)
    print(f"client: {client} ({type(client)}")

    return client

@pytest.fixture
async def web_client(aiohttp_client):
    app = web.Application()
    app.router.add_route('GET', '/', views.stats_view)
    aiohttp_jinja2.setup(app,
        loader=jinja2.FileSystemLoader(config.template_dir),
        filters={
            'datetime': stats.format_datetime
            })

    client = await aiohttp_client(app)

    return client

