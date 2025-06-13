# updater.py (Final)
import requests
import json
import os
import hashlib
import subprocess
import sys
import time

# --- CONFIGURAÇÃO COM OS LINKS CORRETOS ---
GITHUB_USER = "Levisgod"
GITHUB_REPO = "Furanito"
REPO_SUBFOLDER = "BotPokemo/" 
BOT_EXECUTABLE = "bot.exe" 

# Constrói os URLs base a partir da configuração
BASE_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/"
BASE_RELEASE_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/"
# --- FIM DA CONFIGURAÇÃO ---

def calculate_local_hash(filepath):
    if not os.path.exists(filepath): return None
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096): h.update(chunk)
    return h.hexdigest()

def download_file(url, local_path, file_description):
    try:
        print(f"  > A transferir {file_description}...")
        print(f"    URL: {url}")
        
        # Cria a pasta se não existir
        if os.path.dirname(local_path) and not os.path.exists(os.path.dirname(local_path)):
            os.makedirs(os.path.dirname(local_path))
        
        file_response = requests.get(url, stream=True)
        file_response.raise_for_status() # Dará erro para 404 Not Found, etc.
        
        with open(local_path, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"    [OK] '{local_path}' transferido com sucesso.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"    [ERRO] Falha ao transferir {file_description}. Verifica o link ou a tua ligação.")
        print(f"    Detalhe: {e}")
        return False

def check_for_updates():
    print("--- Verificador de Atualizações ---")
    manifest_url = BASE_RAW_URL + REPO_SUBFOLDER + "manifest.json"
    
    try:
        print(f"A obter manifesto de: {manifest_url}")
        response = requests.get(manifest_url)
        response.raise_for_status()
        remote_manifest = response.json()
    except Exception as e:
        print(f"ERRO: Não foi possível obter o manifesto do servidor. ({e})")
        return False

    # Carrega a versão local
    local_version = "0.0.0"
    if os.path.exists("manifest.json"):
        try:
            with open("manifest.json", 'r') as f:
                local_manifest = json.load(f)
                local_version = local_manifest.get('version', '0.0.0')
        except json.JSONDecodeError:
            print("AVISO: manifest.json local corrompido. A forçar atualização.")

    remote_version = remote_manifest.get('version', '0.0.0')
    print(f"Versão Local: {local_version} | Versão Remota: {remote_version}")

    if local_version == remote_version:
        print("\nO teu bot já está na versão mais recente.")
        return True

    print(f"\nNova versão {remote_version} encontrada! A iniciar atualização...")
    update_failed = False
    
    # A TAG da release tem de ser igual à versão no manifesto
    release_tag = remote_version
    
    # Verifica os ficheiros da Release
    files_to_update = remote_manifest.get('files_in_release', {})
    for filename, remote_hash in files_to_update.items():
        if calculate_local_hash(filename) != remote_hash:
            file_url = BASE_RELEASE_URL + release_tag + "/" + filename
            if not download_file(file_url, filename, f"'{filename}' da Release '{release_tag}'"):
                update_failed = True

    if update_failed:
        print("\nA atualização falhou devido a erros na transferência.")
        return False
    else:
        # Guarda o novo manifesto localmente apenas se tudo correu bem
        with open("manifest.json", 'w') as f:
            json.dump(remote_manifest, f, indent=4)
        print("\nAtualização concluída com sucesso!")
        return True

def run_bot():
    if not os.path.exists(BOT_EXECUTABLE):
        print(f"\nERRO: O ficheiro principal '{BOT_EXECUTABLE}' não foi encontrado.")
        print("A atualização pode ter falhado ou o ficheiro não foi transferido.")
        return
        
    print(f"\nA iniciar o {BOT_EXECUTABLE}...")
    try:
        # Inicia o bot como um processo separado
        subprocess.Popen([BOT_EXECUTABLE])
    except Exception as e:
        print(f"ERRO CRÍTICO ao tentar iniciar o bot: {e}")

if __name__ == "__main__":
    update_successful = False
    try:
        update_successful = check_for_updates()
    except Exception as e:
        print(f"\nOcorreu um erro inesperado durante a verificação: {e}")
    
    if update_successful:
        run_bot()
    else:
        print("\nO bot não será iniciado porque a atualização não foi concluída.")
    
    print("\nO updater vai fechar em 10 segundos...")
    time.sleep(10)
    sys.exit()