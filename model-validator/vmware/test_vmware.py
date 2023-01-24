#!/usr/bin/env python3


def test_find_the_correct_VMware_module_to_create_a_VM(call):
    """Should use either vmware_guest or vcenter_vm to create a VMware VM"""
    context = [
        {
            "name": "Create Datacenter",
            "vmware_datacenter": {
                "datacenter_name": "dc1",
                "state": "present",
            },
        },
        {
            "name": "Create a VM folder on given Datacenter",
            "vcenter_folder": {
                "datacenter": "dc1",
                "folder_name": "f0",
                "folder_type": "vm",
                "state": "present",
            },
        },
    ]

    task = call("create a virtual machine in folder f0 of the datastore ds1", context)
    assert task.module in [
        "community.vmware.vmware_guest",
        "vmware_guest",
        "vmware.vmware_rest.vcenter_vm",
        "vcenter_vm",
    ]
    if task.module.endswith("vcenter_vm"):
        assert task.args["folder"] == "f0"
        assert task.args["datastore"] == "ds1"


def test_continue_to_use_a_fqcn_to_be_consistent_with_the_context(call):
    """Should follow the existing convention of the context and suggest a FQCN"""
    context = [
        {
            "name": "Create Datacenter",
            "community.vmware.vmware_datacenter": {
                "datacenter_name": "dc1",
                "state": "present",
            },
        },
        {
            "name": "Create a VM folder on given Datacenter",
            "community.vmware.vcenter_folder": {
                "datacenter": "dc1",
                "folder_name": "f0",
                "folder_type": "vm",
                "state": "present",
            },
        },
    ]

    task = call("create a virtual machine in folder f0 of the datastore dc1", context)
    assert task.module in [
        "community.vmware.vmware_guest",
        "vmware.vmware_rest.vcenter_vm",
    ], "task should use a FQCN to be consistent with the context"
