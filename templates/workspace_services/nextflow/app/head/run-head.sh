#!/usr/bin/env bash
# Runs one pipeline as the Nextflow head process inside an Azure Batch container task.
# The portal stores the run's config and parameters under runs/<run_id>/ before it submits the task.
set -o errexit -o nounset -o pipefail

: "${NF_RUN_ID:?}" "${NF_PIPELINE:?}" "${NF_STORAGE_ACCOUNT:?}" "${NF_IDENTITY_CLIENT_ID:?}" "${NXF_HOME:?}"

blob="https://${NF_STORAGE_ACCOUNT}.blob.core.windows.net"
workdir="${AZ_BATCH_TASK_WORKING_DIR:-$PWD}"
cd "${workdir}"

export HOME="${workdir}"
export AZCOPY_AUTO_LOGIN_TYPE=MSI AZCOPY_MSI_CLIENT_ID="${NF_IDENTITY_CLIENT_ID}"
export AZCOPY_LOG_LOCATION="${workdir}/.azcopy" AZCOPY_JOB_PLAN_LOCATION="${workdir}/.azcopy"
# The workspace has no route to plugin registries or nextflow.io; plugins are pre-installed in NXF_HOME.
export NXF_OFFLINE=true NXF_DISABLE_CHECK_LATEST=true NXF_ANSI_LOG=false

# quiet: azcopy otherwise prints "Final Job Status: Completed", which reads like the run finished.
copy() { azcopy copy "$@" --output-level quiet; }

echo "Preparing Nextflow run ${NF_RUN_ID} (${NF_PIPELINE})"
copy "${blob}/runs/${NF_RUN_ID}/nextflow.config" run.config
copy "${blob}/runs/${NF_RUN_ID}/params.json" params.json

source_type="${NF_PIPELINE%%:*}"
name="${NF_PIPELINE#*:}"
if [[ ! "${name}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
  echo "Invalid pipeline name: ${name}" >&2
  exit 2
fi
case "${source_type}" in
  builtin) pipeline_dir="/opt/nfportal/pipelines/${name}" ;;
  storage)
    mkdir -p pipeline
    copy "${blob}/pipelines/${name}/*" pipeline/ --recursive
    pipeline_dir="${workdir}/pipeline"
    ;;
  *) echo "Unknown pipeline source: ${source_type}" >&2; exit 2 ;;
esac

plugins=$(find "${NXF_HOME}/plugins" -mindepth 1 -maxdepth 1 -type d -name 'nf-*' -printf '%f\n' \
  | sed -E 's/^(nf-[a-z0-9-]+)-([0-9][^/]*)$/\1@\2/' | paste -sd, -)

python3 -m nfportal.weblog_sink &
sink_pid=$!

set +o errexit
nextflow -log nextflow.log run "${pipeline_dir}" \
  -c run.config -params-file params.json -plugins "${plugins}" \
  -with-report report.html -with-timeline timeline.html -with-trace trace.txt -with-dag dag.mmd &
nf_pid=$!
# Batch stops the container on cancel; let Nextflow abort its own Batch tasks first.
trap 'kill -TERM "${nf_pid}" 2>/dev/null' TERM INT
wait "${nf_pid}"
rc=$?
if kill -0 "${nf_pid}" 2>/dev/null; then
  wait "${nf_pid}"
  rc=$?
fi
set -o errexit

mkdir -p _nextflow
for f in nextflow.log report.html timeline.html trace.txt dag.mmd params.json; do
  [[ -f "${f}" ]] && cp "${f}" _nextflow/
done
echo "${rc}" > _nextflow/exit_code
copy "_nextflow/*" "${blob}/results/${NF_RUN_ID}/_nextflow/" --recursive || echo "Could not upload run reports" >&2

kill "${sink_pid}" 2>/dev/null || true
echo "Nextflow finished with exit code ${rc}"
exit "${rc}"
