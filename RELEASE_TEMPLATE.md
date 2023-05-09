This is a new automatic release of Mailu. The new version can be seen in the tag name.
The main version X.Y (e.g. 2.1) will always reflect the latest version of the branch. To update your Mailu installation simply pull the latest images `docker compose pull && docker compose up -d`.
The pinned version X.Y.Z (e.g. 2.1.1) is not updated. It is pinned to the commit that was used for creating this release. You can use a pinned version to make sure your Mailu installation is not suddenly updated when recreating containers. The pinned version allows the user to manually update. It also allows to go back to a previous pinned version.

To check what was changed:
- Go to https://github.com/Mailu/Mailu/tree/master/towncrier/newsfragments
- Change the branch to the tag of this release.
- Read the news fragment files to check what was changed.

The release notes of the original release can be accessed via menu item 'Release notes' on [mailu.io](https://mailu.io/).
