# Polis 2

## Prerequisites
1. install ollama somehwere

Then:
```bash
# download the model:
ollama pull huggingface.co/bartowski/Qwen2.5-14B-Instruct-1M-GGUF
# start ollama server:
OLLAMA_MODELS=/usr/share/ollama/.ollama/models OLLAMA_HOST=0.0.0.0:5000 ollama serve
```

In another terminal:
```bash
# install with poetry
poetry install
# run agent orchestrator
poetry run python agent_orchestrator.py

# it's now running, gl
```

## Tool Sets
* Code Isolation
* File Manager
* Forum
* Notes (in progress)
* Persona (in progress)
* Quest Manager
* Rag
* Wikisearch