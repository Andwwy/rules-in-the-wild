#!/bin/bash
# Start the gateway on :4000. Keys come from ~/Desktop/DAPlab/.env; the sandbox reaches the gateway at
# http://host.docker.internal:4000 with GATEWAY_API_KEY.
# Setup once:  python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd "$(dirname "$0")"
set -a
source ~/Desktop/DAPlab/.env
set +a
# An empty AWS_BEARER_TOKEN_BEDROCK still counts as set for AWS's SDK, which then sends an empty bearer token instead of
# signing with the access keys; drop it unless it has a value.
[ -n "${AWS_BEARER_TOKEN_BEDROCK:-}" ] || unset AWS_BEARER_TOKEN_BEDROCK
[ -n "${BEDROCK_PROFILE_ARN:-}" ] || { echo "BEDROCK_PROFILE_ARN is empty in ~/Desktop/DAPlab/.env (your tagged Bedrock profile)"; exit 1; }
# The calls must go to the profile's own region: arn:aws:bedrock:<region>:<account>:application-inference-profile/<id>
region="$(cut -d: -f4 <<<"$BEDROCK_PROFILE_ARN")"
[ -n "$region" ] || { echo "BEDROCK_PROFILE_ARN is not a Bedrock ARN"; exit 1; }
[ -z "${AWS_REGION_NAME:-}" ] || [ "$AWS_REGION_NAME" = "$region" ] || echo "AWS_REGION_NAME=$AWS_REGION_NAME; using the profile's region, $region"
export AWS_REGION_NAME="$region"
export GATEWAY_API_KEY="${GATEWAY_API_KEY:-sk-experiment-local}"
# The Opus 5.5 profile (config.yaml), found by its name when .env does not give it
export BEDROCK_OPUS_PROFILE_ARN="${BEDROCK_OPUS_PROFILE_ARN:-$(.venv/bin/python -c 'import boto3; print(next((p["inferenceProfileArn"] for p in boto3.client("bedrock", region_name="us-east-1").list_inference_profiles(typeEquals="APPLICATION", maxResults=1000)["inferenceProfileSummaries"] if p["inferenceProfileName"] == "rules-in-the-wild-ww2780-opus-5-5"), ""))' 2>/dev/null)}"
exec .venv/bin/litellm --config config.yaml --host 0.0.0.0 --port 4000
