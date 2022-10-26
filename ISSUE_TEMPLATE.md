<!--

Thank you for opening an issue with Mailu. Please understand that issues are meant for bugs and enhancement-requests.
For **user-support questions**, reach out to us  on [matrix](https://matrix.to/#/#mailu:tedomum.net).

To be able to help you best, we need some more information.

Before you open your issue
- Check if no issue or pull-request for this already exists.
- Check [documentation](https://mailu.io/master/) and [FAQ](https://mailu.io/master/faq.html). (Tip, use the search function on the documentation page)
- You understand `Mailu` is made by volunteers in their **free time** — be concise, civil and accept that delays can occur.
- The title of the issue should be short and simple. It should contain specific terms related to the actual issue. Be specific while writing the title.

Please put your text outside of the comment blocks to be visible. You can use the button "Preview" above to check.

-->

## Environment & Version

### Environment

- [ ] docker-compose
- [ ] kubernetes
- [ ] docker swarm

### Version

- Version: `master`

<!--
To find your version, get the image name of a mailu container and read  the version from the tag (example for version 1.7).

$> docker ps -a | grep mailu
140b09d4b09c    mailu/roundcube:1.7    "docker-php-entrypoi…"    2 weeks ago    Up 2 days (healthy)    80/tcp
$> grep MAILU_VERSION docker-compose.yml mailu.env
-->

## Description
<!--
Further explain the bug in a few words. It should be clear what the unexpected behaviour is.  Share it in an easy-to-understand language.
-->

## Replication Steps
<!--
Steps for replicating your issue
-->

## Observed behaviour
<!--
Explain or paste the result you received.
-->

## Expected behaviour
<!--
Explain what results you expected - be as specific as possible.
Just saying "it doesn’t work as expected" is not useful. It's also helpful to describe what you actually experienced.
-->

## Logs
<!--
Often it is very useful to include log fragments of the involved component.
You can get the logs via `docker logs <container name> --tail 1000`.
For example for the admin container: `docker logs mailu_admin_1 --tail 1000`
or using docker-compose `docker-compose -f /mailu/docker-compose.yml logs --tail 1000 admin`

If you can find the relevant section, please share only the parts that seem relevant. If you have any logs, please enclose them in code tags, like so:

```
Your logs here!
```
-->
