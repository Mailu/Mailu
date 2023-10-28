<!--

Thank you for opening an issue with Mailu. Please understand that issues are meant for bugs only. The bug report should follow the issue template and provide clear replication steps and logs.
For **user-support questions**, reach out to us  on [matrix](https://matrix.to/#/#mailu:tedomum.net) or [disussions](https://github.com/Mailu/Mailu/discussions/categories/user-support).

For anything but bug reports use the [matrix channel](https://matrix.to/#/#mailu:tedomum.net) or [disussions](https://github.com/Mailu/Mailu/discussions).
So use discussions for topics such as

* Checking announcements.
* General discussion about Mailu usage or using Mail software in general.
* Feature requests
* User support.

To be able to help you best, we need some more information.

Before you open your issue
- Check if no issue or pull-request for this already exists.
- Check [documentation](https://mailu.io/master/) and [FAQ](https://mailu.io/master/faq.html). (Tip, use the search function on the documentation page)
- You understand `Mailu` is made by volunteers in their **free time** — be concise, civil and accept that delays can occur.
- The title of the issue should be short and simple. It should contain specific terms related to the actual issue. Be specific while writing the title.
- You understand issues are only meant for bug reports that follow the issue template. Non bug reports or bug reports that do not follow the template will be moved to [disussions](https://github.com/Mailu/Mailu/discussions)

Please put your text outside of the comment blocks to be visible. You can use the button "Preview" above to check.

If you do not follow the issue template suggested below your issue may be summarily closed.

-->

## Environment & Version

- `docker compose version`
- Version: `master`

<!--
To find your version, get the image name of a mailu container and read  the version from the tag (example for version 1.7).

$> docker ps -a | grep mailu
140b09d4b09c    mailu/roundcube:1.7    "docker-php-entrypoi…"    2 weeks ago    Up 2 days (healthy)    80/tcp
$> grep MAILU_VERSION docker-compose.yml mailu.env
-->

If you are not using docker compose do not file any new issue here.
Kubernetes related issues belong to https://github.com/Mailu/helm-charts/issues
If you are not using docker compose or kubernetes, create a new thread on user support in [disussions](https://github.com/Mailu/Mailu/discussions/categories/user-support).
Non-bug reports (or bug reports that do not follow the template) are moved to [disussions](https://github.com/Mailu/Mailu/discussions).

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
or using docker compose `docker compose -f /mailu/docker-compose.yml logs --tail 1000 admin`

If you can find the relevant section, please share only the parts that seem relevant. If you have any logs, please enclose them in code tags and in a section, like so:

```
Your logs here!
```

-->
