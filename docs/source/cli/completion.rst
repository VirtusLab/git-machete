.. _completion:

completion
==========
**Usage:**

.. code-block:: shell

    git machete completion <shell>

where ``<shell>`` is one of: ``bash``, ``fish``, ``zsh``.

Prints out completion scripts.

**Supported shells:**

**bash**

Put the following into ``~/.bashrc`` or ``~/.bash_profile``:

.. code-block:: shell

    eval "$(git machete completion bash)"  # or, if it doesn't work:
    source <(git machete completion bash)

**fish**

Put the following into ``~/.config/fish/config.fish``:

.. code-block:: shell

    git machete completion fish | source

**zsh**

Put the following into ``~/.zshrc``:

.. code-block:: shell

    eval "$(git machete completion zsh)"  # or, if it doesn't work:
    source <(git machete completion zsh)
