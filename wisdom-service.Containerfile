FROM registry.access.redhat.com/ubi9/ubi:latest AS production

ARG IMAGE_TAGS=image-tags-not-defined
ARG GIT_COMMIT=git-commit-not-defined

ARG DJANGO_SETTINGS_MODULE=ansible_ai_connect.main.settings.production

ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

ENV PROMETHEUS_MULTIPROC_DIR=/var/run/django_metrics

ENV BUILD_PATH=/var/www/wisdom/public/static/console

ENV UWSGI_PROCESSES=10

# Install dependencies
RUN dnf module enable nodejs:18 nginx:1.22 -y && \
    dnf install -y \
    git \
    python3.12-devel \
    gcc \
    libpq \
    libpq-devel \
    python3.12 \
    python3.12-pip \
    postgresql \
    less \
    npm \
    nginx \
    rsync

# Copy the ansible_wisdom package files
COPY requirements-x86_64.txt /var/www/ansible-ai-connect-service/
COPY requirements-aarch64.txt /var/www/ansible-ai-connect-service/
COPY requirements.txt /var/www/ansible-ai-connect-service/
COPY setup.cfg /var/www/ansible-ai-connect-service/setup.cfg
COPY pyproject.toml /var/www/ansible-ai-connect-service/pyproject.toml
COPY README.md /var/www/ansible-ai-connect-service/README.md
COPY ansible_ai_connect /var/www/ansible-ai-connect-service/ansible_ai_connect

# Compile Python/Django application
RUN /usr/bin/python3.12 -m pip --no-cache-dir install supervisor
RUN /usr/bin/python3.12 -m venv /var/www/venv
ENV PATH="/var/www/venv/bin:${PATH}"

# Address GHSA-79v4-65xg-pq4g and the fact jwcrypto prevent us from pulling cryptography 44.0.1
# Please remove once jwcrypto and cryptography can be both upgraded
RUN dnf install -y openssl-devel
RUN /var/www/venv/bin/python3.12 -m pip --no-cache-dir install --no-binary=all cryptography==43.0.1

RUN /var/www/venv/bin/python3.12 -m pip --no-cache-dir install -r/var/www/ansible-ai-connect-service/requirements.txt
RUN /var/www/venv/bin/python3.12 -m pip --no-cache-dir install -e/var/www/ansible-ai-connect-service/
RUN mkdir /var/run/uwsgi /var/run/daphne

RUN echo -e "\
{\n\
  \"imageTags\": \"${IMAGE_TAGS}\", \n\
  \"gitCommit\": \"${GIT_COMMIT}\" \n\
}\n\
" > /var/www/ansible-ai-connect-service/ansible_ai_connect/version_info.json

# Compile React/TypeScript Console application
# Copy each source folder individually to avoid copying 'node_modules'
COPY ansible_ai_connect_admin_portal/config /tmp/ansible_ai_connect_admin_portal/config
COPY ansible_ai_connect_admin_portal/public /tmp/ansible_ai_connect_admin_portal/public
COPY ansible_ai_connect_admin_portal/scripts /tmp/ansible_ai_connect_admin_portal/scripts
COPY ansible_ai_connect_admin_portal/src /tmp/ansible_ai_connect_admin_portal/src
COPY ansible_ai_connect_admin_portal/package.json /tmp/ansible_ai_connect_admin_portal/package.json
COPY ansible_ai_connect_admin_portal/package-lock.json /tmp/ansible_ai_connect_admin_portal/package-lock.json
COPY ansible_ai_connect_admin_portal/tsconfig.json /tmp/ansible_ai_connect_admin_portal/tsconfig.json
RUN cd /tmp/ansible_ai_connect_admin_portal && npx update-browserslist-db@latest
RUN npm --prefix /tmp/ansible_ai_connect_admin_portal ci
RUN npm --prefix /tmp/ansible_ai_connect_admin_portal run build

# Compile React/TypeScript Chatbot application
# Copy each source folder individually to avoid copying 'node_modules'
COPY ansible_ai_connect_chatbot/src /tmp/ansible_ai_connect_chatbot/src
COPY ansible_ai_connect_chatbot/index.html /tmp/ansible_ai_connect_chatbot/index.html
COPY ansible_ai_connect_chatbot/package.json /tmp/ansible_ai_connect_chatbot/package.json
COPY ansible_ai_connect_chatbot/package-lock.json /tmp/ansible_ai_connect_chatbot/package-lock.json
COPY ansible_ai_connect_chatbot/tsconfig.json /tmp/ansible_ai_connect_chatbot/tsconfig.json
COPY ansible_ai_connect_chatbot/vite.config.ts /tmp/ansible_ai_connect_chatbot/vite.config.ts
RUN npm --prefix /tmp/ansible_ai_connect_chatbot install
RUN ln -s /var/www/ansible-ai-connect-service/ansible_ai_connect /tmp/ansible_ai_connect
RUN npm --prefix /tmp/ansible_ai_connect_chatbot run build
RUN unlink /tmp/ansible_ai_connect

# Copy configuration files
COPY tools/scripts/launch-wisdom.sh /usr/bin/launch-wisdom.sh
COPY tools/configs/nginx.conf /etc/nginx/nginx.conf
COPY tools/configs/nginx-wisdom.conf /etc/nginx/conf.d/wisdom.conf
COPY tools/configs/uwsgi.ini /etc/wisdom/uwsgi.ini
COPY tools/configs/supervisord.conf /etc/supervisor/supervisord.conf

# Set permissions
RUN for dir in \
      /var/log/supervisor \
      /var/run/supervisor \
      /var/run/uwsgi \
      /var/run/daphne \
      /var/www/wisdom \
      /var/log/nginx \
      /etc/ansible \
      /var/run/django_metrics \
      /var/www/.cache \
      ; \
    do mkdir -p $dir ; chgrp -R 0 $dir; chmod -R g=u $dir ; done && \
    echo "\setenv PAGER 'less -SXF'" > /etc/psqlrc

# Launch!
ENV ANSIBLE_HOME=/etc/ansible
WORKDIR /var/www

USER 1000
EXPOSE 8000

CMD /usr/bin/launch-wisdom.sh

FROM production AS devel
USER 0
RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y inotify-tools && \
    dnf remove -y epel-release && \
    dnf clean all
COPY tools/scripts/auto-reload.sh /usr/bin/auto-reload.sh
RUN mkdir /etc/supervisor/supervisord.d/
COPY tools/configs/supervisord.d/auto-reload.conf /etc/supervisor/supervisord.d/auto-reload.conf
USER 1000
