FROM wisdom-service
USER root

# https://github.com/redhat-appstudio/hacbs-test/blob/main/clamav/Dockerfile
RUN dnf -y --setopt=tsflags=nodocs install \
    https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf -y --setopt=tsflags=nodocs install \
    clamav \
    clamav-update && \
    dnf clean all

RUN rm -rf /var/lib/clamav

COPY clamav-db /var/lib/clamav
COPY tools/scripts/clamscan.sh /usr/local/bin

CMD [ "clamscan.sh" ]
