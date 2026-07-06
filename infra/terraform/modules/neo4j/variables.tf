variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "subnet_id" {
  description = "Subnet for the Neo4j instance (public for POC egress without NAT)."
  type        = string
}

variable "availability_zone" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "r7g.large"
}

variable "data_volume_gb" {
  type    = number
  default = 50
}

variable "neo4j_image" {
  type    = string
  default = "neo4j:5"
}

variable "neo4j_password" {
  type      = string
  sensitive = true
}

variable "heap_size" {
  type    = string
  default = "4g"
}

variable "pagecache_size" {
  type    = string
  default = "9g"
}
