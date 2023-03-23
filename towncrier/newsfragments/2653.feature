Provide a changelog for minor releases. The github release will now:
* Provide the changelog message from the newsfragment of the PR that triggered the backport.
* Provide a github link to the PR/issue of the PR that was backported.

Switch to building multi-arch images. The images build for pull requests, master and production
are now multi-arch images for the architectures:
* linux/amd64
* linux/arm64/v8
* linux/arm/v7

Enhance CI/CD workflow with retry functionality. All steps for building images are now automatically
retried. If a build temporarily fails due to a network error, the retried step will still succeed.