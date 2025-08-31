# mentor_connect_ngo_enhanced/promote_user.py
import os
from datetime import datetime
from app import create_app, db
from app.models import User
from dotenv import load_dotenv

load_dotenv()

# IMPORTANT: Set the email of the user you wish to promote to admin
# This user must already be registered in the application.
USER_EMAIL_TO_PROMOTE = os.getenv('ADMIN_EMAIL', 'admin@example.com') # Use .env or default

def promote_user_to_admin():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=USER_EMAIL_TO_PROMOTE).first()
        if user:
            user.role = 'admin'
            # Also initialize new fields for admin user
            user.last_login = datetime.utcnow()
            user.last_activity = datetime.utcnow()
            db.session.commit()
            print(f"User '{user.username}' ({user.email}) has been promoted to 'admin' role.")
        else:
            print(f"User with email '{USER_EMAIL_TO_PROMOTE}' not found.")

if __name__ == '__main__':
    promote_user_to_admin()

