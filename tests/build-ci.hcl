# build-ci.hcl
#
# only used for Github actions workflow.
# For locally building images use build.hcl
#
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
  default = "ghcr.io/mailu"
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
variable "LABEL_VERSION" {
  default = "local"
}
variable "PINNED_LABEL_VERSION" {
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
    "oletools",
    "smtp",

    "webmail",

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
    VERSION = "${PINNED_LABEL_VERSION}"
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
# Base images
# -----------------------------------------------------------------------------------------
target "base" {
  inherits = ["defaults"]
  context = "core/base/"
  tags = tag("base")
}

target "assets" {
  inherits = ["defaults"]
  context = "core/admin/assets/"
  tags = tag("assets")
}

# -----------------------------------------------------------------------------------------
# Documentation and setup images
# -----------------------------------------------------------------------------------------
target "docs" {
  inherits = ["defaults"]
  context = "docs/"
  tags = tag("docs")
  args = {
    version = "${LABEL_VERSION}"
    pinned_version = "${PINNED_LABEL_VERSION}"
  }
}

target "setup" {
  inherits = ["defaults"]
  context = "setup/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("setup")
}

# -----------------------------------------------------------------------------------------
# Core images
# -----------------------------------------------------------------------------------------
target "none" {
  inherits = ["defaults"]
  context = "core/none/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("none")
}

target "admin" {
  inherits = ["defaults"]
  context = "core/admin/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
    assets = "docker-image://${DOCKER_ORG}/assets:${MAILU_VERSION}"
  }
  tags = tag("admin")
}

target "antispam" {
  inherits = ["defaults"]
  context = "core/rspamd/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("rspamd")
}

target "front" {
  inherits = ["defaults"]
  context = "core/nginx/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("nginx")
}

target "oletools" {
  inherits = ["defaults"]
  context = "core/oletools/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("oletools")
}

target "imap" {
  inherits = ["defaults"]
  context = "core/dovecot/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("dovecot")
}

target "smtp" {
  inherits = ["defaults"]
  context = "core/postfix/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("postfix")
}

# -----------------------------------------------------------------------------------------
# Webmail image
# -----------------------------------------------------------------------------------------
target "webmail" {
  inherits = ["defaults"]
  context = "webmails/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("webmail")
}

# -----------------------------------------------------------------------------------------
# Optional images
# -----------------------------------------------------------------------------------------
target "fetchmail" {
  inherits = ["defaults"]
  context = "optional/fetchmail/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("fetchmail")
}

target "resolver" {
  inherits = ["defaults"]
  context = "optional/unbound/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("unbound")
}

target "traefik-certdumper" {
  inherits = ["defaults"]
  context = "optional/traefik-certdumper/"
  tags = tag("traefik-certdumper")
}

target "webdav" {
  inherits = ["defaults"]
  context = "optional/radicale/"
  contexts = {
    base = "docker-image://${DOCKER_ORG}/base:${MAILU_VERSION}"
  }
  tags = tag("radicale")
}
