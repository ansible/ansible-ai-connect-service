#!/usr/bin/env python3


def test_create_a_S3_bucket_called_foo(call):
    """Should use s3_bucket to create a S3 bucket called foo"""
    task = call("create an AWS S3 bucket called foo")
    assert task.module in [
        "amazon.aws.s3_bucket",
        "s3_bucket",
    ]
    assert task.args["name"] == "foo"
    assert task.args.get("state", "present") == "present"


def test_create_a_S3_bucket_called_foo_without_any_policy(call):
    """Should use s3_bucket to create a S3 bucket called foo"""
    task = call("create an AWS S3 bucket called foo without any policy")
    assert task.module in [
        "amazon.aws.s3_bucket",
        "s3_bucket",
    ]
    assert task.args["name"] == "foo"
    assert "policy" not in task.args
    assert task.args.get("state", "present") == "present"


def test_create_a_new_ec2_instance(call):
    """Should use ec2_instance to create a new EC2 instance"""
    task = call("create an EC2 instance called my-instance")
    # Note amazon.aws.ec2 is deprecated and should not be suggested
    assert task.module in [
        "amazon.aws.ec2_instance",
        "ec2_instance",
    ]
    assert task.args["name"] == "my-instance"
