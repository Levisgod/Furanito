# updater.py
import requests
import json
import os
import hashlib
import subprocess
import sys

# --- CONFIGURAÇÃO ---
# Coloca aqui o URL RAW do teu repositório no GitHub.
# O formato é: https://raw.githubusercontent.com/SEU-NOME/NOME-DO-REPO/main/
# **NOTA**: Tem de terminar com a barra "/"
BASE_URL = "https://raw.githubusercontent.com/Levisgod/Furanito/refs/heads/main/BotPokemo/manifest.json"

# Nome do ficheiro .exe principal do teu bot
BOT_EXECUTABLE = "bot.exe" 
# --- FIM DA CONFIGURAÇÃO ---

def calculate_local_hash(filepath):
    """Calcula o hash de um ficheiro local. Igual ao do gerador."""
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            h.update(chunk)
    return h.hexdigest()

def check_for_updates():
    """Função principal que verifica e aplica as atualizações."""
    print("--- Verificador de Atualizações ---")
    
    # 1. Baixar o manifesto do servidor
    try:
        manifest_url = BASE_URL + "manifest.json"
        print(f"A obter manifesto de: {manifest_url}")
        response = requests.get(manifest_url)
        response.raise_for_status() # Lança um erro se não conseguir baixar (ex: 404)
        remote_manifest = response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Não foi possível obter o manifesto do servidor. Verifica a tua ligação à internet ou o URL.")
        print(e)
        return

    # 2. Ler o manifesto local, se existir
    local_manifest = {}
    if os.path.exists("manifest.json"):
        with open("manifest.json", 'r') as f:
            local_manifest = json.load(f)

    local_version = local_manifest.get('version', '0.0.0')
    remote_version = remote_manifest.get('version', '0.0.0')

    print(f"Versão Local: {local_version} | Versão Remota: {remote_version}")

    if remote_version == local_version:
        print("A tua aplicação já está atualizada.")
        return # Não há nada para fazer

    print(f"Nova versão {remote_version} encontrada! A atualizar...")
    
    # 3. Comparar ficheiros e baixar os que são diferentes
    files_to_update = remote_manifest.get('files', {})
    for relative_path, remote_hash in files_to_update.items():
        local_path = os.path.normpath(relative_path) # Converte barras para o sistema operativo atual
        
        local_hash = calculate_local_hash(local_path)

        if local_hash != remote_hash:
            print(f"  A transferir: {relative_path}")
            try:
                # Cria as pastas necessárias (ex: a pasta 'tesseract')
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Baixa o ficheiro
                file_url = BASE_URL + relative_path
                file_content = requests.get(file_url).content
                
                # Escreve o ficheiro no disco
                with open(local_path, 'wb') as f:
                    f.write(file_content)
            except Exception as e:
                print(f"    ERRO ao transferir {relative_path}: {e}")
                # Poderias adicionar lógica para parar ou tentar de novo aqui

    # 4. Guardar o novo manifesto localmente para a próxima verificação
    with open("manifest.json", 'w') as f:
        json.dump(remote_manifest, f, indent=4)
        
    print("Atualização concluída com sucesso!")


def run_bot():
    """Executa o bot principal."""
    if not os.path.exists(BOT_EXECUTABLE):
        print(f"\nERRO: O ficheiro principal '{BOT_EXECUTABLE}' não foi encontrado.")
        print("A atualização pode ter falhado. Tenta executar o updater novamente.")
        return

    print(f"\nA iniciar o {BOT_EXECUTABLE}...")
    # Usamos Popen para que o updater possa fechar sem fechar o bot
    subprocess.Popen([BOT_EXECUTABLE])


if __name__ == "__main__":
    try:
        check_for_updates()
    except Exception as e:
        print(f"\nOcorreu um erro inesperado durante a atualização: {e}")
    
    run_bot()
    
    # Pequena pausa para o utilizador ler as mensagens antes de a janela fechar
    print("\nO updater vai fechar em 5 segundos...")
    time.sleep(5)
    sys.exit()