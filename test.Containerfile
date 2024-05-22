FROM registry.access.redhat.com/ubi9/ubi:latest AS production
ARG IMAGE_TAGS=not-given
ARG GIT_COMMIT=not-given

RUN echo "IMAGE_TAGS=${IMAGE_TAGS} GIT_COMMIT=${GIT_COMMIT}"

COPY requirements-x86_64.txt /var/www/ansible-wisdom-service/
RUN echo -e "\
{\n\
  \"imageTags\": \"${IMAGE_TAGS}\", \n\
  \"gitCommit\": \"${GIT_COMMIT}\" \n\
}\n\
" > /var/www/ansible-wisdom-service/version_info.json

CMD sleep 10000
USER 1000
LABEL konflux.additional-tags="${IMAGE_TAGS}"
