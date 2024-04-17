
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

# secure stoage

It's important to encrypt data at-rest to prevent and reduce the impact of data leaks.

This rule ensures that the block storage associated with an RDS instance is encrypted.

## Problematic Code

```yaml
---
- name: test playbook
  hosts: all
  tasks:
    - name: deploy engine RDS in region
      become: yes
      aws_rds_instance:
        name: name
        engine: engine
        master_username: myuser
        master_password: "{{ _master_password_ }}"
        instance_class: db.t2.micro
        region: region
        state: present
```

## Correct Code

```yaml
---
- name: test playbook
  hosts: all
  tasks:
    - name: deploy engine RDS in region
      become: yes
      aws_rds_instance:
        name: name
        engine: engine
        master_username: myuser
        master_password: "{{ _master_password_ }}"
        instance_class: db.t2.micro
        region: region
        state: present
        storage_encrypted: true
```
