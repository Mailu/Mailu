require ["fileinto", "envelope", "mailbox", "imap4flags"];

if header :contains "X-Spam" "YES" {
  fileinto :create "Junk";
  setflag "\\seen";
}
