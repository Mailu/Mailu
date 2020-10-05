FROM mailu/roundcube:master

###Begin Package additions###
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libicu-dev \
    libjpeg62-turbo-dev \
    libldap2-dev \
    libpng-dev \
    libpq-dev \
    libsqlite3-dev \
    libzip-dev \
    libmcrypt-dev \
    python3-jinja2 \
    gpg \
    zlib1g-dev \
    unzip \
    libzip4 \
    ; \
    debMultiarch="$(dpkg-architecture --query DEB_BUILD_MULTIARCH)"; \
    docker-php-ext-configure gd --with-freetype-dir=/usr/include/ --with-png-dir=/usr --with-jpeg-dir=/usr; \
    docker-php-ext-configure ldap --with-libdir="lib/$debMultiarch"; \
    docker-php-ext-install \
    exif \
    gd \
    intl \
    ldap \
    pdo_mysql \
    pdo_pgsql \
    pdo_sqlite \
    zip \
    ; \
    rm -rf /var/lib/apt/lists/*

RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/bin --filename=composer
###End Package additions###

CMD /start.py
HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1