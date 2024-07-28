## New Feature

This pull request adds the following feature(s):
<!--
  Add the features this PR adds here. If they are related to an issue, reference it, prepend with 'closes' to auto-close them on merge.

  Examples:
    - Allow setting up multiple OIDC providers
    - Allow setting up OIDC from the UI
  
  If this PR adds multiple features, make sure they are closely related. If not, consider creating multiple PRs.
-->
- Your feature here. closes #000

## Details of Implementation

### What's new

<!--
  Describe the feature(s) after successful implementation.

  Examples:
    - Multiple OIDC providers can now be set up (see guide below)
    - OIDC can now be set up from the UI (see screenshots below)
-->

### Breaking changes

<!--
  Describe any breaking changes introduced by this enhancement. If there are none, you can remove this section.

  Examples:
    - The `OIDC_PROVIDER_INFO_URL` was renamed to `OIDC_PROVIDER_INFO_URL<number>`, where `<number>` is the provider number, i.e. `OIDC_PROVIDER_INFO_URL1`
    - The `OIDC_` prefixed properties were removed. Set up OIDC providers from the UI instead.
  
  It can be helpful to provide a migration path for users to follow, which can be added to the documentation later.
-->

### Previous behavior

<!--
  Describe the feature(s) before the enhancement.

  Examples:
    - Only one OIDC provider could be set up
    - OIDC could only be set up from the `mailu.env` file
-->

## Checklist

Before we can consider review and merge, please make sure the following list is done and checked.

- [ ] Make sure you follow our [Code of Conduct](https://github.com/heviat/Mailu-OIDC/blob/master/CODE_OF_CONDUCT.md).
- [ ] This new feature is tested and works as expected.
- [ ] This new feature introduces new functionality[^1].
- [ ] This enhancement does not break any existing functionality, or breaks it intentionally (documented above).
- [ ] Unless it's a minor change: Add a [Changelog](https://mailu.io/master/contributors/workflow.html#changelog) entry file.

[^1]: If this pull request enhances existing functionality, please create an enhancement pull request instead. For bug fixes, create a bug-fix pull request instead.
