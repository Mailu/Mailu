require ["fileinto", "envelope", "mailbox"];

if header :contains "X-Spam-Flag" "YES" {
  fileinto :create "Junk";
}
