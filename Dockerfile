FROM pytorch/torchserve-nightly:latest-gpu as base

USER 0

# install dependencies
RUN pip3 install transformers==4.21.2 && \
     chgrp -R 0 /home/model-server && \
     chmod -R g=u /home/model-server

# copy model artifacts, custom handler and other dependencies
COPY --chown=1000:0 ./torchserve/handler.py /home/model-server/
COPY --chown=1000:0 ./config.properties /home/model-server/

# expose health and prediction listener ports from the image
EXPOSE 7080
EXPOSE 7081

USER 1000

# run Torchserve HTTP server to respond to prediction requests
ENV TRANSFORMERS_CACHE=~/.cache
CMD ["torchserve", \
     "--start", \
     "--ts-config=/home/model-server/config.properties", \
     "--models=wisdom=wisdom.mar", \
     "--model-store=/home/model-server/model-store"]

FROM base as development

VOLUME /home/model-server/model-store

FROM base as production

ARG MODEL_PATH=./model/wisdom

COPY --chown=1000:0 ${MODEL_PATH}/wisdom.mar /home/model-server/model-store
