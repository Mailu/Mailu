Setup a new Mailu server
========================

Things to consider
------------------

Mailu is working, it has been powering hundreds of e-mail accounts
since around January 2016, and has delivered over a million emails.
It is still not massively tested however and
you should not run any critical mail server until you have properly tested
every feature.

Also, the idea behind Mailu is based on the work by folks from Poste.io.
If free software is not the reason you chose Mailu or if you are seeking
long-term professional support, you should probably turn to them instead.

Prepare the environment
-----------------------

Mailu images are designed to work on x86 or equivalent hardware, so it
should run on pretty much any cloud server as long as enough power is
provided. For non x86 machines, see :ref:`arm_images`

You are free to choose any operating system that runs Docker (>= 1.11),
then chose between various flavors including Docker Compose, Kubernetes
and Rancher.

Compose is the most tested flavor and should be the choice for less experienced
users. Make sure you complete the requirements for the flavor you chose.

You should also have at least a DNS hostname and a DNS name for receiving
emails. Some instructions are provided on the matter in the article
:ref:`dns_setup`.


Pick a Mailu version
--------------------

Mailu is shipped in multiple versions.

- ``1.9`` features the most recent stable version for Mailu. This is the
  recommended build for new setups, old setups should migrate when possible.

- ``1.0``, ``1.1``, and other version branches feature old versions of Mailu
  they will not receive any more patches (except for the stable one) and you should
  not remain forever on one of those branches; you could however setup the stable
  branch by number to avoid introducing unexpected new feature until you read the
  changelog properly. This is the most conservative option.

- ``latest`` points at the latest build from the master
  development branch. It will most likely contain many more bugs, also you should
  never use it for a production server. You are more than welcome to run a testing
  server however and report bugs.

Perform the specific setup steps
--------------------------------

Specific setup steps are described per flavor (Compose, Kubernetes, etc.)
and you should follow the steps after completing the requirements.

After setting up your flavor, continue to the DNS setup instructions,
additional steps in the admin dashboard will be needed to generate your
DMARC and SPF/DKIM keys.

Make sure that you test properly before going live!

- Try to send an email to an external service
- On the external service, verify that DKIM and SPF are listed as passing
- Try to receive an email from an external service
- Check the logs (``docker-compose logs -f servicenamehere``) to look for
  warnings or errors
- Use an open relay checker like `mxtoolbox`_
  to ensure you're not contributing to the spam problem on the internet.
- If using DMARC, be sure to check the reports you get to verify that legitimate
  email is getting through and forgeries are being properly blocked.

  .. _mxtoolbox: https://mxtoolbox.com/diagnostic.aspx
