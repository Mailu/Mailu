Contribution workflow
=====================

.. _git_workflow:

Forking vs. committing
----------------------

Linus' way of things sounds fine for now: if you find yourself implementing a
new feature, either send me an email with a bunch of commits or use Github
pull request feature. Maybe if the user base grows too much as well as the need
for trust in a specific branch of the project, we can switch to a shared
repository and add a couple of trusted committers.

Commits
-------

This is a community project, thus commits should be readable enough for any of
the contributors to guess the content by simply reading the comment or find a
proper commit when one knows what they are looking for.

Usual standards remain: write english comments, single line short comments and
additional multiline if required (keep in mind that the most important piece
of information should fit in the first line).

Branches
--------

You are of course free of naming you branches to your taste or even using
master directly if you find this appropriate. Still, keep in mind that:

- a git email or a pull request should address a single feature a bug,
  so keep your branches as tidy as possible;
- this is a small project with a limited number of forks and active threads
  on Github, so someone might want to look at your fork and find the branch you
  are using to implement a specific feature; to avoid any hassle, we suggest
  that you use branch names prefixed with ``feat-`` or ``fix-`` and followed
  either by the name of the Github issue or a short and meaningful name.

PR Workflow
-----------

All pull requests have to be against the main ``master`` branch.
The PR gets build by a Github Action workflow and some primitive auto-testing is done.
Test images get uploaded to a separate section in Docker hub.
Reviewers will check the PR and test the resulting images.
See the :ref:`testing` section for more info.

Urgent fixes can be backported to the stable branch.
For this a member of **Mailu/contributors** has to set the ``type/backport`` label.
Upon merge of the original PR, a copy of the PR is created against the stable branch.
After some testing on master, we will approve and merge this new PR as well.

At the end of every milestone, a new stable branch will be created from ``master``
or any previous commit that matches the completion of the milestone.

CHANGELOG
---------

Adding entries in the CHANGELOG is an automated process which requires creation of a file under
``towncrier/newsfragments`` directory.

The start of the filename is the ticket number, and the content is what will end up in the news file.
For example, if ticket ``#850`` is about adding a new widget, the filename would be towncrier/newsfragments/850.feature
and the content would be ``Feature that has just been added``.

Supported file extensions are:

- ``.feature``: Signifying a new feature.
- ``.bugfix``: Signifying a bug fix.
- ``.doc``: Signifying a documentation improvement.
- ``.removal``: Signifying a deprecation or removal of public API.
- ``.misc``: A ticket has been closed, but it is not of interest to users.

Forked projects
---------------

If you find yourself forking the project for a specific independent purpose
(commercial use, different philosophy or incompatible point of view), we would
be glad if you let us know so that we can list interesting known forks and
their specific features (and backport some of them if your implementation
is free as well).
