# google-manage-gce-floating-ip
Manage floating virtual IP address for MySQL cluster on GCE instances

This repository consists of a Python microservice app to manage floating IP address distribution between a cluster of MySQL nodes with replication service and deployed on Google Compute Engine (GCE) instances. The Master/Slave election is handled by MySQL MHA which will discover and track the health of the Master and Slave nodes in the MySQL cluster. MySQL clients will access the MySQL cluster via a Virtual IP address which is bounded to the active Master node. In the event when a Slave replica needs to be promoted to Master, the Virtual IP address binding will be released from the old Master node and bounded to the new Master node. This application exposes a REST API interface for the MHA server to handle the Virtual IP management between the Master and Slave nodes on GCE instances.

This README is designed to give you the information you need to get running with the application and understand the exposed REST APIs.


## Installation and Setup

### Environment Setup

- Clone this repository, build the container image, and push the image to your Google Artifact Repository or other Docker repos.
- Reserve a static internal IP address inside your VPC as the Virtual IP address to be used by the MySQL cluster.
- Create a GKE cluster with at least 1 node (recommended: n2-standard-2), with Workload Identity enabled. To enable Workload Identity on an existing GKE cluster, update your existing GKE cluster as follows:
  
  ``` 
  gcloud container clusters update CLUSTER_NAME \
    --region=COMPUTE_REGION \
    --workload-pool=PROJECT_ID.svc.id.goog
  ``` 
### Configure applications to use Workload Identity

- Create a namespace to use for the Kubernetes service account. You can also use the default namespace or any existing namespace.
  ``` 
  kubectl create namespace NAMESPACE
   ``` 
- Create a Kubernetes service account for your application to use. You can also use the default Kubernetes service account in the default or any existing namespace.

  ``` 
  kubectl create serviceaccount KSA_NAME --namespace NAMESPACE
  ``` 
   
  Replace the following:

    * KSA_NAME: the name of your new Kubernetes service account.
    * NAMESPACE: the name of the Kubernetes namespace for the service account.
- Create an IAM service account for your application or use an existing IAM service account instead. You can use any IAM service account in any project in your organization. For Config Connector, apply the IAMServiceAccount object for your selected service account.

  ``` 
  gcloud iam service-accounts create GSA_NAME --project=GSA_PROJECT
  ``` 
  Replace the following:

    * GSA_NAME: the name of the new IAM service account.
    * GSA_PROJECT: the project ID of the Google Cloud project for your IAM service account.
    
- Ensure that your IAM service account has the roles you need. You can grant additional roles using the following command:

  ``` 
  gcloud projects add-iam-policy-binding PROJECT_ID \
     --member "serviceAccount:GSA_NAME@GSA_PROJECT.iam.gserviceaccount.com" \
     --role "roles/compute.instanceAdmin"
  ``` 
  Replace the following:

    * PROJECT_ID: your Google Cloud project ID.
    * GSA_NAME: the name of your IAM service account.
    * GSA_PROJECT: the project ID of the Google Cloud project of your IAM service account.

- Allow the Kubernetes service account to impersonate the IAM service account by adding an IAM policy binding between the two service accounts. This binding allows the Kubernetes service account to act as the IAM service account.


  ``` 
  gcloud iam service-accounts add-iam-policy-binding GSA_NAME@GSA_PROJECT.iam.gserviceaccount.com \
     --role roles/iam.workloadIdentityUser \
     --member "serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/KSA_NAME]"
  ``` 
- Annotate the Kubernetes service account with the email address of the IAM service account.

  ``` 
  kubectl annotate serviceaccount KSA_NAME \
    --namespace NAMESPACE \
    iam.gke.io/gcp-service-account=GSA_NAME@GSA_PROJECT.iam.gserviceaccount.com
  ``` 
- Update your Pod spec to schedule the workloads on nodes that use Workload Identity and to use the annotated Kubernetes service account.
  ```yaml
  spec:
    serviceAccountName: KSA_NAME
    nodeSelector:
      iam.gke.io/gke-metadata-server-enabled: "true"
  ```
- Create a configmap that contains the MySQL cluster information using the sample "cluster_conf.yaml" file. Modify the "cluster_conf.yaml" according to your environment.

  Example:
  ```yaml
  gcp_project: GCP_PROJECT_ID
  cluster:
      - instance: MASTER_NODE
        location: MASTER_NODE_GCP_ZONE
      - instance: SLAVE_1_NODE
        location: SLAVE_1_NODE_GCP_ZONE
      - instance: SLAVE_2_NODE
        location: SLAVE_2_NODE_GCP_ZONE
  vip: VIP_ADDRESS
  ```
  
  Create a configmap on your GKE cluster with the modified "cluster_conf.yaml"
  
  ``` 
  kubectl create configmap floating-ip-configmap --namespace NAMESPACE \
    --from-file=<PATH TO your cluster_conf.yaml>
  ```
  
- Deploy the kubernetes manifest on your GKE cluster using the example "k8s_manifest.yaml" in this repository

  Example:
  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: manage-gce-floating-ip
    labels:
      name: manage-gce-floating-ip
  spec:
    selector:
      matchLabels:
        name: manage-gce-floating-ip
    template:
      metadata:
        labels:
          name: manage-gce-floating-ip
      spec:
        serviceAccountName: floating-ip-sa
        containers:
        - name: manage-gce-floating-ip
          image: <PATH TO YOUR CONTAINER IMAGE on docker repository>
          volumeMounts:
            - name: mnt
              mountPath: /tmp/cluster_conf
        volumes:
        - name: mnt
          configMap:
            name: floating-ip-configmap
  ```
  
  * Note: If necessary, you need to setup your GKE cluster with the appropriate IAM permission or pull secrets to download the container image

- Expose the deployment via an internal load balancer accessible by the MHA server.

## Using the REST API

   Replace the following:
   * LB ENDPOINT - The Internal Load Balancer IP address
   * PORT - The Port number exposed on the Internal LB

1. Get Cluster Members (/get-cluster-members)

   Retrieve the list of nodes in the cluster

   ```
   curl -X GET http://<LB ENDPOINT>:<PORT>/manage-gce-floating-ip/api/v1.0/get-cluster-members
   ```
   
   Sample output:
   ```
   [{'instance': 'mysql-mha-test-master', 'location': 'asia-southeast2-a'}, {'instance': 'mysql-mha-test-slave1', 'location': 'asia-southeast2-a'}, {'instance': 'mysql-mha-test-slave2', 'location': 'asia-southeast2-b'}]
   ```
2. Get Cluster VIP (/get-cluster-vip)

   Retrieve the Virtual IP address used in the cluster
   ```
   curl -X GET http://<LB ENDPOINT>:<PORT>/manage-gce-floating-ip/api/v1.0/get-cluster-vip
   ```
   Sample output:
   ```
   10.184.0.100
   ```
3. Get Master Instance (/get-master-instance)

   Retrieve the currently active Master Node
   
   ```
   curl -X GET http://<LB ENDPOINT>:<PORT>/manage-gce-floating-ip/api/v1.0/get-master-instance
   ```
   Sample output:
   ```
   Master Instance is mysql-mha-test-master
   ```
4. Promote a new Master Instance (/)

   ```
   curl -X POST http://<LB ENDPOINT>:<PORT>/manage-gce-floating-ip/api/v1.0/promote-master/<name of the new master node>
   ```
   
   Sample call and output:
   ```
   curl -X POST 34.128.69.75:8080/manage-gce-floating-ip/api/v1.0/promote-master/mysql-mha-test-slave1
   Instance mysql-mha-test-slave1 successfully promoted to new master
   ```
