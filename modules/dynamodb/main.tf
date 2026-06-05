resource "aws_dynamodb_table" "releases" {
  name         = "releases"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "service"
  range_key = "version_id"

  attribute {
    name = "service"
    type = "S"
  }

  attribute {
    name = "version_id"
    type = "S"
  }
}