# HOW TO INSTALL - BRUTAL WAY

## Create the GPU VM First

- You need to ask for a quota in Central US for this SKU : Standard_NCC40ads_H100_v5
- Follow this guide to setup the VM. **Use gpt-oss-20b instead of Phi-xx** : https://github.com/microsoft/confidential-ai-workshop/blob/main/tutorials/confidential-llm-inferencing/README.md

## Other Azure resources to deploy for the project (other than VM and AKS)

Refer to [arm-teplate.json](../infra/arm-template.json) to a almost full set up of the infrastructure.

- AI Search
- Storage Account
- Key Vault
- Document Intelligence
- Attestation Server
- Azure Container Registry (if needed)

## You need an AKS cluster with this specifications :

- 2 node pools
  - System node pools with 2 nodes : DC4as_v5 with 128GB Disk (Managed Disk in SSD Premium)
  - User node pool with 2 nodes : DC16as_5 with specific labels and taints for nodeSelector (default as **agentpool: cvmnp** in deployment files) with 256GB disk (Managed Disk in SSD Premium)
- 1 Managed Identity need to be created
  - To identify to resources like storage account, Key Vault, AI Search ...
  - Workload Identity enabled in the cluster : https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview?tabs=dotnet
- Service Account created in the namespace linked to the Managed Identity : https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster?tabs=new-cluster#create-a-kubernetes-service-account
- Create a namespace for the app (eg: app)
- Certificates for ingress HTTPS
  - Communications between the pods within cluster will be in HTTP for now (**WIP for HTTPS**) (you can install linkerd for auto mTLS)
  - Create a secret with the certificates (ingress-cert as secretName in the deployment file) in the app namespace
  - If you use some self signed certificate, you will need to import it in your OS/Browser
- Deployment of an ingress controller (in nginx-ingress/ directory) in a dedicated namespace (eg: ingress-nginx)

```
helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace -f values.yaml
```

You can use the ARM template provided in /infra directory, but some actions need to be done in post installation.

## RBAC to apply

### Storage Account
**Storage Blob Data Contributor** : User Managed Identity

### Key Vault
**Key Vault Crypto Officer** : MI AKS Agent Pool + User Managed Identity   
**Key Vault Secrets Officer** : User Managed Identity 

### AI Search
**Search Service Index Contributor** : User Managed Identity  
**Search Service Contributor** : User Managed Identity

## Configuration

- Container is created automatically in the storage account at start 
  
- Create the SKR Key in the KeyVault with the according policy [policy-release.json](../infra/policy-release.json) :
  - https://github.com/microsoft/confidential-ai-workshop/blob/main/tutorials/confidential-llm-inferencing/README.md#4-secure-key-vault-and-attestation-policy-configuration
  - Use the Attestation provider url created with the ARM template or create your own (or use the default one for the region of the app is deployed)

- Key for encrypting vector is automatically created at application start

- Index will be created automatically in AI Search at application start

- Rename the [.env.example](../.env.example) to .env file and set the according values

```
# Configuration Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=saconfidentialai
# Container will be created at the first start
AZURE_STORAGE_CONTAINER_NAME=encrypted-documents-skr
# Configuration Azure Key Vault
AZURE_KEYVAULT_URL=https://kvconfidentialai.vault.azure.net/

# Configuration Azure AI Search
AZURE_SEARCH_SERVICE_NAME=confidentialsearch
# Index is created at first start
AZURE_SEARCH_INDEX_NAME=documents-index-skr

# Configuration Azure Document Intelligence
AZURE_DOC_INTELLIGENCE_ENDPOINT=http://di-extraction-ai-document-intelligence-layout.ai.svc.cluster.local

# Configuration LLM
# IP or FQDN of your LLM Instance in the confidential VM 
PHI_MODEL_ENDPOINT=https://my-confidential-llm.centralus.cloudapp.azure.com
# If you set the authentication with API-key in Caddy (sent anyway but not used if not set in the VM)
PHI_MODEL_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PHI_MODEL_NAME=/dev/shm/decrypted_model/gpt-oss-20b

# Configuration Nomic Embed Text (for embeddings)
NOMIC_EMBED_ENDPOINT=http://nomic-svc.ai.svc.cluster.local/api/embeddings
NOMIC_EMBED_MODEL=nomic-embed-text

# Configuration SKR (Secure Key Release) - Confidential mode
ENABLE_SKR_MODE=true
SKR_MAA_ENDPOINT=https://shareditn.itn.attest.azure.net
SKR_KEYVAULT_KEY_URL=https://kvconfidentialai.vault.azure.net/keys/KekForSKR/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Managed Identity linked to the Service Account
IMDS_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Base URL of the applicaiton to generate download link
# In Azure you need a domain : https://ai-app.mydomain.com
APP_BASE_URL=https://ai-app-skr.mydomain.com

# Key Name in the KeyVault
# You need to create the key BEFORE deployment (with the release policy)
ENCRYPTION_PRIVATE_KEY_NAME=KekForSKR
ENCRYPTION_PUBLIC_KEY_NAME=KekForSKR

# Configuration IronCore Alloy
# Key Name in the KeyVault for IronCore 
# Key will be created at first start(format: openssl rand -hex 128)
IRONCORE_MASTER_KEY_NAME=ironcore-master-key

# Enable Encryption in AI Search
ENABLE_SEARCH_ENCRYPTION=True
```

- Create the configmap from the .env file

 ``kubectl create cm cm-ai-app-skr --from-env-file=.env``

- Create the Service Account and configure the Managed Identity accordingly :
  - https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview?tabs=dotnet
  - https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster?tabs=new-cluster#create-a-kubernetes-service-account
  - Use the sa.yaml file (**You HAVE to set the Client Id of the use managed identity previously created**)

- Create the secret with the API key for Document Intelligence (encode the api-key in base64)

```apiVersion: v1
kind: Secret
metadata:
  name: docintel-secret
type: Opaque
data:
  apikey: bXktc2VjcmV0LXZhbHVl  # This is base64-encoded api-key
```

Deploy all the ressources in this directory to start the app in this order :

- All the pvc*.yaml
- deployment-read.yaml
- deployment-embeddings.yaml
- deployment-app-skr.yaml

You can use my own image for the application (You need network access to this public Azure Container Registry or build the Docker image yourself with the provided Dockerfile, and configure the deployment file)

