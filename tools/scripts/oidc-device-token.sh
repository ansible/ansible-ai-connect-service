#!/usr/bin/env sh

step1=$(curl --silent --request POST  --url 'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/auth/device'  --header 'content-type: application/x-www-form-urlencoded' --data 'client_id=ansible-wisdom-staging-device' --data 'scope=api.lightspeed')
device_code=$(echo ${step1}|jq -r .device_code)
verification_uri_complete=$(echo ${step1}|jq -r .verification_uri_complete)
open_cmd=$(which xdg-open 2>/dev/null|| echo "open")
${open_cmd} ${verification_uri_complete}

access_token=""
while test -z ${access_token}; do
    sleep 3
    access_token=$(curl --silent --request POST --url 'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token' --header 'content-type: application/x-www-form-urlencoded' --data grant_type=urn:ietf:params:oauth:grant-type:device_code --data 'client_id=ansible-wisdom-staging-device' --data 'scope=api.lightspeed' --data "device_code=${device_code}"|jq -r .access_token)
    [ ${access_token} = "null" ] && access_token=""
done

echo "You can now call curl with:"
echo "  curl --header \"Authorization: Bearer ${access_token}\" https://stage.ai.ansible.redhat.com/api/v0/me/"
