import asyncio
import time

import pytest
from aiohttp import web
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist

from denyhosts_server import main
from denyhosts_server import views
from denyhosts_server.models import Cracker

async def test_add(rpc_client):
    host = "69.192.72.150"

    # Host should not be in the database to begin with
    with pytest.raises(DoesNotExist):
        cracker = await Cracker.get(ip_address = host)

    # Execute rpc call to add host
    result = await rpc_client.add_hosts([host])
    assert result == 0

    # host should be in now
    cracker = await Cracker.get(ip_address = host)
    assert cracker.ip_address == host

async def test_add_multiple(rpc_client):
    hosts =[ 
        "69.192.72.150", 
        "69.192.72.151", 
        "69.192.72.152", 
        "69.192.72.153",
        "69.192.72.154", 
        "69.192.72.155", 
        "69.192.72.156"
    ]

    # Hosts should not be in the database to begin with
    for host in hosts:
        with pytest.raises(DoesNotExist):
            print(f"Checking that {host} does not exist yet")
            cracker = await Cracker.get(ip_address = host)

    # Execute rpc call to add hosts
    result = await rpc_client.add_hosts(hosts)
    assert result == 0

    # hosts should be in now
    for host in hosts:
        cracker = await Cracker.get(ip_address = host)
        assert cracker.ip_address == host
        assert cracker.total_reports == 1
        assert cracker.current_reports == 1


async def test_get_new_hosts(rpc_client):
    host = "69.192.72.150"
    now = time.time()

    # Execute rpc call to add host
    await rpc_client.add_hosts([host])
    print(f"now: {now}")
    response = await rpc_client.get_new_hosts(now-10, 1, [], 0)
    print(f"response: {response}")
    hosts = response['hosts']
    assert len(hosts) == 1, "When one report, get_new_hosts with resilience 0 should return one host"

    assert hosts[0] == host, "Expect to report back the host just added"


async def test_add_illegal_hosts(rpc_client):
    for illegal_ip in ["127.0.0.3", "192.168.1.22", "test4.example.org"]:
        with pytest.raises(Exception, match=r'\[104\]'):
            await rpc_client.add_hosts([illegal_ip])

async def test_get_new_hosts_illegal_timestamp(rpc_client):
    with pytest.raises(Exception, match=r'\[102\]'):
        await rpc_client.get_new_hosts("12312iasda", 1, ["69.192.72.150"], 60)

async def test_get_new_hosts_illegal_ip(rpc_client):
    for illegal_ip in ["127.0.0.3", "192.168.1.22", "test4.example.org"]:
        with pytest.raises(Exception, match=r'\[101\]'):
            await rpc_client.get_new_hosts(time.time()-100, 1, [illegal_ip], 60)
