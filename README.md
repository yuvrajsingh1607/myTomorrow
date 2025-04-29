# Flask App deployment on Minikube nodes by utilizing Terraform, Helm and Kubernetes
This project is a part of the assignment to deploy Flask application using Helm, terraform and Kubernetes. It demonstrates how to containerize a flask app, manage configurations with environment variables, and deploy it on Kubernetes clusters running on 2 node minikube nodes.
## 1. Installation

Docker images are kept at:
```
    https://hub.docker.com/repository/docker/yuvrajone/mytomorrow/general
````
Code base is kept on Github repository:
```
https://github.com/yuvrajsingh1607/myTomorrow
```

To get started with this project:

1. Clone the repository:
```bash
    git clone git@github.com:yuvrajsingh1607/myTomorrow.git
```   
2. Install and configure Terraform, Helm and Kubectl commands on laptop
3. validate, plan and apply changes using Terraform. Pass environment variable dev or prod based on the environment being deployed when prompted:
```bash
    cd terraform
    terraform init
    terraform fmt 
    terraform validate
    terraform plan
    terraform apply
```
4. install Prometheus and Grafana:
```bash
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install monitoring prometheus-community/kube-prometheus-stack
```
5. Get the login details of the Grafana
```bash
    kubectl get secrets monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 --decode
```
## 2. Usage
Once the application is deployed, you can access it through the following endpoints:

1. Get the endpoint:
```bash
    minikube service dev-flask-app --url -n mytomorrow
```
2. access the application endpoints using curl or web browser. change the port based on the output of the command executed in step 1.
```bash
    http://127.0.0.1:54240
    http://127.0.0.1:54240/config/
```
3. port forward to access grafana dashboard:
```bash
    kubectl port-forward svc/monitoring-grafana 3000:80
```
4. access grafana dashboard with credentials captured earlier:
```bash
    http://localhost:3000/dashboards
```
## 3. Configuration
- files ./terraform/vlues/dev.yaml and ./terrafor/values/prod.yaml contains environment specific variables
- file ./terraform/main.tf contains OS variables consumed by the flask application including secrets created using random_password terraform resource
- file ./terraform/variables.tf file contains default variables
- helm creates flask-app application on kubernetes cluster running on 2 minikube nodes. application cluster Prod or Dev is created based on the variable passed to "terraform apply" command.
- Deployment, Horizontal Pod Autoscaler, Pod Disruption Budget , Pod Affinity, Liveness and Rediness Probes are implemented using files under ./helm/flask-app/templates folder.
- Dockerfile contains configuration required to build the application image. Minimal Alpine Linux is used to host the flask application. non-root user named appuser is created to run the application.

## 4. Design approach
- Application Structure: The application's design and deployment incorporate Docker, Kubernetes, Helm, and Terraform, as specified in the assignment. The Flask application is deployed as a microservice, optimized for low maintenance and minimal resource usage. APIs are accessible via the root path / and the /config endpoint, while Kubernetes readiness checks are available at the /healthz path.
- Containerization: The Docker container is built using the lightweight and secure python:3.13-alpine image. It runs the Flask application under a non-root user with a read-only file system for enhanced security. The application retrieves the DB_SECRET and SECRET_KEYS via environment variables, which are provided through Helm and Terraform during deployment.
- Infrastructure and Application deployment: Kubernetes manifest files are managed using Helm, while the deployment process is orchestrated through Terraform. Environment-specific deployments are handled by passing DEV or PROD keywords to the terraform apply command. This approach allows a single Helm and Terraform codebase to be reused across both development and production environments.
- Kubernetes: The Flask app is deployed using a Kubernetes Deployment resource, which manages rolling updates and self-healing. The number of replicas is configurable via Helm’s values.yaml, enabling the app to scale horizontally based on expected traffic or reliability needs. Anti-affinity rules are defined to prefer scheduling pods on separate nodes, avoiding placing all replicas on the same physical host. This improves fault tolerance if one node fails, not all replicas are lost. 
An HPA resource is included to monitor CPU usage and automatically scale the number of pods up or down. This allows the application to adapt to real-time workload changes, helping maintain performance without over-provisioning. A PDB ensures that during maintenance operations (like node reboots or upgrades), a minimum number of pods remain running. This protects service availability during voluntary disruptions, minimizing user impact. A NodePort service exposes the app on a consistent port, allowing access via the node’s IP.

## 5. AWS Networking Strategy for PROD env:
To ensure a secure and scalable deployment of the application, the following architecture design is proposed:

1. Virtual Private Cloud (VPC):
A dedicated VPC will be created to host the application. This isolates the application infrastructure from other cloud resources and provides full control over networking components.

2. Subnets and Availability Zones:
The Flask application will be deployed in private subnets to reduce public exposure. At least two Availability Zones (AZs) will be used to ensure high availability and fault tolerance across multiple physical locations. Public subnets will be used to provision Load balancer which route traffic to the flask application running in private network.

3. NAT Gateway:
A NAT Gateway is not required, as the Flask application is packaged in Docker images that do not require any package downloads at deployment time.

4. TLS/SSL Security:
AWS Certificate Manager (ACM) will be used to provision and manage SSL/TLS certificates. The SSL certificate will be terminated at an Application Load Balancer (ALB). The ALB will reside in a public subnet and securely route traffic to the Kubernetes cluster in private subnets.

5. Load Balancer and Routing:
The ALB will handle inbound HTTPS traffic and forward it to the backend services running in the Kubernetes cluster Security Groups will be configured to allow traffic from the ALB to the Kubernetes nodes that host the Flask application.

6. DNS Configuration:
DNS records will be configured to route external browser or client traffic targeting the API hostname to the ALB, ensuring secure and reliable access to the application endpoints.

## 6. Access to AWS services:
 Enable the default IAM role when provisioning an EKS cluster. This role can be used to manage access to various AWS resources. We can later import this resource into Terraform, create new policies as needed, and attach those policies to the role. This approach allows us centralized access control and proper security management while automating the infrastructure and ensuring consistency across deployments.
 We can create Role and RoleBinding resources for K8 namespace-specific permissions and assign them to the IAM users using ConfigMap. This allows us to control access to resources within the namespace based on the IAM policies.

## 7. CI/CD:
1. DEV CI/CD pipeline:
- Developer creates a new branch and update the flask application related codebase. After code changes, user push the change to Github repository hosting code base of the flask application.
- Jenkins docker build job runs and build a new docker image with a new tag and upload the image to ECR with the latest tag.
- once the ECR have the latest image, another Jenkins jobs "update deployment manifest" executes which update the image reference in the deployment manifest file with latest tag and update the github repository hosting the terraform and helm charts in a new branch.
- Final Jenkins job "Deployment application" find the new chnges in the deployment manifest file and deploy the new container on the K8 cluster with the predefined variable env=dev with make sure to deploy the application on right K8 cluster.
- Run the application health checks and if all looks good then create a merge-request to merge new branch into main branch in the flask application repository and same for helm repository. 
2. PROD CI/CD pipeline:
- Once merge requests are approved and merged, "Deploy application" runs and execte pre checks like terraform plan with the env=prod variable. Hold the Pipeline to validate the required changes.
- Validate the output of the job and if all looks good then run the pipeline to deploy the new application on the Prod K8 cluster with predefined environment variable env=prod to make sure that Prod related variables are applied to the Prod env only. The Jenkins node should have the required authentication configured for Prod and Dev env.
3. Pre Checks in the CICD pipeline:
- integrate SonarQuebe to validate the vulnerabilities in the code base
- integrate linting to make sure that code has the required formating and syntax
- integrate Unit tests to reduce the manual application validation
## 8. Trade-offs:
- We should have the AWS Secret Manager implemented to store the DB_Secret and Secret_keys and rotate the secrets every 90 days. Need to have the terraform code changes to rotate the secrets every 90 days and fetch the secrets from SM and create a new deployment CI/CD pipeline to deploy the containers with latest secrets. This solution should be implemented if there is a security and compliance requirements.
- Running multiple Nodes with HPA and CLuster Autoscaling will bring more cost to the project.
- There will be a long project deliery timelines if requirements are to automate all the parts of the CI/CD and enabling security into the solution
- This solution does not have the Cluster autoscaler as the K8 cluster is running on a Minikube.
## 9. scalability, availability, security, and fault tolerance: 
1. Scalability: HPA is used in the solution to make sure that pods scaling handle the traffic on the cluster. 
2. Availability: Multi node cluster is used and multiple pods are running using Node Afinity to make sure that each pods run on different nodes. 
3. Security: Docker containers are running with non-root user and on a read-only file system with latest and lightweight Linux image. Secrets are generated using terraform random_passord resource hence secrets are not part of the code base.
4. Fault tolarance: Flask application is running on 2 node and 2 pods. K8 automatically detects failed pods and replaces them hence maintaining application availability with fault tolarance.

## 10. Potential Enhancements:
1. We could have used AWS EKS to deploy the application enabling HA, Security and Scalable infrastructure.
2. Use AWS ALB, SM, DNS, IAM, VPC and ACM in the solution instead of using MiniKube.
3. Secrets could be kept on SM and periodically rotation could be done using AWS Lambda functions. 
4. Could integrate AWS Inspector and WAF to have more secure env.
