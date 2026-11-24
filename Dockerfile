FROM debian:13-slim@sha256:8aa5a7bf5a1955bddbe7d74fcdd0b91ab30e74362a8b73af672b0481b35b44a0 AS base
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

FROM base AS fetch
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 gnupg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY upstream.lock.json scripts/upstream.py ./
RUN python3 upstream.py verify /out

FROM base AS runtime
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgmp10 libnuma1 libssl3t64 libtinfo6 zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 simplex \
    && useradd --uid 10001 --gid 10001 --home-dir /data --no-create-home --shell /usr/sbin/nologin simplex \
    && install -d -o 10001 -g 10001 -m 0700 /data
COPY --from=fetch --chmod=0755 /out/simplex-chat /usr/local/bin/simplex-chat
COPY --from=fetch /out/LICENSE /usr/share/doc/simplex-chat/LICENSE
COPY --from=fetch /out/SOURCE.txt /out/upstream.lock.json /usr/share/doc/simplex-chat/
COPY SOURCE.md /usr/share/doc/simplex-chat/SOURCE.md
COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint
RUN ldd /usr/local/bin/simplex-chat > /tmp/libraries \
    && ! grep -q 'not found' /tmp/libraries \
    && /usr/local/bin/simplex-chat --version \
    && rm /tmp/libraries
LABEL org.opencontainers.image.title="SimpleX Chat in Docker" \
      org.opencontainers.image.description="SimpleX Chat in Docker" \
      org.opencontainers.image.source="https://github.com/voboshi/simplex-chat-docker" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
ENV HOME=/data
WORKDIR /data
USER 10001:10001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["--database", "/data/chat", "--chat-server-port", "5225", "--user-display-name", "simplex", "--auto-accept-files", "0", "--yes-migrate"]

FROM base AS smoke
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY tests/ws.py /test.py
USER 10001:10001
ENTRYPOINT ["python3", "/test.py"]

FROM runtime AS final
