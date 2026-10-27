.. _kubernetes:

Kubernetes setup
================

Please see `the Helm Chart documentation`_.

We are looking for maintainers.

When deploying the Postfix container with persistent queue storage, mount
``/queue/pid`` as per-pod ephemeral storage (for example, a memory-backed
``emptyDir``). Postfix keeps its default PID and lock files under this directory;
the queue itself remains on the persistent volume.

.. _`the Helm Chart documentation`: https://github.com/Mailu/helm-charts/blob/master/charts/mailu/README.md
