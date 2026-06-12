#!/usr/bin/env bash
# Deploy the Patchwork dispatcher + wire it to the buggy-service logs.
# Idempotent: safe to re-run. Run from the repo root or this directory.
set -euo pipefail

REGION=us-west-2
ACCOUNT=526908180591
RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:526908180591:runtime/test1-EuRGp04eDi
ROLE_NAME=patchwork-dispatcher-role
FUNC=patchwork-dispatcher
LOG_GROUP=/aws/lambda/buggy-service

HERE="$(cd "$(dirname "$0")" && pwd)"

# --- 1. IAM role the dispatcher runs as -------------------------------------
echo "==> Ensuring IAM role $ROLE_NAME"
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }' >/dev/null
fi

# Basic execution (CloudWatch Logs for the dispatcher itself)
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Permission to invoke the Patchwork agent runtime
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name invoke-agent-runtime \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"bedrock-agentcore:InvokeAgentRuntime\",
      \"Resource\": \"${RUNTIME_ARN}*\"
    }]
  }"

ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE_NAME}"

# --- 2. Package + create/update the dispatcher Lambda -----------------------
echo "==> Packaging dispatcher"
( cd "$HERE" && zip -q -FS /tmp/dispatcher.zip handler.py )

if aws lambda get-function --function-name "$FUNC" --region "$REGION" >/dev/null 2>&1; then
  echo "==> Updating $FUNC"
  aws lambda update-function-code --function-name "$FUNC" \
    --zip-file fileb:///tmp/dispatcher.zip --region "$REGION" >/dev/null
  aws lambda update-function-configuration --function-name "$FUNC" \
    --environment "Variables={PATCHWORK_AGENT_RUNTIME_ARN=$RUNTIME_ARN}" \
    --timeout 120 --region "$REGION" >/dev/null
else
  echo "==> Creating $FUNC (waiting ~10s for IAM role to propagate)"
  sleep 10
  aws lambda create-function --function-name "$FUNC" \
    --runtime python3.13 --role "$ROLE_ARN" --handler handler.handler \
    --timeout 120 \
    --environment "Variables={PATCHWORK_AGENT_RUNTIME_ARN=$RUNTIME_ARN}" \
    --zip-file fileb:///tmp/dispatcher.zip --region "$REGION" >/dev/null
fi

FUNC_ARN="arn:aws:lambda:${REGION}:${ACCOUNT}:function:${FUNC}"

# --- 3. Let CloudWatch Logs invoke the dispatcher ---------------------------
echo "==> Granting CloudWatch Logs invoke permission"
aws lambda add-permission --function-name "$FUNC" \
  --statement-id cwlogs-invoke --action lambda:InvokeFunction \
  --principal logs.amazonaws.com --source-account "$ACCOUNT" \
  --region "$REGION" >/dev/null 2>&1 || echo "   (permission already exists)"

# --- 4. Subscribe the filter to the buggy-service logs ----------------------
echo "==> Subscribing filter to $LOG_GROUP"
aws logs put-subscription-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name patchwork-errors \
  --filter-pattern '"quote.error"' \
  --destination-arn "$FUNC_ARN" \
  --region "$REGION"

echo "==> Done. Trigger a failure and watch:"
echo "    aws logs tail /aws/lambda/$FUNC --since 5m --follow --region $REGION"
