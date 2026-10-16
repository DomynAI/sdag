# Installation

sdag is not available on pypi yet (it's coming soon!).

=== "`uv`"

    To install sdag from [GitHub](https://github.com/igeniusai/sdag):

    ```sh
    uv add "sdag @ git+https://github.com/igeniusai/sdag"
    ```

    It is also possible to install it as a tool to gain global access to it:

    ```sh
    uv tool install "sdag @ git+https://github.com/igeniusai/sdag"
    ```
=== "`pip`"

    To install sdag with pip, first clone the GitHub repository:

    ```sh
    git clone https://github.com/igeniusai/sdag.git
    ```

    and then install sdag:

    ```sh
    pip install path/to/sdag
    ```

If you face issues in the process, you likely have to install [Rust](https://rust-lang.org/tools/install/) or update it to a more recent version via:

```sh
rustup update
```
