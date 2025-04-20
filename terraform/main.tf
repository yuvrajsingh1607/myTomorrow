resource "random_password" "mytomorrow-db-password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "mytomorrow-secret-key" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?@"
}

locals {
  api_base_url = "https://${var.env}.api.my-tomorrow.nl"
}

resource "helm_release" "flask_app" {
  name             = "${var.env}-flask-app"
  chart            = "../helm/flask-app"
  namespace        = var.namespace
  create_namespace = true

  values = [
    file("./values/${var.env}.yaml")
  ]

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

