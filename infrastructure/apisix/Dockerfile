FROM apache/apisix:3.9.1-debian
# Only overlay routes — keep the base image config.yaml for entrypoint compatibility.
COPY --chmod=644 apisix.yaml /usr/local/apisix/conf/apisix.yaml
