import kopf
import pykube
import os
import psycopg2
import secrets

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import AsIs

def connect_to_db():
    pg_connection = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS"),
    )
    pg_connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return pg_connection.cursor()


@kopf.on.create("ocf.io", "v1", "postgrespairs")
def create_fn(name: str, **kwargs):
    """Create a new postgres user and associated table, store the credentials in a Secret.
       This is highly opinionated and you should probably not use this unless you accept
       all the assumptions I make here.

    Args:
        name (str): The Kubernetes object name.
    """
    cur = connect_to_db()

    # TODO: Make sure this didn't throw an error.
    username = psycopg2.extensions.AsIs(name)
    password = secrets.token_urlsafe(16)
    cur.execute("CREATE USER %s WITH PASSWORD %s", (username, password))
    cur.execute("CREATE DATABASE %s", [username])
    cur.execute("ALTER DATABASE %s OWNER TO %s", (username, username))

    secret_obj = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name},
        "stringData": {
            "username": name,
            "password": password,
        },
    }

    kopf.adopt(secret_obj)

    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    secret = pykube.Secret(api, secret_obj)
    secret.create()
    api.session.close()


@kopf.on.delete("ocf.io", "v1", "postgrespairs")
def delete_fn(name: str, **kwargs):
    """Delete the postgress user and archive its database. Dropping the table would
       probably be unsafe.

    Args:
        name (str): The Kubernetes object name.
    """
    cur = connect_to_db()

    pad = secrets.token_hex(2)
    cur.execute("ALTER DATABASE %s OWNER TO %s", (AsIs(name), AsIs("postgres")))
    cur.execute("ALTER DATABASE %s RENAME TO %s", (AsIs(name), AsIs(name + pad)))
    cur.execute("DROP USER %s", [AsIs(name)])
