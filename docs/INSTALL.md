# Installation

## Recommended environment

Use Python 3.11 for the closest match to the original MCP execution environment. Dependencies are currently specified as version ranges rather than a locked production environment, so record the installed versions in any reproduction report.

```bash
git clone https://github.com/JJoe0001/2d-agent-llm.git
cd 2d-agent-llm
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./code/exfo_agent
```

Alternatively, with `uv`:

```bash
cd 2d-agent-llm
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ./code/exfo_agent
```

## Main dependencies

The package metadata is in:

```text
code/exfo_agent/pyproject.toml
```

Major dependencies are:

- `mcp`, `fastmcp`
- `pymatgen`
- `numpy`, `pandas`, `scipy`
- `networkx`
- `torch`, `chgnet`, `ase`
- `matplotlib`, `seaborn`
- `tqdm`, `joblib`, `pebble`

## MCP configuration

A local-process MCP configuration template is provided in:

```text
mcp_config/mcp_server_relative.json
```

Replace `${PACKAGE_ROOT}` with the absolute path to the cloned repository. The template launches the server using **stdio**. The command must use the Python interpreter from the environment where the dependencies were installed; replace `"python"` with its absolute path if your client does not activate that environment.

For a separately managed HTTP server, start it explicitly from the repository root:

```bash
.venv/bin/python code/exfo_agent/server.py --transport http --port 8000
```

Connect an HTTP-capable MCP client to that server's HTTP endpoint. A `command`/`args` stdio configuration cannot communicate with the HTTP process.

## Package integrity and syntax checks

From the package root:

```bash
python scripts/verify_package.py
python -m compileall -q code/exfo_agent
```

The original packaging-time syntax-check record is stored in:

```text
checks/python_syntax_check.txt
```
