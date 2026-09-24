import os
from dotenv import load_dotenv
from app import create_app

# Load .env before selecting the configuration, so FLASK_ENV=development is
# an explicit local opt-in and the default run remains production-safe.
load_dotenv()
config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
