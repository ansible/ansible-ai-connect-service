
# Default Rules

(lint_default_rules)=

Below you can see the list of default rules Ansible Lint use to evaluate playbooks and roles:



# dnf

This rule replaces use of the apt module with the dnf module when installing packages on Ubuntu.

The rule validation will check if the module is apt and will replace it with dnf.


## Problematic Code

```yaml
---
- name: Playbook to install {package}
  hosts: localhost
  tasks:
    - name: install {package} on Ubuntu
      apt:
        name: {package}
        state: present
```

## Correct Code

```yaml
---
- name: Playbook to install {package}
  hosts: localhost
  tasks:
    - name: install {package} on Ubuntu
      dnf:
        name: {package}
        state: present
```

# passwd file permissions

This rule changes ensures that the /etc/passwd file has the correct permissions.

The rule validation will check if permissions are not 0600 and update them to match.


## Problematic Code

```yaml
---
- name: Playbook to set permissions on /etc/passwd
  hosts: localhost
  tasks:
    - name: set permission on /etc/passwd
      file:
        path: /etc/passwd
        mode: '0644'
```

## Correct Code

```yaml
---
- name: Playbook to set permissions on /etc/passwd
  hosts: localhost
  tasks:
    - name: set permission on /etc/passwd
      file:
        path: /etc/passwd
        mode: '0600'
```