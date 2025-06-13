# updater.py
import requests
import json
import os
import hashlib
import subprocess
import sys
import time # <<< CORREÇÃO 1: Importar a biblioteca time

# --- CONFIGURAÇÃO ---
# <<< CORREÇÃO 2: URL alterada para a versão RAW correta >>>
BASE_URL = "https://raw.githubusercontent.com/Levisgod/Furanito/main/BotPokemon/"

BOT_EXECUTABLE = "bot.exe" 
# --- FIM DA CONFIGURAÇÃO ---

def calculate_local_hash(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            h.update(chunk)
    return h.hexdigest()

def check_for_updates():
    print("--- Verificador de Atualizações ---")
    
    try:
        manifest_url = BASE_URL + "manifest.json"
        print(f"A obter manifesto de: {manifest_url}")
        response = requests.get(manifest_url)
        response.raise_for_status()
        remote_manifest = response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Não foi possível obter o manifesto do servidor. Verifica a tua ligação à internet ou o URL.")
        print(e)
        return
    except json.JSONDecodeError:
        print("ERRO: O ficheiro manifest.json remoto está mal formatado ou corrompido.")
        return

    local_manifest = {}
    if os.path.exists("manifest.json"):
        try:
            with open("manifest.json", 'r') as f:
                local_manifest = json.load(f)
        except json.JSONDecodeError:
            print("AVISO: O manifest.json local está corrompido. A forçar a atualização.")
            local_manifest = {}

    local_version = local_manifest.get('version', '0.0.0')
    remote_version = remote_manifest.get('version', '0.0.0')

    print(f"Versão Local: {local_version} | Versão Remota: {remote_version}")

    # Verifica se os hashes locais são iguais aos remotos
    files_are_up_to_date = True
    remote_files = remote_manifest.get('files', {})
    if local_version != remote_version:
        files_are_up_to_date = False
    else:
        for relative_path, remote_hash in remote_files.items():
            if calculate_local_hash(os.path.normpath(relative_path)) != remote_hash:
                files_are_up_to_date = False
                break
    
    if files_are_up_to_date:
        print("A tua aplicação já está atualizada.")
        return

    print(f"Nova versão {remote_version} encontrada! A atualizar...")
    
    for relative_path, remote_hash in remote_files.items():
        local_path = os.path.normpath(relative_path)
        if calculate_local_hash(local_path) != remote_hash:
            print(f"  A transferir: {relative_path}")
            try:
                if os.path.dirname(local_path):
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                file_url = BASE_URL + relative_path.replace("\\", "/")
                file_response = requests.get(file_url, stream=True)
                file_response.raise_for_status()
                
                with open(local_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as e:
                print(f"    ERRO ao transferir {relative_path}: {e}")

    with open("manifest.json", 'w') as f:
        json.dump(remote_manifest, f, indent=4)
        
    print("Atualização concluída com sucesso!")


def run_bot():
    if not os.path.exists(BOT_EXECUTABLE):
        print(f"\nERRO: O ficheiro principal '{BOT_EXECUTABLE}' não foi encontrado.")
        print("A atualização pode ter falhado. Tenta executar o updater novamente.")
        return

    print(f"\nA iniciar o {BOT_EXECUTABLE}...")
    try:
        subprocess.Popen([BOT_EXECUTABLE])
    except Exception as e:
        print(f"ERRO ao iniciar o bot: {e}")


if __name__ == "__main__":
    try:
        check_for_updates()
    except Exception as e:
        print(f"\nOcorreu um erro inesperado durante a atualização: {e}")
    
    run_bot()
    
    print("\nO updater vai fechar em 5 segundos...")
    time.sleep(5)
    sys.exit()