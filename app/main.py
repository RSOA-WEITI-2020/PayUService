import os
from app import create_app

app_dir = os.path.dirname(os.path.realpath(__file__))
db_uri = 'mysql+pymysql://root:password@userdb/user_db'
app = create_app(db_uri, app_dir + '/../keys')


def run_development():
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    run_development()
