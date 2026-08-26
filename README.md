# MSFVenom Payload Generator v4.0

Herramienta de línea de comandos para **laboratorios de Red Team, ejercicios Purple Team y pruebas de penetración autorizadas**. El proyecto proporciona una interfaz interactiva alrededor de `msfvenom` para generar artefactos de prueba, crear archivos de recursos para `msfconsole`, levantar opcionalmente un handler y observar nuevas sesiones a través del log local de Metasploit.

> **Aviso de uso autorizado:** este repositorio no debe utilizarse contra sistemas, redes, cuentas o dispositivos para los que no exista autorización explícita, vigente y documentada. El operador es responsable de definir el alcance, las reglas de enfrentamiento, las ventanas de prueba, los objetivos permitidos, la gestión de evidencias y la limpieza posterior.

## Descripción

`MSFVenomPayloadGeneratorv4.0.py` centraliza varias tareas repetitivas de un flujo de validación ofensiva: consulta de payloads y formatos disponibles, construcción de comandos `msfvenom`, generación de archivos `.rc` para `exploit/multi/handler`, lanzamiento opcional de `msfconsole`, monitorización de sesiones y entrega controlada de archivos mediante varios mecanismos de transferencia.

La herramienta **no implementa un exploit**, no contiene payloads generados y no sustituye la validación manual del alcance. Su función es orquestar utilidades que ya deben estar instaladas en el entorno de evaluación.

`msfvenom` es el componente de Metasploit que combina la generación de payloads y el encoding, y ofrece opciones para seleccionar payload, formato, encoder, arquitectura, plataforma, tamaño, bad characters, template y ruta de salida [1]. En un ejercicio Purple Team, estas capacidades deben acompañarse de telemetría, controles de prevención y criterios de detección; no deben interpretarse como mecanismos fiables de evasión.

## Capacidades principales

| Área | Comportamiento implementado | Resultado esperado |
|---|---|---|
| Inventario | Lista payloads, encoders, NOPs, formatos y plataformas disponibles en la instalación local | Salida de `msfvenom` en consola |
| Generación | Construye y ejecuta un comando `msfvenom` con `LHOST`, `LPORT`, formato y opciones avanzadas | Artefacto dentro de `payloads/` |
| Handler | Genera un resource file para `exploit/multi/handler` | Archivo `.rc` dentro de `rc_files/` |
| Listener | Lanza `msfconsole` en primer plano o segundo plano | Proceso local y, opcionalmente, monitor de sesiones |
| Monitorización | Lee incrementalmente `~/.msf4/logs/framework.log` y detecta aperturas de sesiones Meterpreter o command shell | Notificación en consola con ID, tipo, IP y timestamp |
| Distribución | Ofrece HTTP, SCP, SMB, FTP, Netcat y ADB | Comando o transferencia ejecutada según el método elegido |

## Requisitos

El programa requiere **Python 3.8 o superior** y una instalación funcional de Metasploit Framework que proporcione `msfvenom` y, si se utilizará el listener, `msfconsole`. No usa paquetes Python externos; las importaciones pertenecen a la biblioteca estándar.

Las utilidades de transferencia son opcionales y dependen del flujo seleccionado. La siguiente tabla resume el requisito operativo:

| Función | Binario o recurso requerido | Observación |
|---|---|---|
| Listados y generación | `msfvenom` | Debe estar en `PATH` y ser ejecutable por el usuario |
| Handler y sesiones | `msfconsole` | Requiere que Metasploit pueda escribir su log local |
| SCP | `scp` | Cliente OpenSSH |
| SMB | `smbclient` | El código actual recibe usuario, contraseña, host y share |
| FTP | `ftp` | Cliente FTP disponible en el sistema |
| Netcat | `nc` | Se invoca mediante un comando del sistema |
| Android | `adb` | Requiere depuración USB o transporte ADB previamente autorizado |

En distribuciones basadas en Debian/Kali, la instalación de Metasploit y de las utilidades auxiliares debe realizarse siguiendo la documentación y los canales de confianza de cada distribución. Este README no instala paquetes del sistema ni modifica la configuración de red.

## Instalación

Clone o copie el repositorio en una máquina de laboratorio aislada y verifique primero que las dependencias se resuelven desde el `PATH`:

```bash
python3 --version
command -v msfvenom
command -v msfconsole
```

A continuación, ejecute la herramienta desde la raíz del repositorio:

```bash
python3 MSFVenomPayloadGeneratorv4.0.py
```

El script crea automáticamente los directorios `payloads/` y `rc_files/` cuando se inicia. Los artefactos generados son locales y no deben incorporarse al control de versiones.

## Flujo de uso

Al iniciar aparece un menú con dos grupos. El grupo de información delega en `msfvenom` para mostrar inventarios y opciones. El grupo de generación permite una selección rápida por plataforma o la introducción de un payload personalizado.

En una ejecución normal, el operador selecciona el payload, define `LHOST` y `LPORT`, elige el formato y, si procede, ajusta encoder, iteraciones, bad characters, tamaño, template, plataforma, arquitectura, nombre de variable, `--smallest` o `-k`. Después de la generación, el programa crea un archivo de recursos con la configuración del handler y ofrece tres comportamientos: listener en segundo plano, listener en primer plano o únicamente generación del `.rc`.

Si se selecciona el envío, el menú permite usar el servidor HTTP local o una transferencia mediante SCP, SMB, FTP, Netcat o ADB. Debe aplicarse una allowlist de destinos y documentarse cada transferencia dentro de la evidencia del ejercicio. Para el servidor HTTP, el programa imprime una URL y comandos de descarga; **no ejecuta automáticamente el comando en el objetivo**.

## Salidas y estructura local

La estructura esperada después de una ejecución es la siguiente:

```text
.
├── MSFVenomPayloadGeneratorv4.0.py
├── README.md
├── payloads/
│   └── <payload>_<timestamp>.<extension>
└── rc_files/
    └── listener_<timestamp>.rc
```

Los directorios `payloads/` y `rc_files/` están destinados a datos de ejecución. El repositorio debe conservar únicamente el código y la documentación, nunca credenciales, capturas con información sensible, archivos `.rc` con infraestructura real ni binarios generados.

## Consideraciones de seguridad operacional

El proyecto automatiza acciones con impacto potencial sobre sistemas remotos. Antes de iniciar una prueba, el equipo debe confirmar el alcance por escrito, utilizar máquinas y cuentas de laboratorio cuando sea posible, registrar la autorización, establecer una ventana temporal y definir un procedimiento de interrupción. Los listeners deben permanecer limitados a interfaces y redes de prueba; el tráfico debe supervisarse desde los controles defensivos.

La implementación actual presenta varios puntos que deben considerarse antes de usarla fuera de un laboratorio:

| Observación | Riesgo | Mitigación recomendada |
|---|---|---|
| `PayloadHTTPServer` escucha en `0.0.0.0` | Expone el directorio `payloads/` a todas las interfaces alcanzables | Vincular a una interfaz concreta, aplicar firewall de laboratorio, usar una red aislada y detener el servicio al terminar |
| El servidor usa `os.chdir()` | Cambia el directorio de trabajo global del proceso y puede afectar operaciones posteriores | Sustituirlo por un handler con directorio explícito o encapsular el cambio de contexto |
| SMB construye credenciales en el argumento de `smbclient` | Las credenciales pueden quedar visibles en procesos, logs o historial | Preferir mecanismos de autenticación seguros, entrada interactiva o un almacén temporal con permisos restrictivos |
| FTP y Netcat no proporcionan por sí mismos confidencialidad o autenticidad robustas | Riesgo de exposición o manipulación durante la transferencia | Usar SCP/SSH o un canal de laboratorio controlado; verificar hash y registrar la transferencia |
| Netcat se ejecuta mediante `os.system()` | El parsing por shell aumenta el riesgo de inyección y de errores de quoting | Migrar a `subprocess.run()` con lista de argumentos y validación estricta de host/puerto |
| El monitor descarta excepciones con `except Exception: pass` | Puede ocultar fallos y producir una falsa sensación de monitorización activa | Registrar excepciones de forma segura y exponer estado de salud del monitor |
| No existe una allowlist de objetivos | Un error de entrada puede dirigir una transferencia a un sistema no autorizado | Añadir validación de CIDR/hostname, confirmación previa y bloqueo por defecto |
| No se verifica el hash del artefacto | Dificulta probar integridad y trazabilidad del archivo transferido | Generar SHA-256, conservarlo en la evidencia y verificarlo en el receptor |

Estas limitaciones son deliberadamente visibles en la documentación para que el uso ofensivo se traduzca en mejoras concretas de postura defensiva. Las técnicas de intérprete y ejecución deben validarse con telemetría EDR, Sysmon, registros de PowerShell, auditoría de procesos, DNS, proxy, firewall y autenticación, según el alcance del ejercicio.

## Perspectiva Purple Team

La actividad debe planificarse como una validación controlada de controles, no como una carrera por ejecutar un payload. MITRE ATT&CK describe **Command and Scripting Interpreter (T1059)** como el abuso de intérpretes para ejecutar comandos, scripts o binarios, incluyendo sub-técnicas como PowerShell, Windows Command Shell, Unix Shell, Python y JavaScript [2]. El proyecto puede servir para generar eventos de prueba asociados con esas superficies, pero el mapeo final debe basarse en el comportamiento realmente ejecutado y en la telemetría observada.

| Fase | Pregunta ofensiva | Evidencia defensiva esperada |
|---|---|---|
| Preparación | ¿Qué artefacto y qué canal de entrega se probarán? | Ticket de cambio, alcance autorizado, hash, host de laboratorio y ventana temporal |
| Ejecución | ¿Qué proceso inicia la cadena y con qué argumentos? | Árbol de procesos, línea de comandos, usuario, integridad y parent process |
| Transferencia | ¿Cómo llega el archivo al sistema de prueba? | Registros de proxy/firewall, SMB/SSH/FTP/HTTP, DNS y hash del archivo |
| Handler | ¿Qué conexión entrante o saliente se produce? | Flujos de red, destino, puerto, proceso propietario y alertas de IDS/IPS/EDR |
| Sesión | ¿Se detecta y contiene la sesión? | Alerta, tiempo de detección, tiempo de respuesta, aislamiento y cierre de proceso |
| Recuperación | ¿Se eliminaron procesos, archivos y reglas temporales? | Checklist de limpieza, revisión de persistencia y confirmación del estado final |

Los resultados deben registrar al menos: identificador del caso, objetivo autorizado, timestamp, operador, hash SHA-256, payload lógico y formato, canal de entrega, controles que alertaron, controles que bloquearon, tiempo de detección, tiempo de contención y acciones de cleanup. **No se deben almacenar secretos ni datos personales innecesarios**.

## Validación y pruebas seguras

La validación básica del código puede realizarse sin generar artefactos ni iniciar listeners mediante una comprobación de sintaxis:

```bash
python3 -m py_compile MSFVenomPayloadGeneratorv4.0.py
```

Para una prueba funcional, utilice una red de laboratorio desechable, un objetivo expresamente autorizado y un payload de prueba que no contenga datos reales. Verifique primero los listados, después la generación local y finalmente el handler. No pruebe la distribución remota hasta haber confirmado las reglas de firewall, el alcance y el procedimiento de rollback.

La herramienta no incluye una suite automatizada. Como mínimo, una futura contribución debería cubrir la selección de extensiones, la construcción de comandos, el saneamiento de nombres, la detección de puertos ocupados, el cierre del servidor HTTP, el parseo del log y la validación de entradas de host y puerto.

## Limitaciones conocidas

El programa depende de la salida y el comportamiento de la versión local de Metasploit. Las listas de formatos, payloads y encoders pueden cambiar entre versiones. La detección de sesiones depende del formato del log de Metasploit y de la coincidencia de una expresión regular IPv4; por tanto, puede no detectar todos los formatos, IPv6, sesiones con mensajes diferentes o logs rotados.

El proceso de `msfconsole` se inicia con salida canalizada cuando se usa el modo background, pero la herramienta no ofrece un gestor completo de ciclo de vida para todos los procesos descendientes. El operador debe verificar manualmente el PID, el estado del listener y el cierre de los procesos al finalizar.

La herramienta tampoco cifra el contenido de los payloads, no valida certificados, no autentica el servidor HTTP y no proporciona control de acceso multiusuario. Estas propiedades son inadecuadas para una infraestructura de producción o para una red no aislada.

## Higiene del repositorio

El `.gitignore` excluye los artefactos generados y los recursos locales. Antes de cada commit debe revisarse el diff y comprobar que no aparezcan contraseñas, tokens, direcciones internas sensibles, archivos `.rc`, binarios, logs o volcados de sesión.

```bash
git status --short
git diff --check
find payloads rc_files -type f -maxdepth 1 -print 2>/dev/null
```

Si se filtra una credencial, debe revocarse y rotarse inmediatamente; eliminarla de un commit posterior no basta para considerarla retirada del historial.

## Licencia y responsabilidad

Este repositorio se publica como material de laboratorio y automatización de pruebas autorizadas. Antes de asignar una licencia de código abierto, el propietario debe confirmar los derechos sobre el código y decidir las condiciones de redistribución. La publicación del repositorio no concede autorización para evaluar terceros ni transfiere la responsabilidad legal u operativa del uso.

## Referencias

[1]: https://docs.metasploit.com/docs/using-metasploit/basics/how-to-use-msfvenom.html "Metasploit Documentation — How to use msfvenom"

[2]: https://attack.mitre.org/techniques/T1059/ "MITRE ATT&CK — Command and Scripting Interpreter, T1059"

---

Documentación preparada para un flujo de trabajo de **Red Team/Purple Team autorizado**, con énfasis en trazabilidad, contención y mejora de controles defensivos.
