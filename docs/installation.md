# Installation

=== "`pip`"

    ```sh
    pip install sdag
    ```
=== "`uv`"

    ```sh
    uv add sdag
    ```

To install sdag from source:

=== "`pip`"

    First clone the GitHub repository:

    ```sh
    git clone https://github.com/DomynAI/sdag.git
    ```

    and then install sdag:

    ```sh
    pip install path/to/sdag
    ```

=== "`uv`"

    ```sh
    uv add "sdag @ git+https://github.com/DomynAI/sdag"
    ```

    It is also possible to install it as a tool to gain global access to it:

    ```sh
    uv tool install "sdag @ git+https://github.com/DomynAI/sdag"
    ```

If you face issues in the process, you likely have to install [Rust](https://rust-lang.org/tools/install/) or update it to a more recent version via:

```sh
rustup update
```
