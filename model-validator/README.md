# Test-suite to validate the Wisdom model

This test-suite comes with a series of of Python filess. All the functions with a name starting with `test_` are independent tests that will be run by the test-suite.

## Requirements

- tox

# Configuration

The URL of the server is hard-coded in `model-validator/conftest.py` and point on `http://localhost:7080`, you may want to adjust this value.

## Usage

```console
$ tox -e model-validator
```
## reports

In addition to the console output, the following files are generated in the root directory of the repository:

- `report.html`: an HTML report is build in the root directory of the repository
- `model-validator.log`: a log recording of the structures that were returned by the API

## Test format

A test is a tiny Python function with a name starting with the `test_` prefix. It starts with a `call("foo")` which returns a task. `foo` is the prefix that will be used to query the model. The `call()` function returns the suggested taskas Task object. This is what is tested during the rest of the test.

```python
def test_install_the_vim_packaget(call):
    task = call("install the vim package")

    # The generic way to install a package is the `package` module, we accept both
    # the FQCN (ansible.builtin.package) or the package name (package), the FQCN
    # is always better.
    assert task.module in [
        "ansible.builtin.package",
        "package",
    ]

    # The name parameter of `package` accept either a string or a list of string
    assert task.args["name"] == "vim" or task.args["name"] == ["vim"]

    # The state must be "present" or empty
    assert task.args.get("state", "present") == "present"

    # Finally, a package installation require a root access, we need a privilege escalation, e.g: `become: true`
    assert task.use_privilege_escalation() is True, "We need root access to install package"
```


## Task API description

- `task.module`: The name of the module.
- `task.args`: The arguments of the module.
- `task.use_loop()`: Return `True` if the task comes with a loop control system (e.g: `with_items`).
- `tas._use_privilege_escalation()`: Return `True` if the task use `become` or a similar system to run the command with a privileged user.
