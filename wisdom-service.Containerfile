FROM --platform=linux/amd64 registry.access.redhat.com/ubi9/ubi:latest

ARG IMAGE_TAGS=image-tags-not-defined
ARG GIT_COMMIT=git-commit-not-defined

ARG DJANGO_SETTINGS_MODULE=ansible_wisdom.main.settings.production

ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

ENV PROMETHEUS_MULTIPROC_DIR=/var/run/django_metrics

ENV BUILD_PATH=/var/www/wisdom/public/static/console

# Install dependencies
RUN dnf install -y \
    git \
    python3-devel \
    gcc \
    libpq \
    libpq-devel \
    python3 \
    python3-pip \
    postgresql \
    less \
    npm

RUN dnf module install -y nginx/common

# Copy the ansible_wisdom package files
COPY requirements.txt /var/www/ansible-wisdom-service/requirements.txt
COPY setup.cfg /var/www/ansible-wisdom-service/setup.cfg
COPY pyproject.toml /var/www/ansible-wisdom-service/pyproject.toml
COPY README.md /var/www/ansible-wisdom-service/README.md
COPY ansible_wisdom /var/www/ansible-wisdom-service/ansible_wisdom
COPY main /var/www/ansible-wisdom-service/main

# Compile Python/Django application
RUN /usr/bin/python3 -m pip --no-cache-dir install supervisor
RUN /usr/bin/python3 -m venv /var/www/venv
ENV PATH="/var/www/venv/bin:${PATH}"
COPY model-cache /var/www/model-cache
RUN /var/www/venv/bin/python3 -m pip --no-cache-dir install -r/var/www/ansible-wisdom-service/requirements.txt
RUN /var/www/venv/bin/python3 -m pip --no-cache-dir install -e/var/www/ansible-wisdom-service/
RUN mkdir /var/run/uwsgi

RUN echo -e "\
{\n\
  \"imageTags\": \"${IMAGE_TAGS}\", \n\
  \"gitCommit\": \"${GIT_COMMIT}\" \n\
}\n\
" > /var/www/ansible-wisdom-service/ansible_wisdom/version_info.json

# Compile React/TypeScript Console application
# Copy each source folder individually to avoid copying 'node_modules'
COPY ansible_wisdom_console_react/config /tmp/ansible_wisdom_console_react/config
COPY ansible_wisdom_console_react/public /tmp/ansible_wisdom_console_react/public
COPY ansible_wisdom_console_react/scripts /tmp/ansible_wisdom_console_react/scripts
COPY ansible_wisdom_console_react/src /tmp/ansible_wisdom_console_react/src
COPY ansible_wisdom_console_react/package.json /tmp/ansible_wisdom_console_react/package.json
COPY ansible_wisdom_console_react/package-lock.json /tmp/ansible_wisdom_console_react/package-lock.json
COPY ansible_wisdom_console_react/tsconfig.json /tmp/ansible_wisdom_console_react/tsconfig.json
RUN npm --prefix /tmp/ansible_wisdom_console_react ci
RUN npm --prefix /tmp/ansible_wisdom_console_react run build

# Copy configuration files
COPY tools/scripts/launch-wisdom.sh /usr/bin/launch-wisdom.sh
COPY tools/configs/nginx.conf /etc/nginx/nginx.conf
COPY tools/configs/nginx-wisdom.conf /etc/nginx/conf.d/wisdom.conf
COPY tools/configs/uwsgi.ini /etc/wisdom/uwsgi.ini
COPY tools/configs/supervisord.conf /etc/supervisor/supervisord.conf
COPY tools/scripts/install-ari-rule-requirements.sh /usr/bin/install-ari-rule-requirements.sh
COPY ari /etc/ari

# Set permissions
RUN for dir in \
      /var/log/supervisor \
      /var/run/supervisor \
      /var/run/uwsgi \
      /var/www/wisdom \
      /var/www/model-cache \
      /var/log/nginx \
      /etc/ari \
      /etc/ansible \
      /var/run/django_metrics \
      /var/www/.cache \
      ; \
    do mkdir -p $dir ; chgrp -R 0 $dir; chmod -R g=u $dir ; done && \
    echo "\setenv PAGER 'less -SXF'" > /etc/psqlrc

# Install ARI rules
RUN /usr/bin/install-ari-rule-requirements.sh

# Launch!
ENV ANSIBLE_HOME=/etc/ansible
WORKDIR /var/www

USER 1000
EXPOSE 8000

CMD /usr/bin/launch-wisdom.sh
