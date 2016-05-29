require ["fileinto", "envelope", "mailbox"];

if header :contains "X-Spam" "YES" {
  fileinto :create "Junk";
}
