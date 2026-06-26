FROM apache/apisix:3.9.1-debian
# Only overlay routes — replacing config.yaml breaks the image entrypoint permissions.
COPY apisix.yaml /usr/local/apisix/conf/apisix.yaml
RUN chmod a+r /usr/local/apisix/conf/apisix.yaml
