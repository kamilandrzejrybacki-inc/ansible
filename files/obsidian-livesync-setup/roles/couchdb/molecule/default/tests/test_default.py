"""Testinfra tests for couchdb role."""


def test_couchdb_data_directory_exists(host):
    """Verify the CouchDB data directory was created."""
    assert host.file("/opt/obsidian-couchdb").is_directory


def test_couchdb_compose_file_exists(host):
    """Verify the Docker Compose file was templated."""
    compose = host.file("/opt/obsidian-couchdb/docker-compose.yml")
    assert compose.exists
    assert compose.mode == 0o600


def test_couchdb_local_ini_exists(host):
    """Verify the CouchDB local.ini was templated."""
    ini = host.file("/opt/obsidian-couchdb/local.ini")
    assert ini.exists
    assert ini.mode == 0o600


def test_couchdb_local_ini_contains_cors(host):
    """Verify CORS is configured for Obsidian origins."""
    ini = host.file("/opt/obsidian-couchdb/local.ini")
    assert ini.contains("app://obsidian.md")
    assert ini.contains("capacitor://localhost")


def test_couchdb_local_ini_requires_auth(host):
    """Verify CouchDB requires valid user authentication."""
    ini = host.file("/opt/obsidian-couchdb/local.ini")
    assert ini.contains("require_valid_user = true")


def test_couchdb_container_running(host):
    """Verify the CouchDB container is running."""
    result = host.run("docker ps --filter name=obsidian-couchdb --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_couchdb_port_listening(host):
    """Verify CouchDB is listening on port 5984."""
    socket = host.socket("tcp://0.0.0.0:5984")
    assert socket.is_listening


def test_couchdb_database_exists(host):
    """Verify the obsidian-livesync database was created."""
    result = host.run(
        "curl -s -u admin:testadminpassword http://localhost:5984/obsidian-livesync"
    )
    assert '"db_name":"obsidian-livesync"' in result.stdout


def test_couchdb_sync_user_exists(host):
    """Verify the sync user was created."""
    result = host.run(
        "curl -s -u admin:testadminpassword "
        "http://localhost:5984/_users/org.couchdb.user:obsidian-sync"
    )
    assert '"name":"obsidian-sync"' in result.stdout
