variable "name" {
  type = string
}

variable "enabled" {
  type    = bool
  default = false
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Subnets for the internal NLB and the API Gateway VPC Link ENIs."
  type        = list(string)
}

variable "app_instance_id" {
  description = "EC2 instance id running the Lodestone container to register behind the NLB."
  type        = string
}

variable "app_port" {
  type    = number
  default = 8080
}

variable "health_check_path" {
  type    = string
  default = "/docs"
}
