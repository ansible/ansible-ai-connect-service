#!/usr/bin/env python3


def test_install_the_vim_packaget(call):
    """Should use the package module to install vim"""
    task = call("install the vim package")
    assert task.module in [
        "ansible.builtin.package",
        "package",
    ]
    assert task.args["name"] == "vim" or task.args["name"] == ["vim"]
    assert task.use_privilege_escalation() is True, "We need root access to install package"
    task.assert_has_no_loop()
