# -*- coding: utf-8 -*-
r"""Abre una consola real de Windows, ejecuta un guion de PowerShell y guarda la captura de pantalla de esa ventana.

Cada comando del guion se escribe en pantalla (con su prompt) y se ejecuta de verdad, de modo que la imagen muestra exactamente
lo que hizo el programa. La captura es de la pantalla (no se redibuja nada) y recorta solo el area de la consola.

Uso (desde la carpeta del proyecto, montada como G:):
    .venv\Scripts\python.exe scripts\capturar_terminal.py <guion.ps1> <salida.png> [--cols 112] [--filas 32]

En el guion, `Ejecutar 'comando'` imprime el prompt y el comando y luego lo ejecuta; `Comentario 'texto'` imprime una linea gris.
Requisitos: Windows, Pillow y una sesion de escritorio abierta (la ventana debe verse un instante).
"""
import argparse
import ctypes
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

from PIL import Image, ImageGrab

ctypes.windll.shcore.SetProcessDpiAwareness(2)   # coordenadas en pixeles fisicos
user32 = ctypes.windll.user32
HWND_TOPMOST, SWP_NOSIZE, SWP_SHOWWINDOW = -1, 0x0001, 0x0040

PREAMBULO = r"""
$Host.UI.RawUI.WindowTitle = '{titulo}'
$Host.UI.RawUI.BackgroundColor = 'Black'
$Host.UI.RawUI.ForegroundColor = 'Gray'
mode con: cols={cols} lines={filas} | Out-Null
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function prompt {{ 'PS> ' }}
function Ejecutar([string]$linea) {{
    Write-Host -NoNewline 'PS> ' -ForegroundColor Green
    Write-Host $linea
    Invoke-Expression $linea | Out-Host
}}
function Comentario([string]$texto) {{ Write-Host $texto -ForegroundColor DarkGray }}
Clear-Host
. '{guion}'
New-Item -ItemType File -Force '{marca}' | Out-Null
"""


def buscar_ventana(titulo: str, limite: float = 25) -> int:
    fin = time.time() + limite
    while time.time() < fin:
        hwnd = user32.FindWindowW(None, titulo)
        if hwnd:
            return hwnd
        time.sleep(0.3)
    raise TimeoutError("no apareció la ventana de la consola")


def area_cliente(hwnd: int) -> tuple[int, int, int, int]:
    rc = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    origen = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origen))
    return origen.x, origen.y, origen.x + rc.right, origen.y + rc.bottom


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def captura_ventana(hwnd: int):
    """Pide a Windows el contenido de la ventana (PrintWindow): no sale nada de lo que otra ventana tenga encima."""
    gdi32 = ctypes.windll.gdi32
    ptr = ctypes.c_void_p
    user32.GetWindowDC.restype, user32.GetWindowDC.argtypes = ptr, [wintypes.HWND]
    gdi32.CreateCompatibleDC.restype, gdi32.CreateCompatibleDC.argtypes = ptr, [ptr]
    gdi32.CreateCompatibleBitmap.restype, gdi32.CreateCompatibleBitmap.argtypes = ptr, [ptr, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype, gdi32.SelectObject.argtypes = ptr, [ptr, ptr]
    gdi32.GetDIBits.argtypes = [ptr, ptr, wintypes.UINT, wintypes.UINT, ptr, ptr, wintypes.UINT]
    user32.PrintWindow.argtypes = [wintypes.HWND, ptr, wintypes.UINT]
    gdi32.DeleteObject.argtypes, gdi32.DeleteDC.argtypes = [ptr], [ptr]
    user32.ReleaseDC.argtypes = [wintypes.HWND, ptr]
    rc = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    ancho, alto = rc.right - rc.left, rc.bottom - rc.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    mapa = gdi32.CreateCompatibleBitmap(hdc, ancho, alto)
    gdi32.SelectObject(mdc, mapa)
    imagen = None
    if user32.PrintWindow(hwnd, mdc, 2):          # 2 = PW_RENDERFULLCONTENT
        info = BITMAPINFOHEADER()
        info.biSize, info.biWidth, info.biHeight = ctypes.sizeof(BITMAPINFOHEADER), ancho, -alto
        info.biPlanes, info.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(ancho * alto * 4)
        gdi32.GetDIBits(mdc, mapa, 0, alto, buf, ctypes.byref(info), 0)
        completa = Image.frombuffer("RGB", (ancho, alto), buf, "raw", "BGRX", 0, 1)
        area = area_cliente(hwnd)
        recorte = completa.crop((area[0] - rc.left, area[1] - rc.top, area[2] - rc.left, area[3] - rc.top))
        if max(recorte.convert("L").getextrema()) > 40:        # una imagen casi negra significa que PrintWindow no dibujó
            imagen = recorte
    gdi32.DeleteObject(mapa)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return imagen


def capturar(guion: pathlib.Path, salida: pathlib.Path, cols: int, filas: int, espera: float) -> None:
    titulo = f"captura-{os.getpid()}-{int(time.time())}"
    with tempfile.TemporaryDirectory() as tmp:
        marca = pathlib.Path(tmp) / "listo.flag"
        envoltorio = pathlib.Path(tmp) / "envoltorio.ps1"
        copia = pathlib.Path(tmp) / "guion.ps1"       # PowerShell 5.1 solo lee bien las tildes si el archivo lleva BOM
        copia.write_text(guion.read_text(encoding="utf-8"), encoding="utf-8-sig")
        envoltorio.write_text(PREAMBULO.format(titulo=titulo, cols=cols, filas=filas, guion=copia, marca=marca),
                              encoding="utf-8-sig")
        proceso = subprocess.Popen(["conhost.exe", "powershell.exe", "-NoLogo", "-NoProfile", "-NoExit",
                                    "-ExecutionPolicy", "Bypass", "-File", str(envoltorio)])
        try:
            hwnd = buscar_ventana(titulo)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 40, 0, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW)
            fin = time.time() + espera
            while not marca.exists():
                if time.time() > fin:
                    raise TimeoutError("el guion no terminó a tiempo")
                time.sleep(0.4)
            time.sleep(1.0)                       # deja que la consola termine de dibujar
            area = area_cliente(hwnd)
            trabajo = wintypes.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(trabajo), 0)      # SPI_GETWORKAREA: pantalla sin la barra de tareas
            if area[3] > trabajo.bottom:
                raise RuntimeError(f"la consola ({area[3]} px) se sale del área de trabajo ({trabajo.bottom} px): reduce las filas")
            salida.parent.mkdir(parents=True, exist_ok=True)
            imagen = captura_ventana(hwnd)
            if imagen is None:          # si PrintWindow no entrega contenido, se recorta la pantalla
                imagen = ImageGrab.grab(bbox=area, all_screens=True)
            imagen.save(salida)
        finally:
            subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"], capture_output=True, check=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("guion", type=pathlib.Path)
    ap.add_argument("salida", type=pathlib.Path)
    ap.add_argument("--cols", type=int, default=118)
    ap.add_argument("--filas", type=int, default=32)
    ap.add_argument("--espera", type=float, default=120, help="segundos máximos que puede tardar el guion")
    args = ap.parse_args()
    capturar(args.guion.resolve(), args.salida.resolve(), args.cols, args.filas, args.espera)
    print("captura guardada:", args.salida)

