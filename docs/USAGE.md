# IX-Sally Usage

## Install for local evaluation

From the repository root:

```text
python -m pip install -e ".[dev]"
```

The runtime itself has no declared third-party dependencies. The `dev` extra
installs the configured test, lint, formatting, and type-checking tools.

## Run the complete quality gate

```text
python check_green.py
```

Individual gates are available with `--gate`:

```text
python check_green.py --gate format
python check_green.py --gate lint
python check_green.py --gate type-check
python check_green.py --gate repository
python check_green.py --gate dependencies
python check_green.py --gate architecture
python check_green.py --gate test
python check_green.py --gate package
```

## Run the observed cognitive evaluation

```text
python -m ix_sally --cognitive-evaluation
```

The command prints canonical JSON. A successful local run returns process exit
code zero only when every observed benchmark passes. The report still states
`agi_certified: false`.

## Execute an IX source file

```text
python -m ix_sally --execute-ix examples/answer.ix
```

The output is a JSON execution receipt containing status, typed outputs, memory,
trace information, and failure details when applicable.

## Print a clean complete snapshot

```text
python -m ix_sally --empty-cognitive-snapshot
```

## Python integration

```python
from ix_sally.cognition import SallyCognitiveSystem

system = SallyCognitiveSystem.create()
result = system.execute_ix(
    "let answer = 6 * 7\nprint answer\nassert answer == 42\n",
    filename="example.ix",
)

print(result.status.value)
print(result.to_payload())
```

## Persist and recover state

```python
from pathlib import Path

from ix_sally.cognition import SallyCognitiveSystem, SnapshotRepository

system = SallyCognitiveSystem.create()
system.execute_ix("remember answer = 42\n", filename="memory.ix")

repository = SnapshotRepository(Path("ix-sally-state.json"))
repository.save(system.snapshot())
loaded = repository.load()
restored = SallyCognitiveSystem.from_snapshot(loaded.snapshot)

assert restored.state_payload() == system.state_payload()
```

## Run the integrated example

```text
python examples/run_cognitive_demo.py
```

When running directly from an uninstalled checkout, either install the package
in editable mode or set `PYTHONPATH=src` for that process.
