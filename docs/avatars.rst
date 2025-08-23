User Avatar System
==================

The User Avatar system allows users to upload, manage, and display profile pictures within the Mailu mail server. This feature provides both web UI and RESTful API access for avatar management, with automatic fallback to initials-based avatars.

Overview
--------

**Core Features:**

* User avatar upload through admin UI and REST API
* Automatic image processing, resizing, and optimization  
* Initials-based fallback avatars with consistent colors
* Secure file validation and storage management
* vCard export with embedded avatars for email clients
* Public API endpoints for external integration
* RFC 5785 compliant service discovery

**Integration Points:**

* Admin web interface with avatar management page
* Sidebar display of user avatars  
* REST API endpoints for programmatic access
* vCard generation for contact import/export
* External email client discovery mechanisms

Features
--------

Upload & Processing
~~~~~~~~~~~~~~~~~~~

* **Supported Formats**: PNG, JPG, JPEG, WebP
* **File Size Limit**: 2MB maximum
* **Auto-Processing**: Resize to 512×512, optimize quality
* **Security Validation**: MIME type detection, malicious content scanning

Storage & Management  
~~~~~~~~~~~~~~~~~~~

* **Secure Storage**: Configurable directory with proper permissions
* **Unique Filenames**: Hash-based naming prevents conflicts
* **Automatic Cleanup**: Old avatars removed when replaced
* **Fallback Generation**: Dynamic initials avatars when no upload

API Integration
~~~~~~~~~~~~~~~

* **Public Endpoints**: No authentication required for GET requests
* **RESTful Design**: Standard HTTP methods and status codes
* **vCard Export**: Contact data with embedded avatar images
* **Service Discovery**: RFC 5785 well-known URIs for external clients

External Integration
~~~~~~~~~~~~~~~~~~~

* **Email Clients**: Gmail, Outlook, Thunderbird compatibility
* **Contact Managers**: vCard import with avatar photos
* **Service Discovery**: Standardized endpoint discovery
* **CDN Ready**: Static file serving with caching support

API Endpoints
-------------

Get User Avatar
~~~~~~~~~~~~~~~

.. code-block::

   GET /admin/api/v1/user/{email}/avatar
Returns the user's avatar image or generates an initials-based fallback.

Upload User Avatar
~~~~~~~~~~~~~~~~~~

.. code-block::

   POST /admin/api/v1/user/{email}/avatar

**Parameters:**

* ``avatar``: Image file (multipart/form-data)

Delete User Avatar
~~~~~~~~~~~~~~~~~~

.. code-block::

   DELETE /admin/api/v1/user/{email}/avatar

Get Avatar Information
~~~~~~~~~~~~~~~~~~~~~

.. code-block::

   GET /admin/api/v1/user/{email}/avatar/info
Returns information about the user's avatar status.

Configuration
-------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

* ``AVATAR_STORAGE_PATH``: Directory for storing avatar files (default: ``/data/avatars``)

### Application Configuration

The avatar system can be configured through various settings in `avatar_config.py`:

- `MAX_AVATAR_SIZE`: Maximum file size in bytes (default: 2MB)
- `AVATAR_SIZE`: Target dimensions for processed images (default: 512x512)
- `ALLOWED_EXTENSIONS`: Permitted file extensions
- `JPEG_QUALITY`: JPEG compression quality (default: 85)

## Database Schema

The avatar feature adds the following column to the `user` table:

```sql
ALTER TABLE user ADD COLUMN avatar_filename VARCHAR(255);
```

This column stores the filename of the user's uploaded avatar image.

## File Structure

```
/data/avatars/
├── avatar_12345678_abcd1234.jpg
├── avatar_87654321_efgh5678.png
└── ...
```

Filenames are generated using:
- Hash of user email (8 characters)
- Random UUID (8 characters)
- Original file extension

## Security Considerations

1. **File Validation**: All uploaded files are validated for:
   - File type (MIME type detection)
   - File size limits
   - Image content verification

2. **Filename Security**: Generated filenames prevent:
   - Path traversal attacks
   - Filename collisions
   - Information disclosure

3. **Storage Security**: Avatar storage directory:
   - Isolated from other application files
   - Proper file permissions
   - Regular cleanup of orphaned files

## Usage Examples

### Admin Interface

1. Navigate to Users → [Select User] → Settings
2. Click "Manage Avatar" button
3. Upload image file or delete existing avatar

### API Usage

```bash
# Upload avatar
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "avatar=@/path/to/image.jpg" \
  http://your-mailu-server/admin/api/v1/user/john.doe@example.com/avatar

# Get avatar
curl -X GET \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://your-mailu-server/admin/api/v1/user/john.doe@example.com/avatar

# Delete avatar
curl -X DELETE \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://your-mailu-server/admin/api/v1/user/john.doe@example.com/avatar
```

## Testing

The avatar feature includes comprehensive test coverage:

- Unit tests for utility functions
- Integration tests for API endpoints
- Security tests for file validation
- Performance tests for image processing

Run tests with:
```bash
pytest tests/test_avatar.py
pytest tests/test_avatar_integration.py
```

## Migration

To enable the avatar feature on an existing Mailu installation:

1. Apply database migration:
   ```bash
   flask db upgrade
   ```

2. Create avatar storage directory:
   ```bash
   mkdir -p /data/avatars
   chown 1000:1000 /data/avatars
   chmod 755 /data/avatars
   ```

3. Restart admin container to load new functionality

## Troubleshooting

### Common Issues

1. **Upload Fails with "File too large"**
   - Check that file is under 2MB
   - Verify `MAX_AVATAR_SIZE` configuration

2. **Avatar Not Displaying**
   - Check that avatar storage directory exists and is writable
   - Verify file permissions on uploaded images
   - Check browser console for 404 errors

3. **Database Migration Issues**
   - Ensure proper backup before running migration
   - Check database permissions for schema changes

### Logs

Avatar operations are logged to the admin container logs:
```bash
docker logs mailu_admin_1 | grep -i avatar
```

## External System Integration

This section explains how external email clients, contact managers, and other systems can discover and access user avatars and vCard contact information from Mailu.

Public API Endpoints
~~~~~~~~~~~~~~~~~~~~

**Direct API Access (No Authentication Required)**

.. code-block:: bash

   # Get user avatar (PNG/JPEG image)
   GET https://mail.example.com/api/v1/user/{email}/avatar

   # Get user vCard with embedded avatar
   GET https://mail.example.com/api/v1/user/{email}/vcard

**Examples:**

.. code-block:: bash

   curl https://mail.example.com/api/v1/user/john@example.com/avatar
   curl https://mail.example.com/api/v1/user/john@example.com/vcard

Service Discovery (RFC 5785)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

External systems can use standardized well-known URIs to discover avatar and vCard services:

.. code-block:: bash

   # Discover avatar service (redirects to API endpoint)
   GET https://mail.example.com/.well-known/avatar/{email}

   # Discover vCard service (redirects to API endpoint)  
   GET https://mail.example.com/.well-known/vcard/{email}

   # Discover all user services
   GET https://mail.example.com/.well-known/user-services

**Service Discovery Response:**

The ``/.well-known/user-services`` endpoint returns service information:

.. code-block:: json

   {
     "avatar": {
       "description": "User avatar service",
       "url_template": "https://mail.example.com/.well-known/avatar/{email}",
       "direct_url_template": "https://mail.example.com/api/v1/user/{email}/avatar",
       "format": "image/png or image/jpeg",
       "authentication": "none"
     },
     "vcard": {
       "description": "User vCard service with avatar",
       "url_template": "https://mail.example.com/.well-known/vcard/{email}",
       "direct_url_template": "https://mail.example.com/api/v1/user/{email}/vcard",
       "format": "text/vcard",
       "authentication": "none"
     }
   }

Email Client Integration
~~~~~~~~~~~~~~~~~~~~~~~~

**Gmail, Outlook, Thunderbird**

Email clients can integrate using these methods:

1. **Service Discovery:**

   .. code-block:: text

      GET /.well-known/user-services
      Parse JSON response to get URL templates

2. **Direct Avatar Access:**

   .. code-block:: text

      GET /api/v1/user/{sender_email}/avatar
      Display as contact photo in email interface

3. **Contact Import:**

   .. code-block:: text

      GET /api/v1/user/{email}/vcard
      Import contact with embedded avatar photo

**Implementation Examples**

JavaScript/Web Client:

.. code-block:: javascript

   // Discover services
   const response = await fetch('https://mail.example.com/.well-known/user-services');
   const services = await response.json();

   // Get avatar URL template
   const avatarTemplate = services.avatar.direct_url_template;
   const avatarUrl = avatarTemplate.replace('{email}', 'user@example.com');

   // Fetch avatar
   const avatarImg = document.createElement('img');
   avatarImg.src = avatarUrl;

Python Client:

.. code-block:: python

   import requests

   # Get vCard with avatar
   response = requests.get('https://mail.example.com/api/v1/user/john@example.com/vcard')
   vcard_data = response.text

   # Save as contact file
   with open('contact.vcf', 'w') as f:
       f.write(vcard_data)

Security & Privacy
~~~~~~~~~~~~~~~~~~

* **Public Read Access:** Avatar and vCard endpoints are publicly accessible
* **No Authentication Required:** External systems can fetch without API keys
* **Privacy Protection:** Only returns data for existing users (404 for non-existent)
* **Rate Limiting:** Consider implementing rate limiting for public endpoints

Mobile App Integration
~~~~~~~~~~~~~~~~~~~~~~

Mobile email apps can:

1. Query ``/.well-known/user-services`` on domain setup
2. Cache service URLs for the domain
3. Fetch avatars dynamically when displaying emails
4. Import contacts with avatars using vCard endpoints

## Performance Considerations

* Image processing is performed during upload to minimize runtime overhead
* Generated initials avatars are created dynamically but can be cached
* Consider implementing CDN or reverse proxy caching for high-traffic installations
* Service discovery responses can be cached by external clients

## Future Enhancements

Potential future improvements:

* LDAP/Active Directory avatar synchronization
* Bulk avatar import functionality
* Avatar history and versioning
* Integration with webmail interfaces (Roundcube, SnappyMail)
* DNS-based service discovery with TXT records

This implementation provides a solid foundation for these future enhancements while delivering immediate value to users and external integrations.
