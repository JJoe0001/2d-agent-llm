# Installation

## Recommended environment

Use Python 3.10 or newer. Python 3.11 is recommended for matching the original MCP execution environment.

```bash
cd cpc_submission_package_20260604/code/exfo_agent
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Alternatively, with `uv`:

```bash
cd cpc_submission_package_20260604/code/exfo_agent
uv sync
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

A portable MCP launch configuration is provided in:

```text
mcp_config/mcp_server_relative.json
```

If your MCP client requires absolute paths, replace `${PACKAGE_ROOT}` with the absolute path to this archive.

## Quick syntax check

From the package root:

```bash
python -m py_compile $(find code/exfo_agent -name "*.py")
```

The syntax-check output generated during packaging is stored in:

```text
checks/python_syntax_check.txt
```
