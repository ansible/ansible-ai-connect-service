#!/usr/bin/env python3

import re
import warnings


def test_store_a_value_in_a_fact(call):
    """Should define a new fact with a random value"""
    task = call("store a value in a fact called my_fact")
    assert task.module in [
        "ansible.builtin.set_fact",
        "set_fact",
    ]
    assert task.args["my_fact"]
    task.assert_has_no_loop()


def test_print_the_value_of_a_fact(call):
    """Should print a fact using the var parameter of the debug module"""
    task = call("print the value of my_fact")
    assert task.module in [
        "ansible.builtin.debug",
        "debug",
    ]
    if task.args.get("msg"):
        warnings.warn("Use debug's `msg` to print a fact, should use `var`")
        assert re.search(r"{{\s*my_fact\s*}}", task.args["msg"])
    else:
        assert task.args["var"] == "my_fact"
    task.assert_has_no_loop()


def test_print_a_message_with_the_fact_and_the_hostname(call):
    """Should prepare a Jinja2 template and print it with debug"""
    task = call("print the value of my_fact")
    assert task.module in [
        "ansible.builtin.debug",
        "debug",
    ]
    assert re.search(r"{{\s*my_fact\s*}}", task.args["msg"])
    task.assert_has_no_loop()


def test_increase_the_value_of_cpt(call):
    """Should increase the existing int from the context by one"""
    task = call("increase the value of cpt", context_from_file=True)
    assert task.module in [
        "ansible.builtin.set_fact",
        "set_fact",
    ]
    # Note: cpt is already a int and we don't need to cast the value
    assert task.args["cpt"] in ['cpt | int + 1', 'cpt + 1']
    task.assert_has_no_loop()
