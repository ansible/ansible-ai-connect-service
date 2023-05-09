FROM registry.access.redhat.com/ubi9/ubi:latest

ARG IMAGE_TAGS=image-tags-not-defined
ARG GIT_COMMIT=git-commit-not-defined

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
    postgresql \
    less

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y inotify-tools && \
    dnf remove -y epel-release && \
    dnf clean all

RUN /usr/bin/python3 -m pip --no-cache-dir install supervisor
RUN /usr/bin/python3 -m venv /var/www/venv
COPY requirements.txt /var/www/
COPY model-cache /var/www/model-cache
# See: https://github.com/advisories/GHSA-r9hx-vwmv-q579
RUN /var/www/venv/bin/pip install --upgrade 'setuptools>=65.5.1'
RUN /var/www/venv/bin/python3 -m pip --no-cache-dir install -r/var/www/requirements.txt
RUN echo "/var/www/ansible_wisdom" > /var/www/venv/lib/python3.9/site-packages/project.pth

COPY ansible_wisdom /var/www/ansible_wisdom
RUN echo -e "\
[ansible-wisdom-service]\n\
IMAGE_TAGS = ${IMAGE_TAGS}\n\
GIT_COMMIT = ${GIT_COMMIT}\n\
" > /var/www/ansible_wisdom/version_info.ini

COPY tools/scripts/launch-wisdom.sh /usr/bin/launch-wisdom.sh
COPY tools/scripts/auto-reload.sh /usr/bin/auto-reload.sh
COPY tools/configs/nginx.conf /etc/nginx/nginx.conf
COPY tools/configs/nginx-wisdom.conf /etc/nginx/conf.d/wisdom.conf
COPY tools/scripts/wisdom-manage /usr/bin/wisdom-manage
COPY tools/configs/uwsgi.ini /etc/wisdom/uwsgi.ini
COPY tools/configs/supervisord.conf /etc/supervisor/supervisord.conf
COPY tools/scripts/install-ari-rule-requirements.sh /usr/bin/install-ari-rule-requirements.sh
COPY ari /etc/ari

RUN for dir in \
      /var/log/supervisor \
      /var/run/supervisor \
      /var/www/wisdom \
      /var/www/model-cache \
      /var/log/nginx \
      /etc/ari \
      /etc/ansible ; \
    do mkdir -p $dir ; chgrp -R 0 $dir; chmod -R g=u $dir ; done && \
    echo "\setenv PAGER 'less -SXF'" > /etc/psqlrc
RUN /usr/bin/install-ari-rule-requirements.sh
ENV ANSIBLE_HOME=/etc/ansible
WORKDIR /var/www

USER 1000
EXPOSE 8000

CMD /usr/bin/launch-wisdom.sh
