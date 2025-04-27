# environment details should be passed while terraform apply
variable "env" {
  type = string
}

# default namespce to run the flask application
variable "namespace" {
  type = string
  default = "mytomorrow"
}
