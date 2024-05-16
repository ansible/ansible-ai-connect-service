FROM registry.access.redhat.com/ubi9/ubi:latest AS production

ARG DJANGO_SETTINGS_MODULE=ansible_wisdom.main.settings.production

ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

ENV PROMETHEUS_MULTIPROC_DIR=/var/run/django_metrics

ENV BUILD_PATH=/var/www/wisdom/public/static/console

# Install dependencies
RUN dnf module enable nodejs:18 nginx:1.22 -y && \
    dnf install -y \
    git
RUN pwd && ls -lrt
RUN _IMAGE_TAGS="$(cat .version).$(git log -n1 --pretty='format:%cd' --date=format:'%Y%m%d%H%M')"
RUN _GIT_COMMIT=$(git log -n1 --pretty='format:%H')
RUN echo -e "_IMAGE_TAGS=$_IMAGE_TAGS"

ARG IMAGE_TAGS=$_IMAGE_TAGS
ARG GIT_COMMIT=$_GIT_COMMIT

# Copy the ansible_wisdom package files
COPY requirements-x86_64.txt /var/www/ansible-wisdom-service/

RUN echo -e "\
{\n\
  \"imageTags\": \"${IMAGE_TAGS}\", \n\
  \"gitCommit\": \"${GIT_COMMIT}\" \n\
}\n\
" > /var/www/ansible-wisdom-service/version_info.json

CMD sleep 10000
USER 1000
