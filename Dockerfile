FROM pytorch/torchserve-nightly:latest-gpu as base

# install dependencies
RUN pip3 install transformers==4.21.1 torchserve
USER model-server

# copy model artifacts, custom handler and other dependencies
COPY ./torchserve/handler.py /home/model-server/
COPY ./config.properties /home/model-server/

# expose health and prediction listener ports from the image
EXPOSE 7080
EXPOSE 7081

# run Torchserve HTTP server to respond to prediction requests
CMD ["torchserve", \
     "--start", \
     "--ts-config=/home/model-server/config.properties", \
     "--models", \
     "wisdom=wisdom.mar", \
     "--model-store", \
     "/home/model-server/model-store"]

FROM base as development

VOLUME /home/model-server/model-store

FROM base as production

ARG MODEL_PATH=./model

COPY ${MODEL_PATH}/wisdom.mar /home/model-server/model-store
