# 手元で make を走らせる環境。Python は CI(.github/workflows/build.yaml)と同じ 3.11 に揃える。
# 使い方は scripts/docker-make を見る。
FROM python:3.11-slim-bookworm

ARG FONTSPECTOR_VERSION=1.7.4
ARG DIFFENATOR3_VERSION=1.1.4

# libegl1 と libgl1 と libfontconfig1 は、見本画像(make images)を描く skia-python が読み込む。
RUN apt-get update \
 && apt-get install -y --no-install-recommends make git curl ca-certificates libegl1 libgl1 libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*

# 配布されているビルド済みバイナリを使うので、x86_64 のホスト専用になる。
RUN mkdir -p /tmp/bin \
 && curl -fsSL "https://github.com/fonttools/fontspector/releases/download/fontspector-v${FONTSPECTOR_VERSION}/fontspector-v${FONTSPECTOR_VERSION}-x86_64-unknown-linux-gnu.tar.gz" | tar -xz -C /tmp/bin \
 && curl -fsSL "https://github.com/googlefonts/diffenator3/releases/download/v${DIFFENATOR3_VERSION}/diffenator3-${DIFFENATOR3_VERSION}-x86_64-unknown-linux-gnu.tar.gz" | tar -xz -C /tmp/bin \
 && find /tmp/bin -type f -perm -u+x -exec mv {} /usr/local/bin/ \; \
 && rm -rf /tmp/bin

# ホストのユーザーで走らせるので、pip のキャッシュを書ける場所にする。
ENV HOME=/tmp
WORKDIR /work
