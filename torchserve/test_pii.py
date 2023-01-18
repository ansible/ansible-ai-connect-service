#!/usr/bin/env python3

import ciso8601
import ipaddress
import json
import logging
import random
import re
import time
import yaml

from detect_secrets.plugins import keyword
from password_strength import PasswordStats


logger = logging.getLogger(__name__)


sample = [
    """
        user:
            name: "{{ item.name }}"
            password: "{{ item.password }}"
            email: jean-pierre@please-hide-this.org
            ipv4: 13.213.107.236
            ipv6: 2607:f8b0:4020:806::2003
        with_items:
        - { name: 'nginx', password: 'test1234' }
        - { name: 'node', password: '1234' }
        - { name: 'nginx2', password: 'Th!sTim³íT³ríÓs' }
        - { name: 'another-case', password: "F0o^bar2000&"}
        """
]


def gen_sample_password():
    colours = ["red", "blue", "green", "yellow", "purple", "pink", "orange", "brown"]
    fruits = ["papaya", "peach", "apple", "pineapple", "watermelon", "raspberry"]
    countries = ["senegal", "japan", "ukraine"]

    return f"{random.choice(colours)}-{random.choice(fruits)}-{random.choice(countries)}"


def gen_email_address():
    samples = [
        "liam",
        "olivia",
        "noah",
        "emma",
        "oliver",
        "charlotte",
        "elijah",
        "amelia",
        "james",
        "ava",
        "william",
        "sophia",
        "benjamin",
        "isabella",
        "lucas",
        "mia",
        "henry",
        "evelyn",
        "theodore",
        "harper",
    ]
    return f"{random.choice(samples)}{random.randint(0, 100)}@example.com"


def test_is_jinja2():
    assert is_jinja2("  {{\n\nfoo\n   }}\n  \n") is True
    assert is_jinja2("  {%\n\nfoo\n   %}\n  \n") is True


def is_jinja2(content: str) -> bool:
    flags = re.MULTILINE | re.DOTALL
    if bool(re.search(r"{{.*\w+.*}}", content, flags)):
        return True
    if bool(re.search(r"{%.*\w+.*%}", content, flags)):
        return True
    return False


def is_ip_address(content: str):
    try:
        ip = ipaddress.ip_address(content)
    except ValueError:
        return False
    return True


def test_is_path():
    assert is_path("/etc/fstab") is True
    assert is_path("./opt/fstab") is True
    assert is_path("~/.ssh/id_rsa.pub") is True
    assert is_path(".%/mypassword/f$b") is False
    assert is_path("certificates/CA.key") is True


def is_path(content: str):
    # Rather conservative on purpose to avoid a false
    # positive
    return bool(re.match(r"^(|~)[a-z0-9_/\.-]+$", content, flags=re.IGNORECASE))


def test_is_email_address():
    assert is_email_address("contact@.somewhe.re") is True
    assert is_email_address("contact@somewhe.re") is True
    assert is_email_address("contact.somewhe.re") is False
    assert is_email_address("été@somewhe.social") is True
    assert is_email_address("some text with an email  a@somewhe.social  fff") is True


def is_email_address(content: str) -> bool:
    return bool(re.match(r".*\w+@[a-z\.]+[a-z]{2,}.*", content, flags=re.IGNORECASE))


def test_is_date():
    assert is_date("2022-01-19 23:59:59") is True
    assert is_date("Internal Users") is False

def is_date(content: str) -> bool:
    # Py3.11 comes with a very performant solution
    # https://github.com/closeio/ciso8601/blob/master/why_ciso8601.md#do-you-need-to-support-python--311
    try:
        return bool(ciso8601.parse_datetime(content))
    except ValueError:
        return False

def is_password(content):
    stats = PasswordStats(content)
    return stats.strength() > 0.5


def test_sensitive_field_name():
    assert sensitive_field_name("login") is False
    assert sensitive_field_name("password") is True
    assert sensitive_field_name("passwd") is True
    assert sensitive_field_name("db_passwd") is True
    assert sensitive_field_name("db_passwd") is True


def sensitive_field_name(name: str) -> bool:
    return re.search(keyword.DENYLIST_REGEX_WITH_PREFIX, name) is not None


def anonymize_field(value: str, name) -> str:
    if not value:
        return value
    elif is_jinja2(value):
        return value
    elif is_ip_address(value):
        return 'censored-ip-address'
    elif is_email_address(value):
        return gen_email_address()

    if sensitive_field_name(name):
        if is_path(value):
            return value
        elif is_date(value):
            print(f"DATE: {value}")
            return value
        elif is_password(value):
            one_line_value = value.replace('\n', '')
            print(f"name:{name}, value:{one_line_value}")
            return gen_sample_password()
    return value


def walker(o, key_name=''):
    def key_name_str(k):
        return k if isinstance(k, str) else ''

    if key_name and not isinstance(key_name, str):
        key_name = str(key_name)
    if isinstance(o, dict):
        return {k: walker(v, key_name=key_name_str(k)) for k, v in o.items()}
    elif isinstance(o, list):
        return [walker(v) for v in o]
    elif isinstance(o, str):
        return anonymize_field(o, key_name)
    else:
        return o


def anonymize(prediction):
    return walker(prediction)


def test_anonymize():
    anonymize(sample[0])


def benchmark():
    cpt = 0
    duration = 0
    with open("/home/goneri/Downloads/awft_v2.4.2_train.json", "r") as fd:
        while True:
            line = fd.readline()
            if not line:
                break
            train_entry = json.loads(line)
            from pprint import pprint

            prediction = yaml.load(train_entry["output_script"])
            start = time.perf_counter()
            ano = anonymize(prediction)
            duration += time.perf_counter() - start
            cpt += 1
    print(f"cpt: {cpt}")
    print(f"total duration: {duration}")
    print(f"average: {duration/cpt}")

