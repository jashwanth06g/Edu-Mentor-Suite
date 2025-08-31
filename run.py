# mentor_connect_ngo_enhanced/run.py
import os
from app import create_app

# Determines if the app should run in debug mode based on the FLASK_DEBUG environment variable.
# It's crucial to set FLASK_DEBUG=0 (or remove it) in production for security and performance.
# For a hackathon, '1' is fine for development, but remember to switch it for deployment.
debug_mode = os.environ.get('FLASK_DEBUG') == '1'

# Creates the Flask application instance using the factory function `create_app()`.
app = create_app()

# This block ensures that the Flask development server runs only when the script is executed directly.
if __name__ == '__main__':
    # Runs the Flask development server.
    # 'debug=debug_mode' dynamically enables/disables debugging features.
    app.run(debug=debug_mode)
