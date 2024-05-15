FROM busybox

ARG IMAGE_TAGS=image-tags-not-defined
ARG GIT_COMMIT=git-commit-not-defined

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
