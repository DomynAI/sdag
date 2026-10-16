# Visualization

As shown in the previous sections, you can use `sdag view <pipeline-name>` to visualize graphs in the terminal. However, when graphs become large this visualization quickly becomes messy and hard to understand. For this reason, sdag provides another quick visualization method. To leverage it, you must install the [neo4j-viz](https://pypi.org/project/neo4j-viz/) library.

To visualize the `dependent_tasks` pipeline of the [Handling multiple tasks](multiple_tasks.md) section, copy the following snippet into a [Jupyter notebook](https://jupyter.org/) cell:

```py
from sdag import DAGViewer


viewer = DAGViewer()
viewer.view("dependent_tasks")
```

You should see the graph of the pipeline printed in the cell. You can change the attributes of `DAGViewer` to modify colors and sizes of the graph nodes.