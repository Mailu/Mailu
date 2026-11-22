# Alpine Dovecot backports

This directory contains the Alpine 3.24 Dovecot package backports. The
`dovecot-package-build` stage in `core/base/Dockerfile` applies them to Alpine's
`main/dovecot` APKBUILD and builds the APKs in a throwaway container. The base
image carries the signed APK files; `imap` and `front` install their own
package sets from those files. The APKBUILD delta is kept separately so the
patch series can be proposed to Alpine aports without extracting changes from
a Mailu-specific build step.

The two source patches are:

* `0001-login-common-keep-post-login-fd-open.patch`, Dovecot commit
  `98665ed44141f5c64078eeaf937c4224403eb9ce`.
* `0002-imap-empty-partial-as-quoted.patch`, Dovecot PR #317 commit
  `fac4eb5c29d70cbfcd1ccf5147edf0316f12d223`.

`APKBUILD.patch` bumps `pkgrel`, declares Perl as a build dependency, and adds
both patches and their SHA-512 sums to Alpine's recipe. It applies to aports commit
`75e10f2ea64d8adbc06fcec9aea3be394f383a46`, which contains Dovecot 2.4.5-r0.
The package build target is intentionally pinned to that recipe revision; when
Alpine updates the 3.24 package, rebase the APKBUILD delta and verify both
patches against the new Dovecot source before updating the pin.

The IMAP server enables `tb-extra-mailbox-sep`, `tb-lsub-flags`, and
`empty-partial-as-quoted` by default. The latter option is provided by the
second source patch; it cannot be enabled with Alpine's unpatched Dovecot
package. `delay-newmail` remains disabled because it suppresses unsolicited
new-mail updates until NOOP/CHECK, conflicting with Mailu's IMAP IDLE updates.
