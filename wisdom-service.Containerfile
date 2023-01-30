FROM registry.access.redhat.com/ubi9/ubi:9.1.0-1646.1669627755

ARG DJANGO_SETTINGS_MODULE=main.settings.production

ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

RUN dnf install -y \
    python3-devel \
    gcc \
    libpq \
    libpq-devel \
    python3 \
    python3-pip \
    nginx

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf install -y inotify-tools && \
    dnf remove -y epel-release

COPY ansible_wisdom /var/www/ansible_wisdom
RUN sed -i 's,/run/nginx.pid,/tmp/nginx.pid,' /etc/nginx/nginx.conf
COPY tools/scripts/launch-wisdom.sh /usr/bin/launch-wisdom.sh
COPY tools/scripts/auto-reload.sh /usr/bin/auto-reload.sh
COPY tools/configs/nginx.conf /etc/nginx/conf.d/wisdom.conf
COPY tools/configs/uwsgi.ini /etc/wisdom/uwsgi.ini
COPY tools/configs/supervisord.conf /etc/supervisor/supervisord.conf
COPY requirements.txt /tmp

RUN /usr/bin/python3 -m pip install supervisor
RUN for dir in \
      /var/log/supervisor \
      /var/run/supervisor \
      /var/log/nginx ; \
    do mkdir -p $dir ; chown 1000 $dir ; done
RUN /usr/bin/python3 -m venv /var/www/venv
RUN /var/www/venv/bin/python3 -m pip install -r/var/www/ansible_wisdom/requirements.txt && rm -r /root/.cache
WORKDIR /var/www

USER 1000
EXPOSE 8000

CMD /usr/bin/launch-wisdom.sh
