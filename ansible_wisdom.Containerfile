FROM registry.access.redhat.com/ubi9/ubi:9.1.0-1646.1669627755

ARG DJANGO_SETTINGS_MODULE=main.settings.development

RUN dnf install -y python39 python3-pip

COPY ansible_wisdom /opt/ansible_wisdom
COPY requirements.txt /tmp

EXPOSE 8000

RUN /usr/bin/python3 -m pip install -r/opt/ansible_wisdom/requirements.txt && python3 /opt/ansible_wisdom/manage.py migrate && rm -r /root/.cache
WORKDIR /opt
ENTRYPOINT ["/usr/bin/python3", "/opt/ansible_wisdom/manage.py", "runserver", "0.0.0.0:8000"]
