"""Testinfra tests for k8s-prereqs role."""


def test_containerd_installed(host):
    """Verify containerd.io is installed."""
    pkg = host.package("containerd.io")
    assert pkg.is_installed


def test_containerd_running(host):
    """Verify containerd service is running."""
    svc = host.service("containerd")
    assert svc.is_running
    assert svc.is_enabled


def test_kubeadm_installed(host):
    """Verify kubeadm is installed."""
    cmd = host.run("kubeadm version")
    assert cmd.rc == 0


def test_kubelet_installed(host):
    """Verify kubelet is installed."""
    pkg = host.package("kubelet")
    assert pkg.is_installed


def test_kubectl_installed(host):
    """Verify kubectl is installed."""
    cmd = host.run("kubectl version --client")
    assert cmd.rc == 0


def test_swap_disabled(host):
    """Verify swap is disabled."""
    cmd = host.run("swapon --show")
    assert cmd.stdout.strip() == ""


def test_ip_forward_enabled(host):
    """Verify IPv4 forwarding is enabled."""
    sysctl = host.sysctl("net.ipv4.ip_forward")
    assert sysctl == 1


def test_bridge_nf_call_iptables(host):
    """Verify bridge-nf-call-iptables is enabled."""
    sysctl = host.sysctl("net.bridge.bridge-nf-call-iptables")
    assert sysctl == 1
