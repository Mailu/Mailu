# syntax=docker/dockerfile-upstream:1.4.3

# rspamd image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache rspamd rspamd-controller rspamd-fuzzy rspamd-proxy \
  ; mkdir /run/rspamd \
  ; mkdir /overrides

# TEMPORARY PATCH -- remove this comment and the RUN block below, nothing else.
#
# Alpine 3.22 builds rspamd against PUC-Rio Lua 5.4 instead of LuaJIT. dmarc.lua
# hands the fractional double from task:get_date() to os.date(); LuaJIT truncated
# it, Lua 5.3+ rejects it. The exception aborts the DNS callback before any report
# data reaches redis, so DMARC reporting silently collects nothing. Policy
# evaluation is unaffected -- the symbols are inserted earlier in the function.
#
# Fixed in rspamd master, in no release up to 3.13.0:
# https://github.com/rspamd/rspamd/blob/master/src/plugins/lua/dmarc.lua
#
# HOW THIS ENDS: the build fails as soon as the packaged dmarc.lua already
# carries the fix. When that happens, delete this comment and the RUN block --
# no other file participates in this workaround.
RUN set -euxo pipefail \
  ; f=/usr/share/rspamd/plugins/dmarc.lua \
  ; if grep -q 'math.floor(task:get_date' "$f" ; then \
      echo "rspamd ships the DMARC reporting fix: delete this RUN block" >&2 ; exit 1 ; \
    fi \
  ; sed -i "s#^\( *\)task:get_date({ format = 'connect', gmt = false }))#\1math.floor(task:get_date({ format = 'connect', gmt = false })))#" "$f" \
  ; grep -q 'math.floor(task:get_date' "$f"

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 11332/tcp 11334/tcp 11335/tcp
HEALTHCHECK --start-period=350s CMD curl -m3 -skfLo /dev/null http://localhost:11334/

VOLUME ["/var/lib/rspamd"]

CMD /start.py
