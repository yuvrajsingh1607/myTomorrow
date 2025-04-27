# Flask App withTerraform, Helm and Kubernetes Deployment on Minikube nodes
This project is a simple Flask application deployed using Helm on Kubernetes. It demonstrates how to containerize a Python app, manage configurations with environment variables, and deploy it on Kubernetes clusters using Helm charts.
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
- Deployment, Horizontal Pod Autoscaler, Pod Disruption Budget , Pod Affinity, Liveness and Rediness Probes are implemented using files under ./heml/flask-app/templates folder.
- Dockerfile contains configuration required to build the application image. Minimal Alpine Linux is used to host the flask application. non-root user named appuser is created to run the application.