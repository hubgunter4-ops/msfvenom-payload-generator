# Revisión visual de evidencias

La captura `installation-preflight.png` muestra con legibilidad suficiente la versión de Python, la ausencia honesta de Docker en el entorno de captura y la ayuda del complemento. No presenta recortes visibles y el estado final deja claro que la comprobación no ejecuta contenedores ni payloads.

La captura `execution-dry-run.png` muestra la ruta del marcador inofensivo, su SHA-256, el nombre del contenedor previsto, la imagen, la red `none` y el estado de ejecución deshabilitada. El bloque de propiedades de seguridad permite identificar visualmente `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges` y `--pids-limit`. La captura es una evidencia de planificación reproducible, no una ejecución real de Docker.
