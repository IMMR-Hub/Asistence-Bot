#!/usr/bin/env python3
"""
START.py - Inicia todo automáticamente
Solo ejecuta: python START.py
"""

import subprocess
import time
import sys
import os
import requests

def run_command(cmd, description=""):
    """Ejecuta un comando y muestra el resultado"""
    if description:
        print(f"\n{description}...", end=" ", flush=True)
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅")
            return True
        else:
            print(f"❌\n{result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_docker():
    """Verifica si Docker está instalado"""
    print("\n" + "="*40)
    print("Verificando Docker...")
    print("="*40)
    
    if run_command("docker --version", "Docker"):
        return True
    else:
        print("\n❌ Docker no está instalado")
        print("Descárgalo en: https://www.docker.com/products/docker-desktop")
        return False

def start_services():
    """Inicia los servicios con Docker Compose"""
    print("\n" + "="*40)
    print("Iniciando servicios...")
    print("="*40)
    
    os.chdir(r"C:\Users\Daniel\universal-sales-automation-core")
    
    if run_command("docker compose up --build -d", "Docker Compose"):
        return True
    else:
        print("\n❌ Error al iniciar servicios")
        return False

def wait_for_api(max_retries=15):
    """Espera a que la API esté lista"""
    print("\n" + "="*40)
    print("Esperando a que la API se inicie...")
    print("="*40)
    
    for attempt in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                print("✅ API lista")
                return True
        except:
            print(f"Intento {attempt + 1}/{max_retries}...", end=" ", flush=True)
            time.sleep(2)
            if attempt < max_retries - 1:
                print()
    
    print("❌ API no responde")
    return False

def show_urls():
    """Muestra las URLs importantes"""
    print("\n" + "="*40)
    print("✅ ¡TODO LISTO!")
    print("="*40)
    print("\n🌐 Tu aplicación:")
    print("   http://localhost:8000")
    print("\n📚 Documentación (Swagger):")
    print("   http://localhost:8000/docs")
    print("\n🔍 Ver estado:")
    print("   http://localhost:8000/ready")
    print("\n" + "="*40)

def main():
    print("\n" + "="*40)
    print("UNIVERSAL SALES AUTOMATION")
    print("Inicializador Automático")
    print("="*40)
    
    if not check_docker():
        return 1
    
    if not start_services():
        return 1
    
    if not wait_for_api():
        print("\n⚠️  Nota: Los servicios están iniciándose.")
        print("   Espera 1-2 minutos más y luego abre:")
        print("   http://localhost:8000")
        return 1
    
    show_urls()
    
    print("\nPresiona ENTER para cerrar esta ventana...")
    input()
    return 0

if __name__ == "__main__":
    sys.exit(main())
