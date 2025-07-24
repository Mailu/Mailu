"""
vCard utilities for Mailu
Generates vCard data with avatar support for email clients
"""

import base64
import os
from flask import current_app

# Avatar configuration - inline to avoid import issues
INCLUDE_AVATAR_IN_VCARD = True  # Include avatar in vCard exports

def generate_user_vcard(user):
    """Generate vCard data for a user including avatar if available"""
    
    vcard_lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{user.displayed_name or user.localpart}",
        f"EMAIL:{user.email}",
        f"UID:{user.email}",
    ]
    
    # Add avatar if enabled
    if INCLUDE_AVATAR_IN_VCARD:
        avatar_data = None
        mime_type = 'image/jpeg'
        
        # Try to get uploaded avatar first
        if (user.avatar_filename and 
            user.avatar_path and 
            os.path.exists(user.avatar_path)):
            
            try:
                with open(user.avatar_path, 'rb') as f:
                    avatar_data = f.read()
                    
                # Determine MIME type from file extension
                ext = user.avatar_filename.lower().split('.')[-1]
                mime_types = {
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg', 
                    'png': 'image/png',
                    'gif': 'image/gif'
                }
                mime_type = mime_types.get(ext, 'image/jpeg')
            except (IOError, OSError):
                avatar_data = None
        
        # If no uploaded avatar, generate initials avatar
        if avatar_data is None:
            try:
                from . import avatar
                initials = user.get_avatar_initials()
                avatar_img = avatar.generate_initials_avatar(initials)
                
                # Convert PIL image to bytes
                import io
                img_buffer = io.BytesIO()
                avatar_img.save(img_buffer, format='PNG')
                avatar_data = img_buffer.getvalue()
                mime_type = 'image/png'
            except Exception:
                avatar_data = None
        
        # Add avatar to vCard if we have one
        if avatar_data:
            avatar_b64 = base64.b64encode(avatar_data).decode('ascii')
            
            # Add photo field (folded lines for long data)
            vcard_lines.append(f"PHOTO;ENCODING=b;TYPE={mime_type.upper()}:")
            
            # Split base64 data into 75-character lines per vCard spec
            for i in range(0, len(avatar_b64), 75):
                line = avatar_b64[i:i+75]
                if i == 0:
                    vcard_lines[-1] += line
                else:
                    vcard_lines.append(" " + line)  # Continuation line
    
    vcard_lines.append("END:VCARD")
    return "\r\n".join(vcard_lines)


def get_user_vcard_headers():
    """Get HTTP headers for vCard response"""
    return {
        'Content-Type': 'text/vcard; charset=utf-8',
        'Content-Disposition': 'attachment; filename="contact.vcf"'
    }
