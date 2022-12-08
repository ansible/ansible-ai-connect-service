FROM pytorch/torchserve:latest-gpu

# install dependencies
RUN pip3 install transformers==4.21.1 torchserve
USER model-server

# copy model artifacts, custom handler and other dependencies
COPY ./ansible_wisdom/model/handler.py /home/model-server/
COPY ./config.properties /home/model-server/
# rg: do we need this?
#COPY ./index_to_name.json /home/model-server/

COPY ./model/wisdom.mar /home/model-server/model-store

# expose health and prediction listener ports from the image
EXPOSE 7080
EXPOSE 7081

# run Torchserve HTTP serve to respond to prediction requests
CMD ["torchserve", \
     "--start", \
     "--ts-config=/home/model-server/config.properties", \
     "--models", \
     "wisdom=wisdom.mar", \
     "--model-store", \
     "/home/model-server/model-store"]
