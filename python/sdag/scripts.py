"""Utils to handle submission scripts."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ScriptSignal:
    """Class to signal the default script must be generated."""


script = ScriptSignal()
"""Basic script.

It's rendered as:

```python
from sdag import Script

Script("#!/bin/bash\\n${SDAG_LAUNCHER} sdag-execute")
```

It can be directly used in task decorators:

```python
import script, task

@task(script)
def say_hello():
    ...
```

You can make it run on Slurm by configuring the Slurm variables
globally or for specific nodes.
"""


class ScriptPath(BaseModel):
    """Script path.

    Attributes:
        kind (Literal['script_path']): Script path.
        path (Path): Path.
    """

    kind: Literal["script_path"] = "script_path"
    path: Path


class ScriptContent(BaseModel):
    """Script embedded in the pipeline definition.

    Attributes:
        kind (Literal['script']): Script kind.
        content (str): Script content.
    """

    kind: Literal["script"] = "script"
    content: str


ScriptUnion = Annotated[
    ScriptContent | ScriptPath, Field(discriminator="kind")
]
"""Script content or path."""


class Script:
    """Script content.

    It can be used to embed the script content
    in the pipeline definition.

    Attributes:
        content (str): Script content.
    """

    def __init__(self, content: str):
        """Initialize the Script.

        Args:
            content (str): Script content.
        """
        self.content = content


def resolve_script(
    script: str | Path | Script | ScriptSignal,
) -> ScriptUnion:
    """Resolve the script of a task.

    Args:
        script (str | Path | Script | ScriptSignal):
            User-selected script.

    Returns:
        ScriptUnion: Script union.
    """
    if isinstance(script, ScriptSignal):
        script_obj = ScriptContent(
            content="#!/bin/bash\n${SDAG_LAUNCHER} sdag-execute"
        )
    elif isinstance(script, Script):
        script_obj = ScriptContent(content=script.content)
    else:
        script_obj = ScriptPath(path=Path(script))
    return script_obj
