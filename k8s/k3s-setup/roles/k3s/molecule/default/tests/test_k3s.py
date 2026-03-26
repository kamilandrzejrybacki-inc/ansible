def test_k3s_service_running(host):
    svc = host.service("k3s")
    assert svc.is_enabled
    assert svc.is_running

def test_kubectl_available(host):
    result = host.run("kubectl version --client")
    assert result.rc == 0

def test_node_ready(host):
    result = host.run("kubectl get nodes --no-headers")
    assert result.rc == 0
    assert "Ready" in result.stdout

def test_k3s_config_exists(host):
    assert host.file("/etc/rancher/k3s/k3s.yaml").exists
