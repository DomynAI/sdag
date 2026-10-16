"""Utils to handle submission scripts."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class _ScriptSig:
    """Class to signal the default script must be generated."""


script = _ScriptSig()
"""Basic script.

This gets turned into:

```python
from sdag import Script

Script("#!/bin/bash\\nsdag-execute")
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


def get_basic_script() -> ScriptContent:
    """Generate a basic script.

    Returns:
        ScriptContent: Script only containing shebang
            and sdag-execute.
    """
    return ScriptContent(content="#!/bin/bash\nsdag-execute")


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
