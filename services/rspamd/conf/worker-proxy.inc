bind_socket = "*:11332";
upstream "local" {
  default = yes;
  self_scan = yes;
}
