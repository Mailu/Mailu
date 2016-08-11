require ["fileinto", "envelope", "mailbox", "imap4flags"];

if header :contains "X-Spam" "YES" {
  setflag "\\seen";
  fileinto :create "Junk";
}
