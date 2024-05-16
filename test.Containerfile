FROM busybox

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
