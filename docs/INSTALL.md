# 安装与环境配置

为接近原始 MCP 运行环境，建议 Python 3.11。依赖按版本范围声明，未锁定生产环境；复算时记录实际安装版本。

```bash
git clone https://github.com/JJoe0001/2d-agent-llm.git
cd 2d-agent-llm
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./code/exfo_agent
```

也可使用 `uv`：

```bash
cd 2d-agent-llm
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ./code/exfo_agent
```

依赖元数据见 `code/exfo_agent/pyproject.toml`，主要为 `mcp`、`fastmcp`、`pymatgen`、`numpy`、`pandas`、`scipy`、`networkx`、`torch`、`chgnet`、`ase`、`matplotlib`、`seaborn`、`tqdm`、`joblib`、`pebble`。

## MCP 配置

本地进程模板：`mcp_config/mcp_server_relative.json`。把 `${PACKAGE_ROOT}` 换为仓库绝对路径；模板使用 **stdio**。其中 `python` 应指向装有依赖的解释器，客户端不自动激活环境时须填绝对路径。

单独启动 HTTP 服务时，在仓库根目录运行：

```bash
.venv/bin/python code/exfo_agent/server.py --transport http --port 8000
```

HTTP 客户端连接相应端点；`command`／`args` 型 stdio 配置不能连接 HTTP 进程。

## 完整性和语法检查

```bash
python scripts/verify_package.py
python -m compileall -q code/exfo_agent
```

原始打包时的语法检查记录见 `checks/python_syntax_check.txt`。
