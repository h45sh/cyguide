import pytest

from cyguide.engine.executor import Executor, sanitize_subprocess_env
from cyguide.schemas.network import NetworkHost
from tests.fixtures.mock_tools import MockNmapAdapter


@pytest.mark.asyncio
async def test_executor_run_tool():
    executor = Executor()
    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockNmapAdapter()

    findings = []
    async for f in executor.run_tool(adapter, target, {}):
        findings.append(f)

    assert len(findings) == 1
    assert findings[0].schema_type == "network.service"
    assert findings[0].pik["host_ip"] == "127.0.0.1"


class MockHangingAdapter(MockNmapAdapter):
    def build_command(self, target, params):
        return ["sleep", "5"]

    async def parse_output(self, raw_stdout, target, context=None):
        if False:
            yield


@pytest.mark.asyncio
async def test_executor_timeout():
    executor = Executor()
    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockHangingAdapter()

    output_lines = []

    async def record_output(text):
        output_lines.append(text)

    with pytest.raises(TimeoutError):
        async for _ in executor.run_tool(
            adapter, target, {}, timeout_seconds=0.2, on_output=record_output
        ):
            pass

    assert any("TIMEOUT" in line for line in output_lines)


def test_sanitize_subprocess_env():
    raw_env = {
        "PATH": "/usr/bin:/bin",
        "USER": "analyst",
        "CYGUIDE_API_KEY": "secret_key_123",
        "CYGUIDE_API_BASE": "https://api.openai.com",
        "GROQ_API_KEY": "gsk_test123",
        "OPENAI_API_KEY": "sk-test456",
        "ANTHROPIC_API_KEY": "ant-test789",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "GITHUB_TOKEN": "ghp_token",
    }
    cleaned = sanitize_subprocess_env(raw_env)
    assert cleaned["PATH"] == "/usr/bin:/bin"
    assert cleaned["USER"] == "analyst"
    assert "CYGUIDE_API_KEY" not in cleaned
    assert "CYGUIDE_API_BASE" not in cleaned
    assert "GROQ_API_KEY" not in cleaned
    assert "OPENAI_API_KEY" not in cleaned
    assert "ANTHROPIC_API_KEY" not in cleaned
    assert "AWS_SECRET_ACCESS_KEY" not in cleaned
    assert "GITHUB_TOKEN" not in cleaned


def test_sanitize_subprocess_env_extended():
    raw_env = {
        "PATH": "/usr/bin:/bin",
        "DEEPSEEK_API_KEY": "sk-deepseek",
        "PERPLEXITY_API_KEY": "pplx-secret",
        "PPLX_TOKEN": "token123",
        "HUGGINGFACE_TOKEN": "hf_abc",
        "HF_TOKEN": "hf_xyz",
        "VAULT_TOKEN": "s.vaulttoken",
        "SSH_PRIVATE_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----",  # codeguard: ignore[SECRET_PRIVATE_KEY]
    }
    cleaned = sanitize_subprocess_env(raw_env)
    assert cleaned["PATH"] == "/usr/bin:/bin"
    assert "DEEPSEEK_API_KEY" not in cleaned
    assert "PERPLEXITY_API_KEY" not in cleaned
    assert "PPLX_TOKEN" not in cleaned
    assert "HUGGINGFACE_TOKEN" not in cleaned
    assert "HF_TOKEN" not in cleaned
    assert "VAULT_TOKEN" not in cleaned
    assert "SSH_PRIVATE_KEY" not in cleaned
