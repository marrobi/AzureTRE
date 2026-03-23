#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset
# Uncomment this line to see each command for debugging (careful: this will show secrets!)
# set -o xtrace

# Check for import section (import image from external registry to ACR)
if [ "$(yq eval ".custom.runtime_image.import" porter.yaml)" != "null" ]; then
  image_name=$(yq eval ".custom.runtime_image.name" porter.yaml)
  source_image=$(yq eval ".custom.runtime_image.import.source" porter.yaml)
  version=$(yq eval ".custom.runtime_image.import.tag" porter.yaml)

  echo "Importing ${source_image}:${version} to ACR as ${image_name}:${version}..."
  az acr import --name "${ACR_NAME}" \
    --source "${source_image}:${version}" \
    --image "${image_name}:${version}" \
    --force
  echo "Image imported successfully"
  exit 0
fi

if [ "$(yq eval ".custom.runtime_image.build" porter.yaml)" == "null" ]; then
  echo "Runtime image build section isn't specified. Exiting..."
  exit 0
fi

image_name=$(yq eval ".custom.runtime_image.name" porter.yaml)
version_file=$(yq eval ".custom.runtime_image.build.version_file" porter.yaml)
docker_file=$(yq eval ".custom.runtime_image.build.docker_file" porter.yaml)
docker_context=$(yq eval ".custom.runtime_image.build.docker_context" porter.yaml)
acr_domain_suffix=$(az cloud show --query suffixes.acrLoginServerEndpoint --output tsv)

version_line=$(cat "${version_file}")

# doesn't work with quotes
# shellcheck disable=SC2206
version_array=( ${version_line//=/ } ) # split by =
version="${version_array[1]//\"}" # second element is what we want, remove " chars

az acr login -n "${ACR_NAME}"

docker_cache=("--cache-from" "${FULL_IMAGE_NAME_PREFIX}/${image_name}:${version}")

if [ -n "${CI_CACHE_ACR_NAME:-}" ]; then
	az acr login -n "${CI_CACHE_ACR_NAME}"
	docker_cache+=("--cache-from" "${CI_CACHE_ACR_NAME}${acr_domain_suffix}/${IMAGE_NAME_PREFIX}/${image_name}:${version}")
fi

ARCHITECTURE=$(docker info --format "{{ .Architecture }}" )

if [ "${ARCHITECTURE}" == "aarch64" ]; then
    DOCKER_BUILD_COMMAND="docker buildx build --platform linux/amd64"
else
    DOCKER_BUILD_COMMAND="docker build"
fi

${DOCKER_BUILD_COMMAND} --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t "${FULL_IMAGE_NAME_PREFIX}/${image_name}:${version}" \
  "${docker_cache[@]}" -f "${docker_file}" "${docker_context}"

# Process additional imports (for bundles that need both a built image and imported images)
if [ "$(yq eval ".custom.additional_imports" porter.yaml)" != "null" ]; then
  count=$(yq eval ".custom.additional_imports | length" porter.yaml)
  for i in $(seq 0 $((count - 1))); do
    import_name=$(yq eval ".custom.additional_imports[$i].name" porter.yaml)
    import_source=$(yq eval ".custom.additional_imports[$i].source" porter.yaml)
    import_tag=$(yq eval ".custom.additional_imports[$i].tag" porter.yaml)
    echo "Importing ${import_source}:${import_tag} to ACR as ${import_name}:${import_tag}..."
    az acr import --name "${ACR_NAME}" \
      --source "${import_source}:${import_tag}" \
      --image "${import_name}:${import_tag}" \
      --force
    echo "Image ${import_name}:${import_tag} imported successfully"
  done
fi

# Process additional builds (for bundles that need extra images built and pushed to ACR)
if [ "$(yq eval ".custom.additional_builds" porter.yaml)" != "null" ]; then
  count=$(yq eval ".custom.additional_builds | length" porter.yaml)
  for i in $(seq 0 $((count - 1))); do
    build_name=$(yq eval ".custom.additional_builds[$i].name" porter.yaml)
    build_tag=$(yq eval ".custom.additional_builds[$i].tag" porter.yaml)
    build_docker_file=$(yq eval ".custom.additional_builds[$i].docker_file" porter.yaml)
    build_docker_context=$(yq eval ".custom.additional_builds[$i].docker_context" porter.yaml)
    full_tag="${FULL_IMAGE_NAME_PREFIX}/${build_name}:${build_tag}"
    echo "Building additional image ${full_tag}..."
    ${DOCKER_BUILD_COMMAND} -t "${full_tag}" -f "${build_docker_file}" "${build_docker_context}"
    echo "Image ${full_tag} built successfully"
  done
fi

