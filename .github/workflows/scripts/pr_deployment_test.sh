#!/bin/bash

#############################
invoke_pr_test() {
#############################
  WORKFLOW_ID=$1
  TOKEN=$2
  PR_NUMBER=$3
  echo "test pr deployment"
  echo "invoke_pr_test: PR_NUMBER=${PR_NUMBER}"

  run_url=$(curl -sSL \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/ansible/ansible-wisdom-testing/actions/workflows/${WORKFLOW_ID}/dispatches" \
    -d '{"ref": "main", "inputs": {"pr_number": "'"${PR_NUMBER}"'"}}')
  # Give the workflow time to start
  sleep 15
  RUN_ID=$(
    curl -s -X GET \
      -H "Authorization: Bearer ${TOKEN}" \
      "https://api.github.com/repos/ansible/ansible-wisdom-testing/actions/workflows/${WORKFLOW_ID}/runs?per_page=1" | jq '.workflow_runs[0].id'
  )
  if [[ -z $RUN_ID ]]; then
    echo "Failed to fetch the workflow."
    exit 1
  fi
  echo "Workflow triggered. Run ID: $RUN_ID"
  # Pull the run status
  while true; do
    run_info=$(curl -sSL \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Accept: application/vnd.github.v3+json" \
      "https://api.github.com/repos/ansible/ansible-wisdom-testing/actions/runs/$RUN_ID")
    run_status=$(echo "$run_info" | jq -r '.status')
    if [[ $run_status == "completed" ]]; then
      conclusion=$(echo "$run_info" | jq -r '.conclusion')
      echo "Tests execution https://github.com/ansible/ansible-wisdom-testing/actions/runs/$RUN_ID completed with conclusion: $conclusion"
      if [[ $conclusion == "success" ]]; then
        exit 0
      else
        exit 1
      fi
    elif [[ $run_status == "in_progress" ]]; then
      echo "Workflow is still in progress. Checking again in 30 seconds..."
      sleep 30
    else
      echo "Failed to retrieve the workflow status."
      exit 1
    fi
  done
}


#############################
wait_for_pr_deployment() {
#############################
  PR_NUMBER=$1
  CLUSTER_HOST=$2
  echo "wait_for_pr_deployment: PR_NUMBER=${PR_NUMBER}"
  URL="https://wisdom-service-wisdom-pr-${PR_NUMBER}.apps.${CLUSTER_HOST}/check/"
  # URL=https://stage.ai.ansible.redhat.com/check/
  for i in {1..16} # 8 minutes shouid be enough
  do
    health=$(curl --write-out "%{http_code}\n" --silent --output /dev/null $URL)
    echo "${URL} returns: ${health}"
    if [[ $health == "200" ]]; then
      echo "PR deployment completed"
      exit 0
    else
      echo "Deployment is not ready. Checking again in 30 seconds..."
      sleep 30
    fi
  done
  echo "Deployment probably is broken. Please check"
}

$*
