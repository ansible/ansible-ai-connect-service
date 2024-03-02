
# Default Rules

(lint_default_rules)=

Below you can see the list of default rules Ansible Lint use to evaluate playbooks and roles:



# args

This rule validates if the task arguments conform with the plugin documentation.

The rule validation will check if the option name is valid and has the correct
value along with conditionals on the options like `mutually_exclusive`,
`required_together`, `required_one_of` and so on.

For more information see the
(https://docs.ansible.com/ansible/latest/reference_appendices/module_utils.html#argumentspecvalidator)
topic in the Ansible module utility documentation.

Possible messages:

- `args` - missing required arguments: ...
- `args` - missing parameter(s) required by ...

## Problematic Code

```yaml
---
- name: Fixture to validate module options failure scenarios
  hosts: localhost
  tasks:
    - name: Clone content repository
      ansible.builtin.git: # <- Required option `repo` is missing.
        dest: /home/www
        accept_hostkey: true
        version: master
        update: false

    - name: Enable service httpd and ensure it is not masked
      ansible.builtin.systemd: # <- Missing 'name' parameter required by 'enabled'.
        enabled: true
        masked: false

    - name: Use quiet to avoid verbose output
      ansible.builtin.assert:
        test:
          - my_param <= 100
          - my_param >= 0
        quiet: invalid # <- Value for option `quiet` is invalid.
```

## Correct Code

```yaml
---
- name: Fixture to validate module options pass scenario
  hosts: localhost
  tasks:
    - name: Clone content repository
      ansible.builtin.git: # <- Contains required option `repo`.
        repo: https://github.com/ansible/ansible-examples
        dest: /home/www
        accept_hostkey: true
        version: master
        update: false

    - name: Enable service httpd and ensure it is not masked
      ansible.builtin.systemd: # <- Contains 'name' parameter required by 'enabled'.
        name: httpd
        enabled: false
        masked: false

    - name: Use quiet to avoid verbose output
      ansible.builtin.assert:
        that:
          - my_param <= 100
          - my_param >= 0
        quiet: True # <- Has correct type value for option `quiet` which is boolean.
```

## Special cases

In some complex cases where you are using jinja expressions, the linter may not
able to fully validate all the possible values and report a false positive. The
example below would usually report
`parameters are mutually exclusive: data|file|keyserver|url` but because we
added `# noqa: args` it will just pass.

```yaml
- name: Add apt keys # noqa: args
  become: true
  ansible.builtin.apt_key:
    url: "{{ zj_item['url'] | default(omit) }}"
    data: "{{ zj_item['data'] | default(omit) }}"
  loop: "{{ repositories_keys }}"
  loop_control:
    loop_var: zj_item
```


# avoid-implicit

This rule identifies the use of dangerous implicit behaviors, often also
undocumented.

This rule will produce the following type of error messages:

- `avoid-implicit` is not a string as (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html#synopsis)
  modules also accept these, but without documenting them.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Write file content
      ansible.builtin.copy:
        content: { "foo": "bar" } # <-- should use explicit jinja template
        dest: /tmp/foo.txt
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Write file content
      vars:
        content: { "foo": "bar" }
      ansible.builtin.copy:
        content: "{{ content | to_json }}" # explicit better than implicit!
        dest: /tmp/foo.txt
```


# command-instead-of-module

This rule will recommend you to use a specific ansible module instead for tasks
that are better served by a module, as these are more reliable, provide better
messaging and usually have additional features like the ability to retry.

In the unlikely case that the rule triggers false positives, you can disable it
by adding a comment like `# noqa: command-instead-of-module` to the same line.

You can check the (https://github.com/ansible/ansible-lint/blob/main/src/ansiblelint/rules/command_instead_of_module.py)
of the rule for all the known commands that trigger the rule and their allowed
list arguments of exceptions and raise a pull request to improve them.

## Problematic Code

```yaml
---
- name: Update apt cache
  hosts: all
  tasks:
    - name: Run apt-get update
      ansible.builtin.command: apt-get update # <-- better to use ansible.builtin.apt module
```

## Correct Code

```yaml
---
- name: Update apt cache
  hosts: all
  tasks:
    - name: Run apt-get update
      ansible.builtin.apt:
        update_cache: true
```


# command-instead-of-shell

This rule identifies uses of `shell` modules instead of a `command` one when
this is not really needed. Shell is considerably slower than command and should
be avoided unless there is a special need for using shell features, like
environment variable expansion or chaining multiple commands using pipes.

## Problematic Code

```yaml
---
- name: Problematic example
  hosts: localhost
  tasks:
    - name: Echo a message
      ansible.builtin.shell: echo hello # <-- command is better in this case
      changed_when: false
```

## Correct Code

```yaml
---
- name: Correct example
  hosts: localhost
  tasks:
    - name: Echo a message
      ansible.builtin.command: echo hello
      changed_when: false
```


# complexity

This rule aims to warn about Ansible content that seems to be overly complex,
suggesting refactoring for better readability and maintainability.

## complexity

`complexity` will be triggered if the total number of tasks inside a file
is above 100. If encountered, you should consider using
[`ansible.builtin.include_tasks`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/include_tasks_module.html)
to split your tasks into smaller files.

## complexity

`complexity` will appear when a block contains too many tasks, by
default that number is 20 but it can be changed inside the configuration file by
defining `max_block_depth` value.

    Replace nested block with an include_tasks to make code easier to maintain. Maximum block depth allowed is ...


# deprecated-bare-vars

This rule identifies possible confusing expressions where it is not clear if
a variable or string is to be used and asks for clarification.

You should either use the full variable syntax ('{{{{ {0} }}}}') or, whenever
possible, convert it to a list of strings.

## Problematic code

```yaml
---
- ansible.builtin.debug:
    msg: "{{ item }}"
  with_items: foo # <-- deprecated-bare-vars
```

## Correct code

```yaml
---
# if foo is not really a variable:
- ansible.builtin.debug:
    msg: "{{ item }}"
  with_items:
    - foo

# if foo is a variable:
- ansible.builtin.debug:
    msg: "{{ item }}"
  with_items: "{{ foo }}"
```


# deprecated-local-action

This rule recommends using `delegate_to: localhost` instead of the
`local_action`.

## Problematic Code

```yaml
---
- name: Task example
  local_action: # <-- this is deprecated
    module: ansible.builtin.debug
```

## Correct Code

```yaml
- name: Task example
    ansible.builtin.debug:
  delegate_to: localhost # <-- recommended way to run on localhost
```


# deprecated-module

This rule identifies deprecated modules in playbooks.
You should avoid using deprecated modules because they are not maintained, which can pose a security risk.
Additionally when a module is deprecated it is available temporarily with a plan for future removal.

Refer to the [Ansible module index](https://docs.ansible.com/ansible/latest/collections/index_module.html) for information about replacements and removal dates for deprecated modules.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Configure VLAN ID
      ansible.netcommon.net_vlan: # <- Uses a deprecated module.
        vlan_id: 20
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Configure VLAN ID
      dellemc.enterprise_sonic.sonic_vlans: # <- Uses a platform specific module.
        config:
          - vlan_id: 20
```


# empty-string-compare

This rule checks for empty string comparison in playbooks.
To ensure code clarity you should avoid using empty strings in conditional statements with the `when` clause.

- Use `when: var | length > 0` instead of `when: var != ""`.
- Use `when: var | length == 0` instead of `when: var == ""`.

This is an opt-in rule.
You must enable it in your Ansible-lint configuration as follows:

```yaml
enable_list:
  - empty-string-compare
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Shut down
      ansible.builtin.command: /sbin/shutdown -t now
      when: ansible_os_family == "" # <- Compares with an empty string.
    - name: Shut down
      ansible.builtin.command: /sbin/shutdown -t now
      when: ansible_os_family !="" # <- Compares with an empty string.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Shut down
      ansible.builtin.shell: |
        /sbin/shutdown -t now
        echo $var ==
      when: ansible_os_family
```


# fqcn

This rule checks for fully-qualified collection names (FQCN) in Ansible content.

Declaring an FQCN ensures that an action uses code from the correct namespace.
This avoids ambiguity and conflicts that can cause operations to fail or produce
unexpected results.

The `fqcn` rule has the following checks:

- `fqcn` - Use FQCN for module actions, such ...
- `fqcn` - Checks for FQCNs from the `ansible.legacy` or
  `ansible.builtin` collection.
- `fqcn` - You should use canonical module name ... instead of ...
- [`fqcn`](#deep-modules) - Checks for deep/nested plugins directory
  inside collections.
- `fqcn` - Avoid `collections` keyword by using FQCN for all plugins,
  modules, roles and playbooks.

!!! note

    In most cases you should declare the `ansible.builtin` collection for internal Ansible actions.
    You should declare the `ansible.legacy` collection if you use local overrides with actions, such with as the ``shell`` module.

!!! warning

    This rule does not take [`collections` keyword](https://docs.ansible.com/ansible/latest/collections_guide/collections_using_playbooks.html#simplifying-module-names-with-the-collections-keyword) into consideration for resolving content.
    The `collections` keyword provided a temporary mechanism transitioning to Ansible 2.9.
    You should rewrite any content that uses the `collections:` key and avoid it where possible.

## Canonical module names

Canonical module names are also known as **resolved module names** and they are
to be preferred for most cases. Many Ansible modules have multiple aliases and
redirects, as these were created over time while the content was refactored.
Still, all of them do finally resolve to the same module name, but not without
adding some performance overhead. As very old aliases are at some point removed,
it makes to just refresh the content to make it point to the current canonical
name.

The only exception for using a canonical name is if your code still needs to be
compatible with a very old version of Ansible, one that does not know how to
resolve that name. If you find yourself in such a situation, feel free to add
this rule to the ignored list.

## Deep modules

When writing modules, you should avoid nesting them in deep directories, even if
Ansible allows you to do so. Since early 2023, the official guidance, backed by
the core team, is to use a flat directory structure for modules. This ensures
optimal performance.

Existing collections that still use deep directories can migrate to the flat
structure in a backward-compatible way by adding redirects like in
(https://github.com/ansible-collections/community.general/blob/main/meta/runtime.yml#L227-L233).

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Create an SSH connection
      shell: ssh ssh_user@{{ ansible_ssh_host }} # <- Does not use the FQCN for the shell module.
```

## Correct Code

```yaml
---
- name: Example playbook (1st solution)
  hosts: all
  tasks:
    - name: Create an SSH connection
      # Use the FQCN for the legacy shell module and allow local overrides.
      ansible.legacy.shell:
        ssh ssh_user@{{ ansible_ssh_host }} -o IdentityFile=path/to/my_rsa
```

```yaml
---
- name: Example playbook (2nd solution)
  hosts: all
  tasks:
    - name: Create an SSH connection
      # Use the FQCN for the builtin shell module.
      ansible.builtin.shell: ssh ssh_user@{{ ansible_ssh_host }}
```


# galaxy

This rule identifies if the collection version mentioned in galaxy.yml is ideal
in terms of the version number being greater than or equal to `1.0.0`.

This rule looks for a changelog file in expected locations, detailed below in
the Changelog Details section.

This rule checks to see if the `galaxy.yml` file includes one of the required
tags for certification on Automation Hub. Additional custom tags can be added,
but one or more of these tags must be present for certification.

The tag list is as follows: `application`, `cloud`,`database`, `infrastructure`,
`linux`, `monitoring`, `networking`, `security`,`storage`, `tools`, `windows`.

This rule can produce messages such:

- `galaxy` - `galaxy.yaml` should have version tag.
- `galaxy` - collection version should be greater than or
  equal to `1.0.0`
- `galaxy` - collection is missing a changelog file in expected
  locations.
- `galaxy` - Please add a
  (https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_structure.html#meta-directory-and-runtime-yml)
  file.
- `galaxy` - `galaxy.yaml` must have one of the required tags:
  `application`, `cloud`, `database`, `infrastructure`, `linux`, `monitoring`,
  `networking`, `security`, `storage`, `tools`, `windows`.
- `galaxy` = Invalid collection metadata. Dependency
  version spec range is invalid

If you want to ignore some of the messages above, you can add any of them to the
`ignore_list`.

## Problematic code

```yaml
# galaxy.yml
---
name: foo
namespace: bar
version: 0.2.3 # <-- collection version should be >= 1.0.0
authors:
  - John
readme: ../README.md
description: "..."
```

## Correct code

```yaml
# galaxy.yml
---
name: foo
namespace: bar
version: 1.0.0
authors:
  - John
readme: ../README.md
description: "..."
```

# Changelog Details

This rule expects a `CHANGELOG.md` or `.rst` file in the collection root or a
`changelogs/changelog.yaml` file.

If a `changelogs/changelog.yaml` file exists, the schema will be checked.

## Minimum required changelog.yaml file

```yaml
# changelog.yaml
---
releases: {}
```

# Required Tag Details

## Problematic code

```yaml
# galaxy.yml
---
namespace: bar
name: foo
version: 1.0.0
authors:
  - John
readme: ../README.md
description: "..."
license:
  - Apache-2.0
repository: https://github.com/ORG/REPO_NAME
```

## Correct code

```yaml
# galaxy.yml
---
namespace: bar
name: foo
version: 1.0.0
authors:
  - John
readme: ../README.md
description: "..."
license:
  - Apache-2.0
repository: https://github.com/ORG/REPO_NAME
tags: 
```


# ignore-errors

This rule checks that playbooks do not use the `ignore_errors` directive to ignore all errors.
Ignoring all errors in a playbook hides actual failures, incorrectly mark tasks as failed, and result in unexpected side effects and behavior.

Instead of using the `ignore_errors: true` directive, you should do the following:

- Ignore errors only when using the `{{ ansible_check_mode }}` variable.
- Use `register` to register errors.
- Use `failed_when:` and specify acceptable error conditions.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Run apt-get update
      ansible.builtin.command: apt-get update
      ignore_errors: true # <- Ignores all errors, including important failures.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Run apt-get update
      ansible.builtin.command: apt-get update
      ignore_errors: "{{ ansible_check_mode }}" # <- Ignores errors in check mode.
```

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Run apt-get update
      ansible.builtin.command: apt-get update
      ignore_errors: true
      register: ignore_errors_register # <- Stores errors and failures for evaluation.
```

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Disable apport
      become: "yes"
      lineinfile:
        line: "enabled=0"
        dest: /etc/default/apport
        mode: 0644
        state: present
      register: default_apport
      failed_when: default_apport.rc !=0 and not default_apport.rc == 257 # <- Defines conditions that constitute a failure.
```


# inline-env-var

This rule checks that playbooks do not set environment variables in the `ansible.builtin.command` module.

You should set environment variables with the `ansible.builtin.shell` module or the `environment` keyword.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Set environment variable
      ansible.builtin.command: MY_ENV_VAR=my_value # <- Sets an environment variable in the command module.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Set environment variable
      ansible.builtin.shell: echo $MY_ENV_VAR
      environment:
        MY_ENV_VAR: my_value # <- Sets an environment variable with the environment keyword.
```

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Set environment variable
      ansible.builtin.shell: MY_ENV_VAR=my_value # <- Sets an environment variable with the shell module.
```


# internal-error

This error can also be caused by internal bugs but also by custom rules.
Instead of just stopping tool execution, we generate the errors and continue
processing other files. This allows users to add this rule to their `warn_list`
until the root cause is fixed.

Keep in mind that once an `internal-error` is found on a specific file, no
other rules will be executed on that same file.

In almost all cases you will see more detailed information regarding the
original error or runtime exception that triggered this rule.

If these files are broken on purpose, like some test fixtures, you need to add
them to the `exclude_paths`.

## Problematic code

```yaml
---
- name: Some title {{ # <-- Ansible will not load this invalid jinja template
  hosts: localhost
  tasks: []
```

## Correct code

```yaml
---
- name: Some title
  hosts: localhost
  tasks: []
```

## ERROR! No hosts matched the subscripted pattern

If you see this error, it means that you tried to index a host group variable
that is using an index above its size.

Instead of doing something like `hosts: all[1]` which assumes that you have
at least two hosts in your current inventory, you better write something like
`hosts: "{{ all[1] | default([]) }}`, which is safe and do not produce runtime
errors. Use safe fallbacks to make your code more resilient.


# jinja

This rule can report problems related to jinja2 string templates. The current
version can report:

- `jinja` when there are no spaces between variables
  and operators, including filters, like `{{ var_name | filter }}`. This
  improves readability and makes it less likely to introduce typos.
- `jinja` when the jinja2 template is invalid, like `{{ {{ '1' }} }}`,
  which would result in a runtime error if you try to use it with Ansible, even
  if it does pass the Ansible syntax check.

As jinja2 syntax is closely following Python one we aim to follow
(https://black.readthedocs.io/en/stable/) formatting rules. If you are
curious how black would reformat a small sniped feel free to visit
(https://black.vercel.app/) site. Keep in mind to not
include the entire jinja2 template, so instead of `{{ 1+2==3 }}`, do paste
only `1+2==3`.

In ansible, `changed_when`, `failed_when`, `until`, `when` are considered to
use implicit jinja2 templating, meaning that they do not require `{{ }}`. Our
rule will suggest the removal of the braces for these fields.

## Problematic code

```yaml
---
- name: Some task
  vars:
    foo: "{{some|dict2items}}" # <-- jinja
    bar: "{{ & }}" # <-- jinja
  when: "{{ foo | bool }}" # <-- jinja - 'when' has implicit templating
```

## Correct code

```yaml
---
- name: Some task
  vars:
    foo: "{{ some | dict2items }}"
    bar: "{{ '&' }}"
  when: foo | bool
```

## Current limitations

In its current form, this rule presents the following limitations:

- Jinja2 blocks that have newlines in them will not be reformatted because we
  consider that the user deliberately wanted to format them in a particular way.
- Jinja2 blocks that use tilde as a binary operation are ignored because black
  does not support tilde as a binary operator. Example: `{{ a ~ b }}`.
- Jinja2 blocks that use dot notation with numbers are ignored because python
  and black do not allow it. Example: `{{ foo.0.bar }}`


# key-order

This rule recommends reordering key names in ansible content to make
code easier to maintain and less prone to errors.

Here are some examples of common ordering checks done for tasks and handlers:

- `name` must always be the first key for plays, tasks and handlers
- on tasks, the `block`, `rescue` and `always` keys must be the last keys,
  as this would avoid accidental miss-indentation errors between the last task
  and the parent level.

## Problematic code

```yaml
---
- hosts: localhost
  name: This is a playbook # <-- name key should be the first one
  tasks:
    - name: A block
      block:
        - name: Display a message
          debug:
            msg: "Hello world!"
      when: true # <-- when key should be before block
```

## Correct code

```yaml
---
- name: This is a playbook
  hosts: localhost
  tasks:
    - name: A block
      when: true
      block:
        - name: Display a message
          debug:
            msg: "Hello world!"
```

## Reasoning

Making decisions about the optimal order of keys for ansible tasks or plays is
no easy task, as we had a huge number of combinations to consider. This is also
the reason why we started with a minimal sorting rule (name to be the first),
and aimed to gradually add more fields later, and only when we find the proofs
that one approach is likely better than the other.

### Why I no longer can put `when` after a `block`?

Try to remember that in real life, `block/rescue/always` have the habit to
grow due to the number of tasks they host inside, making them exceed what a single screen. This would move the `when` task further away from the rest of the task properties. A `when` from the last task inside the block can
easily be confused as being at the block level, or the reverse. When tasks are
moved from one location to another, there is a real risk of moving the block
level when with it.

By putting the `when` before the `block`, we avoid that kind of risk. The same risk applies to any simple property at the task level, so that is why
we concluded that the block keys must be the last ones.

Another common practice was to put `tags` as the last property. Still, for the
same reasons, we decided that they should not be put after block keys either.


# latest

The `latest` rule checks that module arguments like those used for source
control checkout do not have arguments that might generate different results
based on context.

This more generic rule replaced two older rules named `git-latest` and
`hg-latest`.

We are aware that there are genuine cases where getting the tip of the main
branch is not accidental. For these cases, just add a comment such as
`# noqa: latest` to the same line to prevent it from triggering.

## Possible errors messages:

- `latest`
- `latest`

## Problematic code

```yaml
---
- name: Example for `latest` rule
  hosts: localhost
  tasks:
    - name: Risky use of git module
      ansible.builtin.git:
        repo: "https://github.com/ansible/ansible-lint"
        version: HEAD # <-- HEAD value is triggering the rule
```

## Correct code

```yaml
---
- name: Example for `latest` rule
  hosts: localhost
  tasks:
    - name: Safe use of git module
      ansible.builtin.git:
        repo: "https://github.com/ansible/ansible-lint"
        version: abcd1234... # <-- that is safe
```


# literal-compare

This rule checks for literal comparison with the `when` clause.
Literal comparison, like `when: var == True`, is unnecessarily complex.
Use `when: var` to keep your playbooks simple.

Similarly, a check like `when: var != True` or `when: var == False`
should be replaced with `when: not var`.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Print environment variable to stdout
      ansible.builtin.command: echo $MY_ENV_VAR
      when: ansible_os_family == True # <- Adds complexity to your playbook.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Print environment variable to stdout
      ansible.builtin.command: echo $MY_ENV_VAR
      when: ansible_os_family # <- Keeps your playbook simple.
```


# load-failure

"Linter failed to process a file, possible invalid file. Possible reasons:

* contains unsupported encoding (only UTF-8 is supported)
* not an Ansible file
* it contains some unsupported custom YAML objects (`!!` prefix)
* it was not able to decrypt an inline `!vault` block.

This violation **is not** skippable, so it cannot be added to the `warn_list`
or the `skip_list`. If a vault decryption issue cannot be avoided, the
offending file can be added to `exclude_paths` configuration.


# loop-var-prefix

This rule avoids conflicts with nested looping tasks by enforcing an individual
variable name in loops. Ansible defaults to `item` as the loop variable. You can
use `loop_var` to rename it. Optionally require a prefix on the variable name.
The prefix can be configured via the `<loop_var_prefix>` setting.

This rule can produce the following messages:

- `loop-var-prefix` - Replace any unsafe implicit `item` loop variable
  by adding `loop_var: <variable_name>...`.
- `loop-var-prefix` - Ensure the loop variable starts with
  `<loop_var_prefix>`.

This rule originates from the [Naming parameters section of Ansible Best
Practices guide].

## Settings

You can change the behavior of this rule by overriding its default regular
expression used to check loop variable naming. Keep in mind that the `{role}`
part is replaced with the inferred role name when applicable.

```yaml
# .ansible-lint
loop_var_prefix: "^(__|{role}_)"
```

This is an opt-in rule. You must enable it in your Ansible-lint configuration as
follows:

```yaml
enable_list:
  - loop-var-prefix
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Does not set a variable name for loop variables.
      ansible.builtin.debug:
        var: item # <- When in a nested loop, "item" is ambiguous
      loop:
        - foo
        - bar
    - name: Sets a variable name that doesn't start with <loop_var_prefix>.
      ansible.builtin.debug:
        var: zz_item
      loop:
        - foo
        - bar
      loop_control:
        loop_var: zz_item # <- zz is not the role name so the prefix is wrong
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Sets a unique variable_name with role as prefix for loop variables.
      ansible.builtin.debug:
        var: myrole_item
      loop:
        - foo
        - bar
      loop_control:
        loop_var: myrole_item # <- Unique variable name with role as prefix
```

:
  https://redhat-cop.github.io/automation-good-practices/#_naming_parameters


# meta-incorrect

This rule checks role metadata for fields with undefined or default values.
Always set appropriate values for the following metadata fields in the `meta/main.yml` file:

- `author`
- `description`
- `company`
- `license`

## Problematic Code

```yaml
---
# Metadata fields for the role contain default values.
galaxy_info:
  author: your name
  description: your role description
  company: your company (optional)
  license: license (GPL-2.0-or-later, MIT, etc)
```

## Correct Code

```yaml
---
galaxy_info:
  author: Leroy Jenkins
  description: This role will set you free.
  company: Red Hat
  license: Apache
```


# meta-no-tags

This rule checks role metadata for tags with special characters.
Always use lowercase numbers and letters for tags in the `meta/main.yml` file.

## Problematic Code

```yaml
---
# Metadata tags contain upper-case letters and special characters.
galaxy_info:
  galaxy_tags: [MyTag#1, MyTag&^-]
```

## Correct Code

```yaml
---
# Metadata tags contain only lowercase letters and numbers.
galaxy_info:
  galaxy_tags: 
```


# meta-runtime

This rule checks the meta/runtime.yml `requires_ansible` key against the list of currently supported versions of ansible-core.

This rule can produce messages such:

- `requires_ansible` key must be set to a supported version.

Currently supported versions of ansible-core are:

- `2.9.10`
- `2.11.x`
- `2.12.x`
- `2.13.x`
- `2.14.x`
- `2.15.x`
- `2.16.x` (in development)

This rule can produce messages such as:

- `meta-runtime` - `requires_ansible` key must contain a supported version, shown in the list above.
- `meta-runtime` - `requires_ansible` key must be a valid version identifier.


## Problematic code

```yaml
# runtime.yml
---
requires_ansible: ">=2.9"
```


```yaml
# runtime.yml
---
requires_ansible: "2.9"
```

## Correct code

```yaml
# runtime.yml
---
requires_ansible: ">=2.9.10"
```


# meta-video-links

This rule checks formatting for video links in metadata. Always use dictionaries
for items in the `meta/main.yml` file.

Items in the `video_links` section must be in a dictionary and use the following
keys:

- `url`
- `title`

The value of the `url` key must be a shared link from YouTube, Vimeo, or Google
Drive.

## Problematic Code

```yaml
---
galaxy_info:
  video_links:
    - https://www.youtube.com/watch?v=aWmRepTSFKs&feature=youtu.be # <- Does not use the url key.
    - my_bad_key: https://www.youtube.com/watch?v=aWmRepTSFKs&feature=youtu.be # <- Uses an unsupported key.
      title: Incorrect key.
    - url: www.acme.com/vid # <- Uses an unsupported url format.
      title: Incorrect url format.
```

## Correct Code

```yaml
---
galaxy_info:
  video_links:
    - url: https://www.youtube.com/watch?v=aWmRepTSFKs&feature=youtu.be # <- Uses a supported shared link with the url key.
      title: Correctly formatted video link.
```


# name

This rule identifies several problems related to the naming of tasks and plays.
This is important because these names are the primary way to **identify** and
**document** executed operations on the console, logs or web interface.

This rule can produce messages as:

- `name` - All names should start with an uppercase letter for languages
  that support it.
- `name` - All tasks should be named.
- `name` - All plays should be named.
- `name` - Prefix task names in sub-tasks files. (opt-in)
- `name` - Jinja templates should only be at the end of 'name'. This
  helps with the identification of tasks inside the source code when they fail.
  The use of templating inside `name` keys is discouraged as there are multiple
  cases where the rendering of the name template is not possible.

If you want to ignore some of the messages above, you can add any of them to the
`skip_list`.

## name

This rule applies only to included task files that are not named `main.yml`. It
suggests adding the stem of the file as a prefix to the task name.

For example, if you have a task named `Restart server` inside a file named
`tasks/deploy.yml`, this rule suggests renaming it to `deploy | Restart server`,
so it would be easier to identify where it comes from.

For the moment, this sub-rule is just an **opt-in**, so you need to add it to
your `enable_list` to activate it.

!!! note

    This rule was designed by [Red Hat Community of Practice](https://redhat-cop.github.io/automation-good-practices/#_prefix_task_names_in_sub_tasks_files_of_roles). The reasoning behind it being
    that in a complex roles or playbooks with multiple (sub-)tasks file, it becomes
    difficult to understand which task belongs to which file. Adding a prefix, in
    combination with the role’s name automatically added by Ansible, makes it a
    lot easier to follow and troubleshoot a role play.

## Problematic code

```yaml
---
- hosts: localhost # <-- playbook name
  tasks:
    - name: create placefolder file # <-- name due lack of capital letter
      ansible.builtin.command: touch /tmp/.placeholder
```

## Correct code

```yaml
---
- name: Play for creating placeholder
  hosts: localhost
  tasks:
    - name: Create placeholder file
      ansible.builtin.command: touch /tmp/.placeholder
```


# no-changed-when

This rule checks that tasks return changes to results or conditions. Unless
tasks only read information, you should ensure that they return changes in the
following ways:

- Register results or conditions and use the `changed_when` clause.
- Use the `creates` or `removes` argument.

You should always use the `changed_when` clause on tasks that do not naturally
detect if a change has occurred or not. Some of the most common examples are
 and  modules, which run arbitrary commands.

One very common workaround is to use a boolean value like `changed_when: false`
if the task never changes anything or `changed_when: true` if it always changes
something, but you can also use any expressions, including ones that use the
registered result of a task, like in our example below.

This rule also applies to handlers, not only to tasks because they are also
tasks.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Does not handle any output or return codes
      ansible.builtin.command: cat {{ my_file | quote }} # <- Does not handle the command output.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Handle shell output with return code
      ansible.builtin.command: cat {{ my_file | quote }}
      register: my_output # <- Registers the command output.
      changed_when: my_output.rc != 0 # <- Uses the return code to define when the task has changed.
```

:
  https://docs.ansible.com/ansible/latest/collections/ansible/builtin/shell_module.html
:
  https://docs.ansible.com/ansible/latest/collections/ansible/builtin/command_module.html


# no-free-form

This rule identifies any use of
(https://docs.ansible.com/ansible/2.7/user_guide/playbooks_intro.html#action-shorthand)
module calling syntax and asks for switching to the full syntax.

**Free-form** syntax, also known as **inline** or **shorthand**, can produce
subtle bugs. It can also prevent editors and IDEs from providing feedback,
autocomplete and validation for the edited line.

!!! note

    As long you just pass a YAML string that contains a `=` character inside as the
    parameter to the action module name, we consider this as using free-form syntax.
    Be sure you pass a dictionary to the module, so the free-form parsing is never
    triggered.

As `raw` module only accepts free-form, we trigger `no-free-form` only if
we detect the presence of `executable=` inside raw calls. We advise the explicit
use of `args:` for configuring the executable to be run.

This rule can produce messages as:

- `no-free-form` - Free-form syntax is discouraged.
- `no-free-form` - Passing a non-string value to `raw` module is
  neither documented nor supported.

## Problematic code

```yaml
---
- name: Example with discouraged free-form syntax
  hosts: localhost
  tasks:
    - name: Create a placefolder file
      ansible.builtin.command: chdir=/tmp touch foo # <-- don't use free-form
    - name: Use raw to echo
      ansible.builtin.raw: executable=/bin/bash echo foo # <-- don't use executable=
      changed_when: false
```

## Correct code

```yaml
---
- name: Example that avoids free-form syntax
  hosts: localhost
  tasks:
    - name: Create a placefolder file
      ansible.builtin.command:
        cmd: touch foo # <-- ansible will not touch it
        chdir: /tmp
    - name: Use raw to echo
      ansible.builtin.raw: echo foo
      args:
        executable: /bin/bash # <-- explicit is better
      changed_when: false
```


# no-handler

This rule checks for the correct handling of changes to results or conditions.

If a task has a `when: result.changed` condition, it effectively acts as a
(https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html#handlers).
The recommended approach is to use `notify` and move tasks to `handlers`.
If necessary you can silence the rule by add a `# noqa: no-handler` comment at the end of the line.

## Problematic Code

```yaml
---
- name: Example of no-handler rule
  hosts: localhost
  tasks:
    - name: Register result of a task
      ansible.builtin.copy:
        dest: "/tmp/placeholder"
        content: "Ansible made this!"
        mode: 0600
      register: result # <-- Registers the result of the task.
    - name: Second command to run
      ansible.builtin.debug:
        msg: The placeholder file was modified!
      when: result.changed # <-- Triggers the no-handler rule.
```

```yaml
---
# Optionally silences the rule.
when: result.changed # noqa: no-handler
```

## Correct Code

The following code includes the same functionality as the problematic code without recording a `result` variable.

```yaml
---
- name: Example of no-handler rule
  hosts: localhost
  tasks:
    - name: Register result of a task
      ansible.builtin.copy:
        dest: "/tmp/placeholder"
        content: "Ansible made this!"
        mode: 0600
      notify:
        - Second command to run # <-- Handler runs only when the file changes.
  handlers:
    - name: Second command to run
      ansible.builtin.debug:
        msg: The placeholder file was modified!
```


# no-jinja-when

This rule checks conditional statements for Jinja expressions in curly brackets `{{ }}`.
Ansible processes conditionals statements that use the `when`, `failed_when`, and `changed_when` clauses as Jinja expressions.

An Ansible rule is to always use `{{ }}` except with `when` keys.
Using `{{ }}` in conditionals creates a nested expression, which is an Ansible
anti-pattern and does not produce expected results.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Shut down Debian systems
      ansible.builtin.command: /sbin/shutdown -t now
      when: "{{ ansible_facts['os_family'] == 'Debian' }}" # <- Nests a Jinja expression in a conditional statement.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Shut down Debian systems
      ansible.builtin.command: /sbin/shutdown -t now
      when: ansible_facts['os_family'] == "Debian" # <- Uses facts in a conditional statement.
```


# no-log-password

This rule ensures playbooks do not write passwords to logs when using loops.
Always set the `no_log: true` attribute to protect sensitive data.

While most Ansible modules mask sensitive data, using secrets inside a loop can result in those secrets being logged.
Explicitly adding `no_log: true` prevents accidentally exposing secrets.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Log user passwords
      ansible.builtin.user:
        name: john_doe
        comment: John Doe
        uid: 1040
        group: admin
        password: "{{ item }}"
      with_items:
        - wow
      no_log: false # <- Sets the no_log attribute to false.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Do not log user passwords
      ansible.builtin.user:
        name: john_doe
        comment: John Doe
        uid: 1040
        group: admin
        password: "{{ item }}"
      with_items:
        - wow
      no_log: true # <- Sets the no_log attribute to a non-false value.
```


# no-prompting

This rule checks for `vars_prompt` or the `ansible.builtin.pause` module in playbooks.
You should enable this rule to ensure that playbooks can run unattended and in CI/CD pipelines.

This is an opt-in rule.
You must enable it in your Ansible-lint configuration as follows:

```yaml
enable_list:
  - no-prompting
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  vars_prompt: # <- Prompts the user to input credentials.
    - name: username
      prompt: What is your username?
      private: false

    - name: password
      prompt: What is your password?
  tasks:
    - name: Pause for 5 minutes
      ansible.builtin.pause:
        minutes: 5 # <- Pauses playbook execution for a set period of time.
```

## Correct Code

Correct code for this rule is to omit `vars_prompt` and the `ansible.builtin.pause` module from your playbook.


# no-relative-paths

This rule checks for relative paths in the `ansible.builtin.copy` and
`ansible.builtin.template` modules.

Relative paths in a task most often direct Ansible to remote files and
directories on managed nodes. In the `ansible.builtin.copy` and
`ansible.builtin.template` modules, the `src` argument refers to local files and
directories on the control node.

The recommended locations to store files are as follows:

- Use the `files/` folder in the playbook or role directory for the `copy`
  module.
- Use the `templates/` folder in the playbook or role directory for the
  `template` module.

These folders allow you to omit the path or use a sub-folder when specifying
files with the `src` argument.

!!! note

    If resources are outside your Ansible playbook or role directory you should use an absolute path with the `src` argument.

!!! warning

    Do not store resources at the same directory level as your Ansible playbook or tasks files.
    Doing this can result in disorganized projects and cause user confusion when distinguishing between resources of the same type, such as YAML.

See
(https://docs.ansible.com/ansible/latest/playbook_guide/playbook_pathing.html#task-paths)
in the Ansible documentation for more information.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Template a file to /etc/file.conf
      ansible.builtin.template:
        src: ../my_templates/foo.j2 # <- Uses a relative path in the src argument.
        dest: /etc/file.conf
        owner: bin
        group: wheel
        mode: "0644"
```

```yaml
- name: Example playbook
  hosts: all
  vars:
    source_path: ../../my_templates/foo.j2 # <- Sets a variable to a relative path.
  tasks:
    - name: Copy a file to /etc/file.conf
      ansible.builtin.copy:
        src: "{{ source_path }}" # <- Uses the variable in the src argument.
        dest: /etc/foo.conf
        owner: foo
        group: foo
        mode: "0644"
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Template a file to /etc/file.conf
      ansible.builtin.template:
        src: foo.j2 # <- Uses a path from inside templates/ directory.
        dest: /etc/file.conf
        owner: bin
        group: wheel
        mode: "0644"
```

```yaml
- name: Example playbook
  hosts: all
  vars:
    source_path: foo.j2 # <- Uses a path from inside files/ directory.
  tasks:
    - name: Copy a file to /etc/file.conf
      ansible.builtin.copy:
        src: "{{ source_path }}" # <- Uses the variable in the src argument.
        dest: /etc/foo.conf
        owner: foo
        group: foo
        mode: "0644"
```


# no-same-owner

This rule checks that the owner and group do not transfer across hosts.

In many cases the owner and group on remote hosts do not match the owner and group assigned to source files.
Preserving the owner and group during transfer can result in errors with permissions or leaking sensitive information.

When you synchronize files, you should avoid transferring the owner and group by setting `owner: false` and `group: false` arguments.
When you unpack archives with the `ansible.builtin.unarchive` module you should set the `--no-same-owner` option.

This is an opt-in rule.
You must enable it in your Ansible-lint configuration as follows:

```yaml
enable_list:
  - no-same-owner
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Synchronize conf file
      ansible.posix.synchronize:
        src: /path/conf.yaml
        dest: /path/conf.yaml # <- Transfers the owner and group for the file.
    - name: Extract tarball to path
      ansible.builtin.unarchive:
        src: "{{ file }}.tar.gz"
        dest: /my/path/ # <- Transfers the owner and group for the file.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Synchronize conf file
      ansible.posix.synchronize:
        src: /path/conf.yaml
        dest: /path/conf.yaml
        owner: false
        group: false # <- Does not transfer the owner and group for the file.
    - name: Extract tarball to path
      ansible.builtin.unarchive:
        src: "{{ file }}.tar.gz"
        dest: /my/path/
        extra_opts:
          - --no-same-owner # <- Does not transfer the owner and group for the file.
```


# no-tabs

This rule checks for the tab character. The `\t` tab character can result in
unexpected display or formatting issues. You should always use spaces instead of
tabs.

!!! note

    This rule does not trigger alerts for tab characters in the ``ansible.builtin.lineinfile`` module.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Do not trigger the rule
      ansible.builtin.lineinfile:
        path: some.txt
        regexp: '^\t$'
        line: 'string with \t inside'
    - name: Trigger the rule with a debug message
      ansible.builtin.debug:
        msg: "Using the \t character can cause formatting issues." # <- Includes the tab character.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Do not trigger the no-tabs rule
      ansible.builtin.debug:
        msg: "Using space characters avoids formatting issues."
```


# only-builtins

This rule checks that playbooks use actions from the `ansible.builtin` collection only.

This is an opt-in rule.
You must enable it in your Ansible-lint configuration as follows:

```yaml
enable_list:
  - only-builtins
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: all
  tasks:
    - name: Deploy a Helm chart for Prometheus
      kubernetes.core.helm: # <- Uses a non-builtin collection.
        name: test
        chart_ref: stable/prometheus
        release_namespace: monitoring
        create_namespace: true
```

## Correct Code

```yaml
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Run a shell command
      ansible.builtin.shell: echo This playbook uses actions from the builtin collection only.
```


# package-latest

This rule checks that package managers install software in a controlled, safe manner.

Package manager modules, such as `ansible.builtin.yum`, include a `state` parameter that configures how Ansible installs software.
In production environments, you should set `state` to `present` and specify a target version to ensure that packages are installed to a planned and tested version.

Setting `state` to `latest` not only installs software, it performs an update and installs additional packages.
This can result in performance degradation or loss of service.
If you do want to update packages to the latest version, you should also set the `update_only` parameter to `true` to avoid installing additional packages.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Install Ansible
      ansible.builtin.yum:
        name: ansible
        state: latest # <- Installs the latest package.

    - name: Install Ansible-lint
      ansible.builtin.pip:
        name: ansible-lint
      args:
        state: latest # <- Installs the latest package.

    - name: Install some-package
      ansible.builtin.package:
        name: some-package
        state: latest # <- Installs the latest package.

    - name: Install Ansible with update_only to false
      ansible.builtin.yum:
        name: sudo
        state: latest
        update_only: false # <- Updates and installs packages.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Install Ansible
      ansible.builtin.yum:
        name: ansible-2.12.7.0
        state: present # <- Pins the version to install with yum.

    - name: Install Ansible-lint
      ansible.builtin.pip:
        name: ansible-lint
      args:
        state: present
        version: 5.4.0 # <- Pins the version to install with pip.

    - name: Install some-package
      ansible.builtin.package:
        name: some-package
        state: present # <- Ensures the package is installed.

    - name: Update Ansible with update_only to true
      ansible.builtin.yum:
        name: sudo
        state: latest
        update_only: true # <- Updates but does not install additional packages.
```


## parser-error

**AnsibleParserError.**

Ansible parser fails; this usually indicates an invalid file.

# partial-become

This rule checks that privilege escalation is activated when changing users.

To perform an action as a different user with the `become_user` directive, you
must set `become: true`.

!!! warning

    While Ansible inherits have of `become` and `become_user` from upper levels,
    like play level or command line, we do not look at these values. This rule
    requires you to be explicit and always define both in the same place, mainly
    in order to prevent accidents when some tasks are moved from one location to
    another one.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Start the httpd service as the apache user
      ansible.builtin.service:
        name: httpd
        state: started
        become_user: apache # <- Does not change the user because "become: true" is not set.
```

## Correct Code

```yaml
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Start the httpd service as the apache user
      ansible.builtin.service:
        name: httpd
        state: started
        become: true # <- Activates privilege escalation.
        become_user: apache # <- Changes the user with the desired privileges.
```


# playbook-extension

This rule checks the file extension for playbooks is either `.yml` or `.yaml`.
Ansible playbooks are expressed in YAML format with minimal syntax.

The [YAML syntax](https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html#yaml-syntax) reference provides additional detail.

## Problematic Code

This rule is triggered if Ansible playbooks do not have a file extension or use an unsupported file extension such as `playbook.json` or `playbook.xml`.

## Correct Code

Save Ansible playbooks as valid YAML with the `.yml` or `.yaml` file extension.


# risky-file-permissions

This rule is triggered by various modules that could end up creating new files
on disk with permissions that might be too open, or unpredictable. Please read
the documentation of each module carefully to understand the implications of
using different argument values, as these make the difference between using the
module safely or not. The fix depends on each module and also your particular
situation.

Some modules have a `create` argument that defaults to `true`. For those you
either need to set `create: false` or provide some permissions like `mode: 0600`
to make the behavior predictable and not dependent on the current system
settings.

Modules that are checked:

- [`ansible.builtin.assemble`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/assemble_module.html)
- [`ansible.builtin.copy`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html)
- [`ansible.builtin.file`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/file_module.html)
- [`ansible.builtin.get_url`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/get_url_module.html)
- [`ansible.builtin.replace`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/replace_module.html)
- [`ansible.builtin.template`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html)
- [`community.general.archive`](https://docs.ansible.com/ansible/latest/collections/community/general/archive_module.html)
- [`community.general.ini_file`](https://docs.ansible.com/ansible/latest/collections/community/general/ini_file_module.html)

!!! warning

    This rule does not take (https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_module_defaults.html) configuration into account.
    There are currently no plans to implement this feature because changing task location can also change task behavior.

## Problematic code

```yaml
---
- name: Unsafe example of using ini_file
  community.general.ini_file:
    path: foo
    create: true
```

## Correct code

```yaml
---
- name: Safe example of using ini_file (1st solution)
  community.general.ini_file:
    path: foo
    create: false  # prevents creating a file with potentially insecure permissions

- name: Safe example of using ini_file (2nd solution)
  community.general.ini_file:
    path: foo
    mode: 0600  # explicitly sets the desired permissions, to make the results predictable

- name: Safe example of using copy (3rd solution)
  ansible.builtin.copy:
    src: foo
    dest: bar
    mode: preserve   # copy has a special mode that sets the same permissions as the source file
```


# risky-octal

This rule checks that octal file permissions are strings that contain a leading
zero or are written in
(https://www.gnu.org/software/findutils/manual/html_node/find_html/Symbolic-Modes.html),
such as `u+rwx` or `u=rw,g=r,o=r`.

Using integers or octal values in YAML can result in unexpected behavior. For
example, the YAML loader interprets `0644` as the decimal number `420` but
putting `644` there will produce very different results.

Modules that are checked:

- [`ansible.builtin.assemble`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/assemble_module.html)
- [`ansible.builtin.copy`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html)
- [`ansible.builtin.file`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/file_module.html)
- [`ansible.builtin.replace`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/replace_module.html)
- [`ansible.builtin.template`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html)

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Unsafe example of declaring Numeric file permissions
      ansible.builtin.file:
        path: /etc/foo.conf
        owner: foo
        group: foo
        mode: 644
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Safe example of declaring Numeric file permissions (1st solution)
      ansible.builtin.file:
        path: /etc/foo.conf
        owner: foo
        group: foo
        mode: "0644" # <- quoting and the leading zero will prevent surprises
        # "0o644" is also a valid alternative.
```


# risky-shell-pipe

This rule checks for the bash `pipefail` option with the Ansible `shell` module.

You should always set `pipefail` when piping output from one command to another.
The return status of a pipeline is the exit status of the command. The
`pipefail` option ensures that tasks fail as expected if the first command
fails.

As this requirement does apply to PowerShell, for shell commands that have
`pwsh` inside `executable` attribute, this rule will not trigger.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  tasks:
    - name: Pipeline without pipefail
      ansible.builtin.shell: false | cat
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  become: false
  tasks:
    - name: Pipeline with pipefail
      ansible.builtin.shell: set -o pipefail && false | cat

    - name: Pipeline with pipefail, multi-line
      ansible.builtin.shell: |
        set -o pipefail # <-- adding this will prevent surprises
        false | cat
```


# role-name

This rule checks role names to ensure they conform with requirements.

Role names must contain only lowercase alphanumeric characters and the underscore `_` character.
Role names must also start with an alphabetic character.

For more information see the (https://docs.ansible.com/ansible/devel/dev_guide/developing_collections_structure.html#roles-directory) topic in Ansible documentation.

`role-name` message tells you to avoid using paths when importing roles.
You should only rely on Ansible's ability to find the role and refer to them
using fully qualified names.

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  roles:
    - 1myrole # <- Does not start with an alphabetic character.
    - myrole2[*^ # <- Contains invalid special characters.
    - myRole_3 # <- Contains uppercase alphabetic characters.
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  roles:
    - myrole1 # <- Starts with an alphabetic character.
    - myrole2 # <- Contains only alphanumeric characters.
    - myrole_3 # <- Contains only lowercase alphabetic characters.
```


# run-once

This rule warns against the use of `run_once` when the `strategy` is set to
`free`.

This rule can produce the following messages:

- `run-once`: Play uses `strategy: free`.
- `run-once`: Using `run_once` may behave differently if the `strategy` is
  set to `free`.

For more information see the following topics in Ansible documentation:

- (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/free_strategy.html#free-strategy)
- (https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html#selecting-a-strategy)
- (https://docs.ansible.com/ansible/latest/reference_appendices/playbooks_keywords.html)

!!! warning

    The reason for the existence of this rule is for reminding users that `run_once`
    is not providing any warranty that the task will run only once.
    This rule will always trigger regardless of the value configured inside the 'strategy' field. That is because the effective value used at runtime can be different than the value inside the file. For example, ansible command line arguments can alter it.

It is perfectly fine to add `# noqa: run-once` to mark the warning as
acknowledged and ignored.

## Problematic Code

```yaml
---
- name: "Example with run_once"
  hosts: all
  strategy: free # <-- avoid use of strategy as free
  gather_facts: false
  tasks:
    - name: Task with run_once
      ansible.builtin.debug:
        msg: "Test"
      run_once: true # <-- avoid use of strategy as free at play level when using run_once at task level
```

## Correct Code

```yaml
- name: "Example without run_once"
  hosts: all
  gather_facts: false
  tasks:
    - name: Task without run_once
      ansible.builtin.debug:
        msg: "Test"
```

```yaml
- name: "Example of using run_once with strategy other than free"
  hosts: all
  strategy: linear
  # strategy: free # noqa: run-once (if using strategy: free can skip it this way)
  gather_facts: false
  tasks: # <-- use noqa to disable rule violations for specific tasks
    - name: Task with run_once # noqa: run-once
      ansible.builtin.debug:
        msg: "Test"
      run_once: true
```


# sanity

This rule checks the `tests/sanity/ignore-x.x.txt` file for disallowed ignores.
This rule is extremely opinionated and enforced by Partner Engineering. The
currently allowed ruleset is subject to change, but is starting at a minimal
number of allowed ignores for maximum test enforcement. Any commented-out ignore
entries are not evaluated.

This rule can produce messages like:

- `sanity` - Ignore file contains {test} at line {line_num},
  which is not a permitted ignore.
- `sanity` - Ignore file entry at {line_num} is formatted
  incorrectly. Please review.

Currently allowed ignores for all Ansible versions are:

- `validate-modules:missing-gplv3-license`
- `action-plugin-docs`
- `import-2.6`
- `import-2.6!skip`
- `import-2.7`
- `import-2.7!skip`
- `import-3.5`
- `import-3.5!skip`
- `compile-2.6`
- `compile-2.6!skip`
- `compile-2.7`
- `compile-2.7!skip`
- `compile-3.5`
- `compile-3.5!skip`

Additionally allowed ignores for Ansible 2.9 are:
- `validate-modules:deprecation-mismatch`
- `validate-modules:invalid-documentation`

## Problematic code

```
# tests/sanity/ignore-x.x.txt
plugins/module_utils/ansible_example_module.py import-3.6!skip
```

```
# tests/sanity/ignore-x.x.txt
plugins/module_utils/ansible_example_module.oops-3.6!skip
```

## Correct code

```
# tests/sanity/ignore-x.x.txt
plugins/module_utils/ansible_example_module.py import-2.7!skip
```


# schema

The `schema` rule validates Ansible metadata files against JSON schemas. These
schemas ensure the compatibility of Ansible syntax content across versions.

This `schema` rule is **mandatory**. You cannot use inline `noqa` comments to
ignore it.

Ansible-lint validates the `schema` rule before processing other rules. This
prevents unexpected syntax from triggering multiple rule violations.

## Validated schema

Ansible-lint currently validates several schemas that are maintained in separate
projects and updated independently to ansible-lint.

> Report bugs related to schema in their respective repository and not in the
> ansible-lint project.

Maintained in the (https://github.com/ansible/ansible-lint)
project:

- `schema` validates
  (https://github.com/ansible/ansible-lint/blob/main/src/ansiblelint/schemas/ansible-lint-config.json)
- `schema` validates
  (https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#specification-format)
  which is a little bit different than the module argument spec.
- `schema` validates
  (https://docs.ansible.com/automation-controller/latest/html/userguide/execution_environments.html)
- `schema` validates
  (https://docs.ansible.com/ansible/latest/dev_guide/collections_galaxy_meta.html).
- `schema` validates
  (https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html)
  that match `inventory/*.yml`.
- `schema` validates
  (https://docs.ansible.com/ansible/devel/dev_guide/developing_collections_structure.html#meta-directory-and-runtime-yml)
  that matches `meta/runtime.yml`
- `schema` validates metadata for roles that match `meta/main.yml`. See
  (https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-dependencies)
  or
  (https://github.com/ansible/ansible/blob/devel/lib/ansible/playbook/role/metadata.py#L79))
  for details.
- `schema` validates Ansible playbooks.
- `schema` validates Ansible
  (https://docs.ansible.com/ansible/latest/galaxy/user_guide.html#install-multiple-collections-with-a-requirements-file)
  files that match `requirements.yml`.
- `schema` validates Ansible task files that match `tasks/**/*.yml`.
- `schema` validates Ansible
  (https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html)
  that match `vars/*.yml` and `defaults/*.yml`.

Maintained in the
(https://github.com/ansible/ansible-navigator) project:

- `schema` validates
  (https://github.com/ansible/ansible-navigator/blob/main/src/ansible_navigator/data/ansible-navigator.json)

## schema

For `meta/main.yml` files, Ansible-lint requires a `galaxy_info.standalone`
property that clarifies if a role is an old standalone one or a new one,
collection based:

```yaml
galaxy_info:
  standalone: true # <-- this is a standalone role (not part of a collection)
```

Ansible-lint requires the `standalone` key to avoid confusion and provide more
specific error messages. For example, the `meta` schema will require some
properties only for standalone roles or prevent the use of some properties that
are not supported by collections.

You cannot use an empty `meta/main.yml` file or use only comments in the
`meta/main.yml` file.

## schema

These errors usually look like "foo was moved to bar in 2.10" and indicate
module moves between Ansible versions.


# syntax-check

Our linter runs `ansible-playbook --syntax-check` on all playbooks, and if any
of these reports a syntax error, this stops any further processing of these
files.

This error **cannot be disabled** due to being a prerequisite for other steps.
You can exclude these files from linting, but it is better to make sure they can
be loaded by Ansible. This is often achieved by editing the inventory file
and/or `ansible.cfg` so ansible can load required variables.

If undefined variables cause the failure, you can use the jinja `default()`
filter to provide fallback values, like in the example below.

This rule is among the few `unskippable` rules that cannot be added to
`skip_list` or `warn_list`. One possible workaround is to add the entire file to
the `exclude_paths`. This is a valid approach for special cases, like testing
fixtures that are invalid on purpose.

One of the most common sources of errors is a failure to assert the presence of
various variables at the beginning of the playbook.

This rule can produce messages like below:

- `syntax-check` is raised when a playbook file has no content.

## Problematic code

```yaml
---
- name:
    Bad use of variable inside hosts block (wrong assumption of it being
    defined)
  hosts: "{{ my_hosts }}"
  tasks: []
```

## Correct code

```yaml
---
- name: Good use of variable inside hosts, without assumptions
  hosts: "{{ my_hosts | default([]) }}"
  tasks: []
```


# var-naming

This rule checks variable names to ensure they conform with requirements.

Variable names must contain only lowercase alphanumeric characters and the
underscore `_` character. Variable names must also start with either an
alphabetic or underscore `_` character.

For more information see the  topic in
Ansible documentation and [Naming things (Good Practices for Ansible)].

You should also be fully aware of , also known as
magic variables, especially as most of them can only be read. While Ansible will
just ignore any attempt to set them, the linter will notify the user, so they
would not be confused about a line that does not effectively do anything.

Possible errors messages:

- `var-naming`: Variables names must be strings.
- `var-naming`: Variables names must be ASCII.
- `var-naming`: Variables names must not be Python keywords.
- `var-naming`: Variables names must not contain jinja2 templating.
- `var-naming`: Variables names should match ... regex.
- `var-naming`: Variables names from within roles should use
  `role_name_` as a prefix.
- `var-naming`: Variables names must not be Ansible reserved names.
- `var-naming`: This special variable is read-only.

!!! note

    When using `include_role` or `import_role` with `vars`, vars should start
    with included role name prefix. As this role might not be compliant
    with this rule yet, you might need to temporarily disable this rule using
    a `# noqa: var-naming` comment.

## Settings

This rule behavior can be changed by altering the below settings:

```yaml
# .ansible-lint
var_naming_pattern: "^*$"
```

## Problematic Code

```yaml
---
- name: Example playbook
  hosts: localhost
  vars:
    CamelCase: true # <- Contains a mix of lowercase and uppercase characters.
    ALL_CAPS: bar # <- Contains only uppercase characters.
    v@r!able: baz # <- Contains special characters.
    hosts: [] # <- hosts is an Ansible reserved name
    role_name: boo # <-- invalid as being Ansible special magic variable
```

## Correct Code

```yaml
---
- name: Example playbook
  hosts: localhost
  vars:
    lowercase: true # <- Contains only lowercase characters.
    no_caps: bar # <- Does not contains uppercase characters.
    variable: baz # <- Does not contain special characters.
    my_hosts: [] # <- Does not use a reserved names.
    my_role_name: boo
```

: https://redhat-cop.github.io/automation-good-practices/#_naming_things
:
  https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#creating-valid-variable-names
:
  https://docs.ansible.com/ansible/latest/reference_appendices/special_variables.html


# warning

`warning` is a special type of internal rule that is used to report generic
runtime warnings found during execution. As stated by its name, they are not
counted as errors, so they do not influence the final outcome.

- `warning` indicates that you are using
  `(https://docs.ansible.com/ansible/latest/collections/ansible/builtin/raw_module.html#ansible-collections-ansible-builtin-raw-module)`
  module with non-string arguments, which is not supported by Ansible.


# yaml

This rule checks YAML syntax and is an implementation of `yamllint`.

You can disable YAML syntax violations by adding `yaml` to the `skip_list` in
your Ansible-lint configuration as follows:

```yaml
skip_list:
  - yaml
```

For more fine-grained control, disable violations for specific rules using tag
identifiers in the `yaml` format as follows:

```yaml
skip_list:
  - yaml
  - yaml
```

If you want Ansible-lint to report YAML syntax violations as warnings, and not
fatal errors, add tag identifiers to the `warn_list` in your configuration, for
example:

```yaml
warn_list:
  - yaml
```

!!! warning

    You cannot use `tags: ` to disable this rule but you can
    use (https://yamllint.readthedocs.io/en/stable/disable_with_comments.html#disabling-checks-for-all-or-part-of-the-file) for tuning it.

See the
(https://yamllint.readthedocs.io/en/stable/rules.html)
for more information.

Some of the detailed error codes that you might see are:

- `yaml` - _too few spaces inside empty brackets_, or _too many spaces
  inside brackets_
- `yaml` - _too many spaces before colon_, or _too many spaces after
  colon_
- `yaml` - _too many spaces before comma_, or _too few spaces after
  comma_
- `yaml` - _Comment not indented like content_
- `yaml` - _Too few spaces before comment_, or _Missing starting space
  in comment_
- `yaml` - _missing document start "---"_ or _found forbidden
  document start "---"_
- `yaml` - _too many blank lines (...> ...)_
- `yaml` - _Wrong indentation: expected ... but found ..._
- `yaml` - _Duplication of key "..." in mapping_
- `yaml` - _Line too long (... > ... characters)_
- `yaml` - _No new line character at the end of file_
- `yaml`: forbidden implicit or explicit (#octals) value
- `yaml` - YAML syntax is broken
- `yaml` - Spaces are found at the end of lines
- `yaml` - _Truthy value should be one of ..._

## Octals

As [YAML specification] regarding octal values changed at least 3 times in
[1.1], [1.2.0] and [1.2.2] we now require users to always add quotes around
octal values, so the YAML loaders will all load them as strings, providing a
consistent behavior. This is also safer as JSON does not support octal values
either.

By default, yamllint does not check for octals but our custom default ruleset
for it does check these. If for some reason, you do not want to follow our
defaults, you can create a `.yamllint` file in your project and this will take
precedence over our defaults.

## Additional Information for Multiline Strings

Adhering to yaml rule, for writing multiline strings we recommend using Block Style Indicator: literal style indicated by a pipe (|) or folded style indicated by a right angle bracket (>), instead of escaping the newlines with backslashes.
Reference  for writing multiple line strings in yaml.

## Problematic code

```yaml
# Missing YAML document start.
foo: 0777 # <-- yaml
foo2: 0o777 # <-- yaml
foo2: ... # <-- yaml
bar: ...       # <-- yaml
```

## Correct code

```yaml
---
foo: "0777" # <-- Explicitly quoting octal is less risky.
foo2: "0o777" # <-- Explicitly quoting octal is less risky.
bar: ... # Correct comment indentation.
```

[1.1]: https://yaml.org/spec/1.1/
[1.2.0]: https://yaml.org/spec/1.2.0/
[1.2.2]: https://yaml.org/spec/1.2.2/
: https://yaml.org/
: https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html#yaml-basics

