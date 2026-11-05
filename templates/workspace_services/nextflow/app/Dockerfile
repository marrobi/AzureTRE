# syntax=docker/dockerfile:1.7
# One image runs the portal on App Service and the Nextflow head process on the Batch head pool.
# Worker nodes copy azcopy from this image in their start task, because Batch nodes have no internet access.

FROM node:24-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS tools
ARG NEXTFLOW_VERSION=26.10.5
ARG NF_WEBLOG_VERSION=1.2.0
ARG AZCOPY_VERSION=10.34.1
ARG NF_SCHEMA_VERSION=2.0.0
ARG PGSC_CALC_VERSION=v2.3.0
ENV NXF_HOME=/opt/nextflow-home
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates openjdk-17-jre-headless \
  && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /usr/local/bin/nextflow \
    "https://github.com/nextflow-io/nextflow/releases/download/v${NEXTFLOW_VERSION}/nextflow-${NEXTFLOW_VERSION}-dist" \
  && chmod 755 /usr/local/bin/nextflow \
  && nextflow -version \
  && nextflow plugin install "nf-azure,nf-weblog@${NF_WEBLOG_VERSION},nf-schema@${NF_SCHEMA_VERSION}" \
  && ls "${NXF_HOME}/plugins"
# pgsc_calc runs offline from this copy; app/pipelines/pgsc-calc adds the TRE overlay on top.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
  && git clone --quiet --depth 1 --branch "${PGSC_CALC_VERSION}" https://github.com/PGScatalog/pgsc_calc /opt/pgsc-calc \
  && rm -rf /opt/pgsc-calc/.git /opt/pgsc-calc/.github /opt/pgsc-calc/docs
RUN curl -fsSL "https://github.com/Azure/azure-storage-azcopy/releases/download/v${AZCOPY_VERSION}/azcopy_linux_amd64_${AZCOPY_VERSION}.tar.gz" \
    | tar -xz --strip-components=1 -C /usr/local/bin --wildcards '*/azcopy' \
  && chmod 755 /usr/local/bin/azcopy \
  && azcopy --version

# Demo data for pipelines/uk-1kg-germline, sliced from public 1000 Genomes and UCSC files at build time.
FROM tools AS demo-data-fetch
COPY pipelines/uk-1kg-germline/prepare-demo-data.sh /usr/local/bin/
RUN prepare-demo-data.sh fetch /data

FROM staphb/samtools:1.24 AS demo-data-reads
COPY --from=demo-data-fetch /data /data
COPY pipelines/uk-1kg-germline/prepare-demo-data.sh /usr/local/bin/
RUN bash /usr/local/bin/prepare-demo-data.sh reads /data

FROM staphb/bcftools:1.24 AS demo-data-vcf
COPY --from=demo-data-fetch /data /data
COPY pipelines/uk-1kg-germline/prepare-demo-data.sh /usr/local/bin/
RUN bash /usr/local/bin/prepare-demo-data.sh vcf /data

FROM python:3.12-slim-bookworm
ENV NXF_HOME=/opt/nextflow-home \
    NXF_OFFLINE=true \
    NXF_DISABLE_CHECK_LATEST=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/nfportal/app \
    NF_BUILTIN_PIPELINES_DIR=/opt/nfportal/pipelines
RUN apt-get update \
  && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps ca-certificates \
  && rm -rf /var/lib/apt/lists/*
COPY --from=tools /usr/local/bin/nextflow /usr/local/bin/azcopy /usr/local/bin/
COPY --from=tools /opt/nextflow-home /opt/nextflow-home
# Batch runs the head task as a pool user, so Nextflow must be able to write its caches here.
RUN chmod -R a+rwX /opt/nextflow-home

WORKDIR /opt/nfportal
COPY requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt
COPY nfportal/ app/nfportal/
COPY --from=ui /nfportal/static/ app/nfportal/static/
COPY --from=tools /opt/pgsc-calc/ pipelines/pgsc-calc/
COPY pipelines/ pipelines/
COPY --from=demo-data-reads /data/HG00096_R1.fastq.gz /data/HG00096_R2.fastq.gz pipelines/uk-1kg-germline/data/
COPY --from=demo-data-vcf /data/chr22.fa.gz /data/HG00096_1kg_truth.vcf.gz /data/HG00096_1kg_truth.vcf.gz.tbi /data/1kg_population_af.vcf.gz /data/1kg_population_af.vcf.gz.tbi pipelines/uk-1kg-germline/data/
COPY head/ head/
RUN chmod 755 head/*.sh

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "nfportal.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
