# Setting up the OpenShift cluster

## Deploy OpenShift
1. Download OpenShift installer
2. From directory containing `install-config.yaml`:
    ```bash
    ./openshift-install create cluster
    ```

### Preparation
1. (TODO): Create namespaces
2. (TODO): Set variables required for deploy
    ```bash
    $AWS_HOSTED_ZONE_ID
    $AWS_ACCESS_KEY_ID
    $AWS_HOSTED_ZONE_ID
    $AWS_ACCESS_KEY_ID
    $AWS_SECRET_ACCESS_KEY
    $PULL_SECRET
    $PUBLIC_SSH_KEY
    $CONTAINER_IMAGE
    ```

### Install operators
1. Install cert-manager operator
1. Install Node Feature Discovery operator
1. Install NVIDIA GPU operator
1. Create cluster GPU policy
    ```bash
    envsubst < deploy/gpu-cluster-policy.yaml | oc apply -f -
    ```

### Configure DNS
1. Create a new DNS domain (under testing.ansible.com: wisdom.testing.ansible.com)
1. Add an NS entry named wisdom.testing.ansible.com under testing.ansible.com with the nameservers from wisdom.testing.ansible.com
1. Add an NS entry named apps.dev.wisdom.testing.ansible.com under testing.ansible.com with the nameservers from wisdom.testing.ansible.com
1. Create IAM policy (that matches deploy/route53-policy.json) for automatically updating the DNS zone
1. Create IAM user and attach new policy

### Configure cert-manager & create certificate
1. Create secret containing AWS credentials used by cert-manager to create DNS entries as part of ACME challenge
    ```bash
    envsubst < deploy/prod-route53-credentials-secret.yaml | oc apply -f -
    ```
1. Create production and staging cluster certificate issuers
    ```bash
    envsubst < deploy/*-clusterissuers.yaml | oc apply -f -
    ```
1. Generate certificate
    ```bash
    envsubst < deploy/certificate.yaml | oc apply -f -
    ```
1. Set default ingress cert
    ```bash
    oc patch ingresscontroller.operator default \
        --type=merge -p \
        '{"spec":{"defaultCertificate": {"name": "default-ingress"}}}' \
        -n openshift-ingress-operator
    ```
1. Enable Edge TLS
    ```bash
    oc patch ingresscontroller.operator default --type=merge -p '{"spec":{"tls": {"insecureEdgeTerminationPolicy": "Redirect", "termination": "edge"}}}' -n openshift-ingress-operator 
    ```

## Deploy the application

1. (TODO) Create namespaces
1. Deploy application and service
    ```bash
    envsubst < deploy/application/*.yaml | oc apply -f -
    ```
