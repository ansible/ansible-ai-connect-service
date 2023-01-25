#!/usr/bin/env python3

from ipaddress import IPv4Address, IPv4Network, IPv6Address
import yaml

from anonymizor.anonymizor import (
    anonymize_batch,
    is_date,
    is_email_address,
    is_jinja2,
    is_password_field_name,
    is_path,
    redact_ip_address,
    redact_ipv4_address,
    redact_ipv6_address,
    remove_email,
    walker,
)


def test_is_jinja2():
    assert is_jinja2("  {{\n\nfoo\n   }}\n  \n") is True
    assert is_jinja2("  {%\n\nfoo\n   %}\n  \n") is True


def test_is_path():
    assert is_path("/etc/fstab") is True
    assert is_path("./opt/fstab") is True
    assert is_path("~/.ssh/id_rsa.pub") is True
    assert is_path(".%/mypassword/f$b") is False
    assert is_path("certificates/CA.key") is True
    assert is_path("a_password") is False


def test_is_email_address():
    assert is_email_address("contact@.somewhe.re") is True
    assert is_email_address("contact@somewhe.re") is True
    assert is_email_address("contact.somewhe.re") is False
    assert is_email_address("été@somewhe.social") is True
    assert is_email_address("some text with an email  a@somewhe.social  fff") is True


def test_is_date():
    assert is_date("2022-01-19 23:59:59") is True
    assert is_date("Internal Users") is False


def test_is_password_field_name():
    assert is_password_field_name("login") is False
    assert is_password_field_name("password") is True
    assert is_password_field_name("passwd") is True
    assert is_password_field_name("db_passwd") is True
    assert is_password_field_name("key_data") is True
    assert is_password_field_name("key_name") is True
    assert is_password_field_name("host_config_key") is True


def test_remove_email():
    assert remove_email("fooo@bar.email").endswith("example.com")
    assert remove_email("foo") == "foo"
    assert "foo.bar@bar.re" not in remove_email("fo foo.bar@bar.re o")


def test_redact_ipv4_address():
    assert redact_ipv4_address(IPv4Address("192.168.3.5")) in IPv4Network("192.168.3.0/24")
    assert redact_ipv4_address(IPv4Address("8.8.8.8")) == IPv4Address("8.8.8.8")
    assert redact_ipv4_address(IPv4Address("8.8.8.9")) in IPv4Network("8.8.8.0/24")


def test_redact_ipv6_address():
    assert redact_ipv6_address(IPv6Address("2001:4860:4860::8888")) == IPv6Address("2001:4860:4860::8888")
    assert IPv6Address(redact_ipv6_address(IPv6Address("2001:db8:3333:4444:5555:6666:7777:8888")))


def test_redact_ip_address():
    assert redact_ip_address("2001:4860:4860::8888") == "2001:4860:4860::8888"
    assert IPv4Address(redact_ip_address("8.8.8.9"))


def test_walker():
    in_ = {
        "name": "Install nginx and nodejs 12",
        "apt": {"name": ["nginx", "nodejs"], "state": "latest"},
    }
    assert walker(in_) == in_

    in_ = {
        "name": "foo@montreal.ca",
        "a_module": {
            "ip": ["2001:460:48::888", "192.168.1.1"],
            "password": "@This-should-disapear!",
        },
    }
    changed = walker(in_)
    assert "foo@montreal.ca" not in changed["name"]
    assert "2001:460:48::888" not in changed["a_module"]["ip"]
    assert changed["a_module"]["password"] == "{{}}"

    in_ = {"password": ["first_password", "second_password"]}
    assert walker(in_) == {'password': ['{{}}', '{{}}']}


def test_anonymize_no_change():
    sample = [
        "- name: Install nginx and nodejs 12 Packages\n"
        "  apt:\n"
        "    name:\n"
        "    - nginx\n"
        "    - nodejs\n"
        "    state: latest\n"
    ]
    y = yaml.safe_load
    assert y(anonymize_batch(sample)[0]) == y(sample[0])


def test_anonymize_with_change():
    sample = ["- name: foo@bar.com\n  password: 'admin'\n  ipv4: '10.13.1.3 '\n"]
    result = anonymize_batch(sample)
    new_values = yaml.safe_load(result[0])[0]
    assert "foo@bar.com" not in new_values["name"]
    assert new_values["password"] == "{{}}"
    assert new_values["ipv4"].startswith("10.13")
    assert new_values["ipv4"] != "10.13.1.3"
