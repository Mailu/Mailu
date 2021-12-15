Use semantic versioning for building releases.
- Add versioning (tagging) for branch x.y (1.8). E.g. 1.8.0, 1.8.1 etc.
  - docker repo will contain x.y (latest) and x.y.z (pinned version) images.
  - The X.Y.Z tag is incremented automatically. E.g. if 1.8.0 already exists, then the next merge on 1.8 will result in the new tag 1.8.1 being used.
- Make the version available in the image.
  -  For X.Y and X.Y.Z write the version (X.Y.Z) into /version on the image and add a label with version=X.Y.Z
	  -  This means that the latest X.Y image shows the pinned version (X.Y.Z e.g. 1.8.1) it was based on. Via the tag X.Y.Z you can see the commit hash that triggered the built.
  -  For master write the commit hash into /version on the image and add a label with version={commit hash}
-  Automatic releases. For x.y triggered builts (e.g. merge on 1.9) do a new github release for the pinned x.y.z (e.g. 1.9.2). 
  -  Release shows a static message (see RELEASE_TEMPLATE.md) that explains how to reach the newsfragments folder and change the branch to the tag (x.y.z) mentioned in the release. Now you can get the changelog by reading all newsfragment files in this folder.