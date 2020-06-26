from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS


def create_app(db_uri, keys_dir_path):
    app = Flask(__name__)

    public_key = ''

    with open(keys_dir_path + '/jwtRS256.key.pub', 'r') as content_file:
        public_key = content_file.read()

    app.config['JWT_ALGORITHM'] = 'RS256'
    app.config['JWT_PUBLIC_KEY'] = public_key
    app.config['JWT_IDENTITY_CLAIM'] = 'sub'
    app.config['JWT_USER_CLAIMS'] = 'payload'
    app.config['JWT_CLAIMS_IN_REFRESH_TOKEN'] = False
    app.config['JWT_ERROR_MESSAGE_KEY'] = 'message'
    app.config['JWT_TOKEN_LOCATION'] = ('headers', 'cookies')

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['PROPAGATE_EXCEPTIONS'] = True

    from extensions import (
        api,
        jwt,
        db,
    )

    jwt.init_app(app)
    db.init_app(app)

    import models
    with app.app_context():
        db.create_all()

    import resources
    resources.BaseResource.register(api)
    api.init_app(app)

    CORS(app)

    return app
