# build.hcl
# For more information on buildx bake file definition see:
# https://github.com/docker/buildx/blob/master/docs/guides/bake/file-definition.md
#
# NOTE: You can only run this from the Mailu root folder.
# Make sure the context is Mailu (project folder) and not Mailu/tests
#-----------------------------------------------------------------------------------------
# (Environment) input variables
# If the env var is not set, then the default value is used
#-----------------------------------------------------------------------------------------
variable "DOCKER_ORG" {
  default = "mailu"
}
variable "DOCKER_PREFIX" {
  default = ""
}
variable "PINNED_MAILU_VERSION" {
  default = "local"
}
variable "MAILU_VERSION" {
  default = "local"
}

#-----------------------------------------------------------------------------------------
# Grouping of targets to build. All these images are built when using:
# docker buildx bake -f tests\build.hcl
#-----------------------------------------------------------------------------------------
group "default" {
  targets = [
    "docs",
    "setup",

    "admin",
    "antispam",
    "front",
    "imap",
    "smtp",

    "rainloop",
    "roundcube",

    "antivirus",
    "fetchmail",
    "resolver",
    "traefik-certdumper",
    "webdav"
  ]
}

#-----------------------------------------------------------------------------------------
# Default settings that will be inherited by all targets (images to build).
#-----------------------------------------------------------------------------------------
target "defaults" {
  platforms = [ "linux/amd64"]
  dockerfile = "Dockerfile"
  args = {
    VERSION = "${PINNED_MAILU_VERSION}"
  }
}

#-----------------------------------------------------------------------------------------
# User defined functions
#------------------------------------------------------------------------------------------
# Derive all tags
function "tag" {
  params = [image_name]
  result = [  notequal("master",MAILU_VERSION) && notequal("master-arm",MAILU_VERSION) ? "${DOCKER_ORG}/${DOCKER_PREFIX}${image_name}:${PINNED_MAILU_VERSION}": "",
             "${DOCKER_ORG}/${DOCKER_PREFIX}${image_name}:${MAILU_VERSION}",
             "${DOCKER_ORG}/${DOCKER_PREFIX}${image_name}:latest"
          ]
}

#-----------------------------------------------------------------------------------------
# All individual targets (images to build)
# Build an individual target using.
# docker buildx bake -f tests\build.hcl <target>
# E.g. to build target docs
# docker buildx bake -f tests\build.hcl docs
#-----------------------------------------------------------------------------------------

# -----------------------------------------------------------------------------------------
# Documentation and setup images
# -----------------------------------------------------------------------------------------
target "docs" {
  inherits = ["defaults"]
  context = "docs"
  tags = tag("docs")
  args = {
    version = "${MAILU_VERSION}"
    pinned_version = "${PINNED_MAILU_VERSION}"
  }
}

target "setup" {
  inherits = ["defaults"]
  context="setup"
  tags = tag("setup")
}

# -----------------------------------------------------------------------------------------
# Core images
# -----------------------------------------------------------------------------------------
target "none" {
  inherits = ["defaults"]
  context="core/none"
  tags = tag("none")
}

target "admin" {
  inherits = ["defaults"]
  context="core/admin"
  tags = tag("admin")
}

target "antispam" {
  inherits = ["defaults"]
  context="core/rspamd"
  tags = tag("rspamd")
}

target "front" {
  inherits = ["defaults"]
  context="core/nginx"
  tags = tag("nginx")
}

target "imap" {
  inherits = ["defaults"]
  context="core/dovecot"
  tags = tag("dovecot")
}

target "smtp" {
  inherits = ["defaults"]
  context="core/postfix"
  tags = tag("postfix")
}

# -----------------------------------------------------------------------------------------
# Webmail images
# -----------------------------------------------------------------------------------------
target "rainloop" {
  inherits = ["defaults"]
  context="webmails/rainloop"
  tags = tag("rainloop")
}

target "roundcube" {
  inherits = ["defaults"]
  context="webmails/roundcube"
  tags = tag("roundcube")
}

# -----------------------------------------------------------------------------------------
# Optional images
# -----------------------------------------------------------------------------------------
target "antivirus" {
  inherits = ["defaults"]
  context="optional/clamav"
  tags = tag("clamav")
}

target "fetchmail" {
  inherits = ["defaults"]
  context="optional/fetchmail"
  tags = tag("fetchmail")
}

target "resolver" {
  inherits = ["defaults"]
  context="optional/unbound"
  tags = tag("unbound")
}

target "traefik-certdumper" {
  inherits = ["defaults"]
  context="optional/traefik-certdumper"
  tags = tag("traefik-certdumper")
}

target "webdav" {
  inherits = ["defaults"]
  context="optional/radicale"
  tags = tag("radicale")
}