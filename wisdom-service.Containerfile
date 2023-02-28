FROM registry.access.redhat.com/ubi9/ubi:latest

ARG DJANGO_SETTINGS_MODULE=main.settings.production

ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

RUN dnf install -y \
    git \
    python3-devel \
    gcc \
    libpq \
    libpq-devel \
    python3 \
    python3-pip \
    nginx \
    less

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y inotify-tools && \
    dnf remove -y epel-release && \
    dnf clean all

COPY ansible_wisdom /var/www/ansible_wisdom
COPY tools/scripts/launch-wisdom.sh /usr/bin/launch-wisdom.sh
COPY tools/scripts/auto-reload.sh /usr/bin/auto-reload.sh
COPY tools/configs/nginx.conf /etc/nginx/nginx.conf
COPY tools/configs/nginx-wisdom.conf /etc/nginx/conf.d/wisdom.conf
COPY tools/configs/uwsgi.ini /etc/wisdom/uwsgi.ini
COPY tools/configs/supervisord.conf /etc/supervisor/supervisord.conf
COPY requirements.txt /var/www/
COPY ari /etc/ari

RUN /usr/bin/python3 -m pip --no-cache-dir install supervisor
RUN for dir in \
      /var/log/supervisor \
      /var/run/supervisor \
      /var/log/nginx \
      /etc/ari \
      /etc/ansible ; \
    do mkdir -p $dir ; chgrp -R 0 $dir; chmod -R g=u $dir ; done
ENV ANSIBLE_HOME=/etc/ansible
RUN /usr/bin/python3 -m venv /var/www/venv
RUN /var/www/venv/bin/python3 -m pip --no-cache-dir install -r/var/www/requirements.txt
RUN echo "/var/www/ansible_wisdom" > /var/www/venv/lib/python3.9/site-packages/project.pth
WORKDIR /var/www

USER 1000
EXPOSE 8000

CMD /usr/bin/launch-wisdom.sh
