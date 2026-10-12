variable "name" {
  description = "Prefix for resource names and tags (e.g. poc)."
  type        = string
}

variable "vpc_cidr" {
  type = string
}

variable "public_subnet_cidr" {
  type = string
}

variable "private_subnet_cidr" {
  type = string
}

variable "availability_zone" {
  description = "Single AZ for POC cost minimization."
  type        = string
}
