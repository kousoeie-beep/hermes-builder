ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

# curl is the sole prerequisite of the advertised POSIX one-liner. sudo and
# certificates model a normal newly installed Linux workstation/server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl sudo \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash hermes-user \
    && printf '%s\n' 'hermes-user ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/hermes-user \
    && chmod 0440 /etc/sudoers.d/hermes-user

COPY --chown=hermes-user:hermes-user . /workspace/hermes-builder

USER hermes-user
ENV HOME=/home/hermes-user
WORKDIR /workspace/hermes-builder

CMD ["bash", "tests/docker/full_install.sh"]
