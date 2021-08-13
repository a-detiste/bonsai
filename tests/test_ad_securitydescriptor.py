import os
import sys

import pytest
from bonsai.active_directory.acl import ACL
from bonsai.active_directory.sid import SID
from conftest import get_config

from bonsai import LDAPClient
from bonsai.active_directory import SecurityDescriptor


@pytest.fixture
def client():
    """ Create a client with authentication settings. """
    cfg = get_config()
    url = "ldap://{host}:{port}".format(
        host=cfg["SERVER"]["hostname"], port=cfg["SERVER"]["port"],
    )
    client = LDAPClient(url)
    client.set_credentials(
        "SIMPLE", user=cfg["SIMPLEAUTH"]["user"], password=cfg["SIMPLEAUTH"]["password"]
    )
    return client


def test_from_binary():
    """ Test from_binary method. """
    with pytest.raises(TypeError):
        _ = SecurityDescriptor.from_binary(0)
    with pytest.raises(TypeError):
        _ = SecurityDescriptor.from_binary("INVALID")
    with pytest.raises(ValueError):
        _ = SecurityDescriptor.from_binary(b"\x05\nH\x00\x07\x00")
    curdir = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(curdir, "testenv", "sd-sample0.bin"), "rb") as data:
        input_data = data.read()
        sec_desc = SecurityDescriptor.from_binary(input_data)
        assert sec_desc.revision == 1
        assert sec_desc.group_sid == "S-1-5-21-3526669579-2242266465-3136906013-512"
        assert sec_desc.owner_sid == "S-1-5-21-3526669579-2242266465-3136906013-512"
        assert sec_desc.sbz1 == 0
        assert sec_desc.control["dacl_present"]
        assert len(sec_desc.dacl.aces) == 24
        assert sec_desc.dacl.aces[0].type == 5
        assert str(sec_desc.dacl.aces[0].trustee_sid) == "S-1-5-32-554"
        assert not sec_desc.control["sacl_present"]
        assert sec_desc.sacl is None
    with open(os.path.join(curdir, "testenv", "sd-sample1.bin"), "rb") as data:
        input_data = data.read()
        sec_desc = SecurityDescriptor.from_binary(input_data)
        assert sec_desc.revision == 1
        assert sec_desc.group_sid == "S-1-5-21-3526669579-2242266465-3136906013-512"
        assert sec_desc.owner_sid == "S-1-5-21-3526669579-2242266465-3136906013-512"
        assert sec_desc.sbz1 == 0
        assert sec_desc.control["dacl_present"]
        assert len(sec_desc.dacl.aces) == 24
        assert sec_desc.dacl.aces[0].type == 5
        assert sec_desc.dacl.aces[0].trustee_sid == "S-1-5-32-554"
        assert sec_desc.control["sacl_present"]
        assert len(sec_desc.sacl.aces) == 3
        assert sec_desc.sacl.aces[0].type == 2
        assert sec_desc.sacl.aces[0].trustee_sid == "S-1-1-0"


@pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="Cannot query SecurityDescriptor from OpenLDAP",
)
@pytest.mark.parametrize(
    "sd_flags, owner_sid, group_sid, dacl, sacl",
    [
        (1, True, False, False, False),
        (2, False, True, False, False),
        (3, True, True, False, False),
        (4, False, False, True, False),
        (8, False, False, False, True),
        (15, True, True, True, True),
    ],
    ids=["only-owner", "only-group", "owner-group", "only-dacl", "only-sacl", "all"],
)
def test_sd_flags(client, sd_flags, owner_sid, group_sid, dacl, sacl):
    """ Test LDAP_SERVER_SD_FLAGS_OID control """
    client.sd_flags = sd_flags
    with client.connect() as conn:
        res = conn.search(
            "cn=chuck,ou=nerdherd,dc=bonsai,dc=test",
            0,
            attrlist=["nTSecurityDescriptor"],
        )[0]
        sec_desc = SecurityDescriptor.from_binary(res["nTSecurityDescriptor"][0])
        assert sec_desc.revision == 1
        if owner_sid:
            assert sec_desc.owner_sid is not None
            assert isinstance(sec_desc.owner_sid, SID)
        else:
            assert sec_desc.owner_sid is None
        if group_sid:
            assert sec_desc.group_sid is not None
            assert isinstance(sec_desc.group_sid, SID)
        else:
            assert sec_desc.group_sid is None
        assert sec_desc.control["dacl_present"] is dacl
        if dacl:
            assert isinstance(sec_desc.dacl, ACL)
        else:
            assert sec_desc.dacl is None
        assert sec_desc.control["sacl_present"] is sacl
        if sacl:
            assert isinstance(sec_desc.sacl, ACL)
        else:
            assert sec_desc.sacl is None