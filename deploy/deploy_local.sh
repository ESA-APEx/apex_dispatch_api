#!/usr/bin/env bash
set -euo pipefail

RELEASE_NAME="${1:-apex-dispatch-api}"
CLUSTER_NAME="${2:-local}"
IMAGE_NAME="${3:-apex-dispatch-api:latest}"
HOST="${4:-apex-dispatch-api.local}"
NAMESPACE="${5:-apex-dispatch-api-local}"
ENV_FILE="${6:-../.env}"
SECRET_NAME="${7:-apex-dispatch-api-secrets}"

echo "(1) Create kind cluster (if missing)"
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  kind create cluster --name "${CLUSTER_NAME}"
else
  echo "Cluster ${CLUSTER_NAME} already exists"
fi

echo "(2) Load local image into kind"
kind load docker-image "${IMAGE_NAME}" --name "${CLUSTER_NAME}"

echo "(3) Install ingress-nginx "
kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s

# Create namespace up front so we can create secrets there
echo "(4) Creating namespace ${NAMESPACE}"
if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl create namespace "${NAMESPACE}"
else
  echo "Namespace ${NAMESPACE} exists"
fi


echo "(5) Creating/updating Kubernetes Secret ${SECRET_NAME} in namespace ${NAMESPACE}"

_extract_env() {
  local key="$1"
  local val
  if [ ! -f "${ENV_FILE}" ]; then
    echo ""
    return
  fi
  val=$(sed -n -E "s/^${key}=(.*)/\1/p" "${ENV_FILE}" | sed -E 's/^"(.*)"$/\1/' | sed -E "s/^'(.*)'$/\1/")
  echo "${val}"
}

KEYCLOAK_CLIENT_ID=$(_extract_env "KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET=$(_extract_env "KEYCLOAK_CLIENT_SECRET")
DATABASE_URL=$(_extract_env "DATABASE_URL")
OPENEO_BACKENDS=$(_extract_env "OPENEO_BACKENDS")

# Create or update secret using kubectl apply via dry-run
kubectl create secret generic "${SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  --from-literal=KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID}" \
  --from-literal=KEYCLOAK_CLIENT_SECRET="${KEYCLOAK_CLIENT_SECRET}" \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=OPENEO_BACKENDS="${OPENEO_BACKENDS}" \
  --dry-run=client -o yaml | kubectl apply -f -


echo "(6) Install/upgrade apex-dispatch-api chart with ingress enabled"
helm upgrade --install "${RELEASE_NAME}" ./apex-dispatch-api  -f ./apex-dispatch-api/values.yaml \
  --namespace "${NAMESPACE}" --create-namespace \
  --wait


echo "(7) Enabling port forwarding to test locally"
kubectl -n apex-dispatch-api-local port-forward svc/apex-dispatch-api 8000:8000