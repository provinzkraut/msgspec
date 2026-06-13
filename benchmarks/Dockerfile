# image for running msgspec's benchmarks on bencher.dev bare-metal
# runners (https://bencher.dev/docs/explanation/bare-metal/).

# Pinned for reproducible benchmarking: the Python version must stay fixed so
# results remain comparable over time.
FROM python:3.14-slim AS build

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

ARG MSGSPEC_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${MSGSPEC_VERSION}

# Copy only the files needed to build the wheel -- never the whole context.
WORKDIR /src
COPY pyproject.toml setup.py README.md LICENSE ./
COPY src ./src
RUN uv build --wheel --out-dir /dist


FROM python:3.14-slim

WORKDIR /app

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

COPY benchmarks ./benchmarks

# put the compiled extension at a stable path so we can track its size via
# `--file-size`: https://bencher.dev/docs/how-to/track-file-size/.
RUN python -c "import msgspec._core, shutil; shutil.copyfile(msgspec._core.__file__, '/app/msgspec_core.so')"

CMD ["python", "-m", "benchmarks.bencher"]
