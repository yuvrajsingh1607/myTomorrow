# use random_password resource to create a password used for DB access
resource "random_password" "mytomorrow-db-password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# use random_password resource to create a secret-key
resource "random_password" "mytomorrow-secret-key" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?@"
}

# create API base URL based on the environment
locals {
  api_base_url = "https://${var.env}.api.my-tomorrow.nl"
}

# create resource flask_app and deploy the application using terraform
resource "helm_release" "flask_app" {
  name             = "${var.env}-flask-app"
  chart            = "../helm/flask-app"
  namespace        = var.namespace
  create_namespace = true
# get variable values from dev.yaml or prod.yaml file based on the environment being deployed
  values = [
    file("./values/${var.env}.yaml")
  ]

# Pass variables to the helm
  set_sensitive {
  name  = "secrets.db_password"
  value = random_password.mytomorrow-db-password.result
  }

  set_sensitive {
  name  = "secrets.secret_key"
  value = random_password.mytomorrow-secret-key.result
  }

  set {
  name  = "env.API_BASE_URL"
  value = local.api_base_url
  }

set {
  name  = "namespace"
  value = var.namespace
  }

}

