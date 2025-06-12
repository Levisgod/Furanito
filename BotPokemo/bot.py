import pyautogui
import time
import sys
import threading
import tkinter as tk
from tkinter import font, ttk
from PIL import Image, ImageOps
import os
import json

try:
    import win32gui, win32com.client, psutil, pytesseract
    from pynput import mouse
    from thefuzz import fuzz
except ImportError:
    print("ERRO: Bibliotecas em falta. Execute:")
    print("pip install pywin32 psutil pytesseract pillow pynput")
    print("pip install thefuzz python-Levenshtein") 
    sys.exit()

# --- CONFIGURAÇÕES ---

CONFIG_FILE = "config.json"
NOME_JANELA = "Pokemon Blaze Online"
IMAGEM_BATALHA = 'batalha.png'
IMAGEM_FIM_BATALHA = 'fim_batalha.png' 
IMAGEM_PEIXE = 'peixe.png' 
DEFAULT_POKEMON_PARAR = "shiny, ditto, zigzagoon" 

def get_tesseract_path():
    if getattr(sys, 'frozen', False): base_path = sys._MEIPASS
    else: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'tesseract', 'tesseract.exe')

try:
    pytesseract.pytesseract.tesseract_cmd = get_tesseract_path()
    print(f"Tesseract configurado para usar: {get_tesseract_path()}")
except Exception as e: print(f"Erro ao configurar Tesseract: {e}")

REGIAO_NOME_POKEMON = (0, 0, 0, 0)
POSICAO_BAG = (0, 0)
POSICAO_POKEBOLA = (0, 0)

SEQUENCIA_MOVIMENTO = ['a', 'd']
TECLA_PESCA = 'f'
COOLDOWN_RECAST_PESCA = 4.0

CONFIANCA = 0.7
CONFIANCA_PEIXE = 0.8 
CONFIANCA_FIM_BATALHA = 0.8
# <<< MUDANÇA FINAL: O limite foi ajustado para o valor que observámos! >>>
FUZZY_MATCH_THRESHOLD = 70 

DURACAO_MOVIMENTO = 0.05
PAUSA_ENTRE_ATAQUES = 1.0
PAUSA_INICIO_BATALHA = 0.3 
PAUSA_FIM_BATALHA = 0.2
PAUSA_ENTRE_CLICKS_CAPTURA = 0.5
TIMEOUT_FIM_BATALHA = 2.0


class BotControllerGUI(tk.Tk):
    # ... (Todo o resto do código permanece exatamente o mesmo) ...
    def __init__(self):
        super().__init__()
        self.title("Controlador do Bot"); self.geometry("380x460"); self.wm_attributes("-topmost", 1)
        self.bot_is_running = False; self.bot_thread = None; self.indice_movimento_atual = 0; self.listener = None; self.last_action_time = 0; self.capture_count = 0; self.ocr_calibration_step = 0; self.capture_calibration_step = 0; self.first_click = None
        self.default_font = font.Font(family="Helvetica", size=10); self.bold_font = font.Font(family="Helvetica", size=10, weight="bold")
        self.bot_mode_var = tk.StringVar(value="patrulha"); self.pokemon_name_var = tk.StringVar(value=DEFAULT_POKEMON_PARAR); self.region_var = tk.StringVar(value=f"Região: {REGIAO_NOME_POKEMON}"); self.attack_choice_var = tk.StringVar(value="3"); self.capture_enabled_var = tk.BooleanVar(value=True); self.bag_pos_var = tk.StringVar(value=f"Bag: {POSICAO_BAG}"); self.ball_pos_var = tk.StringVar(value=f"Bola: {POSICAO_POKEBOLA}"); self.capture_count_var = tk.StringVar(value="Alvos Capturados: 0"); self.invert_colors_var = tk.BooleanVar(value=False)
        self.load_config()
        if os.path.exists(CONFIG_FILE) and REGIAO_NOME_POKEMON != (0, 0, 0, 0): status_inicial, status_color = "Bot parado. Configuração carregada.", "green"
        else: status_inicial, status_color = "PRIMEIRA VEZ? Vá à aba de Calibração!", "red"
        self.status_label = tk.Label(self, text=status_inicial, font=self.default_font, fg=status_color); self.status_label.pack(pady=5)
        notebook = ttk.Notebook(self); notebook.pack(pady=10, padx=10, fill="both", expand=True)
        tab_control = ttk.Frame(notebook); tab_calibration = ttk.Frame(notebook)
        notebook.add(tab_control, text='Controle Principal'); notebook.add(tab_calibration, text='Calibração')
        self.mode_frame = tk.LabelFrame(tab_control, text="Modo de Operação", font=self.default_font); self.mode_frame.pack(pady=5, padx=10, fill=tk.X)
        self.patrol_radio = tk.Radiobutton(self.mode_frame, text="Patrulha (Andar)", variable=self.bot_mode_var, value="patrulha", font=self.default_font); self.patrol_radio.pack(side=tk.LEFT, expand=True)
        self.fish_radio = tk.Radiobutton(self.mode_frame, text="Pesca (Parado)", variable=self.bot_mode_var, value="pesca", font=self.default_font); self.fish_radio.pack(side=tk.LEFT, expand=True)
        self.target_frame = tk.LabelFrame(tab_control, text="Pokémon Alvo (separar por vírgula)", font=self.default_font); self.target_frame.pack(pady=5, padx=10, fill=tk.X)
        self.pokemon_entry = tk.Entry(self.target_frame, textvariable=self.pokemon_name_var, font=self.default_font); self.pokemon_entry.pack(pady=5, padx=5, fill=tk.X)
        self.attack_frame = tk.LabelFrame(tab_control, text="Ação de Batalha Padrão", font=self.default_font); self.attack_frame.pack(pady=5, padx=10, fill=tk.X)
        self.radio_buttons = []
        for i in range(1, 5): rb = tk.Radiobutton(self.attack_frame, text=f"{i}", variable=self.attack_choice_var, value=str(i)); rb.pack(side=tk.LEFT, expand=True); self.radio_buttons.append(rb)
        run_rb = tk.Radiobutton(self.attack_frame, text="Run", variable=self.attack_choice_var, value="run"); run_rb.pack(side=tk.LEFT, expand=True); self.radio_buttons.append(run_rb)
        self.stats_frame = tk.LabelFrame(tab_control, text="Estatísticas", font=self.default_font); self.stats_frame.pack(pady=5, padx=10, fill=tk.X)
        self.capture_count_label = tk.Label(self.stats_frame, textvariable=self.capture_count_var, font=self.default_font); self.capture_count_label.pack(pady=5, padx=5)
        self.calibration_frame = tk.LabelFrame(tab_calibration, text="Calibração do OCR", font=self.default_font); self.calibration_frame.pack(pady=10, padx=10, fill=tk.X)
        ocr_buttons_frame = tk.Frame(self.calibration_frame); ocr_buttons_frame.pack(fill=tk.X, pady=5)
        self.calibrate_ocr_button = tk.Button(ocr_buttons_frame, text="Calibrar Região OCR", command=self.start_ocr_calibration, font=self.default_font); self.calibrate_ocr_button.pack(side=tk.LEFT, padx=5)
        self.test_ocr_button = tk.Button(ocr_buttons_frame, text="Testar OCR", command=self.test_ocr, font=self.default_font); self.test_ocr_button.pack(side=tk.LEFT, padx=5)
        self.region_label = tk.Label(self.calibration_frame, textvariable=self.region_var, font=self.default_font); self.region_label.pack(fill=tk.X, padx=5)
        self.invert_colors_check = tk.Checkbutton(self.calibration_frame, text="Inverter Cores (para texto branco)", variable=self.invert_colors_var, font=self.default_font); self.invert_colors_check.pack(anchor=tk.W, padx=5)
        self.capture_frame = tk.LabelFrame(tab_calibration, text="Captura Automática", font=self.default_font); self.capture_frame.pack(pady=10, padx=10, fill=tk.X)
        self.capture_check = tk.Checkbutton(self.capture_frame, text="Tentar Capturar Pokémon Alvo", variable=self.capture_enabled_var, font=self.default_font); self.capture_check.pack(anchor=tk.W, padx=5)
        capture_buttons_frame = tk.Frame(self.capture_frame); capture_buttons_frame.pack(fill=tk.X, pady=5)
        self.calibrate_capture_button = tk.Button(capture_buttons_frame, text="Calibrar Captura", command=self.start_capture_calibration, font=self.default_font); self.calibrate_capture_button.pack(side=tk.LEFT, padx=5)
        self.bag_pos_label = tk.Label(capture_buttons_frame, textvariable=self.bag_pos_var, font=self.default_font); self.bag_pos_label.pack(side=tk.LEFT, padx=5)
        self.ball_pos_label = tk.Label(capture_buttons_frame, textvariable=self.ball_pos_var, font=self.default_font); self.ball_pos_label.pack(side=tk.LEFT, padx=5)
        self.start_button = tk.Button(self, text="Start Bot", command=self.start_bot, font=self.bold_font, bg="#4CAF50", fg="white"); self.start_button.pack(pady=5, fill=tk.X, padx=20)
        self.stop_button = tk.Button(self, text="Stop Bot", command=self.stop_bot, font=self.bold_font, bg="#f44336", fg="white", state=tk.DISABLED); self.stop_button.pack(pady=(0,5), fill=tk.X, padx=20)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    def load_config(self):
        global REGIAO_NOME_POKEMON, POSICAO_BAG, POSICAO_POKEBOLA
        try:
            with open(CONFIG_FILE, 'r') as f: config_data = json.load(f)
            REGIAO_NOME_POKEMON = tuple(config_data.get('regiao_ocr', (0,0,0,0))); self.invert_colors_var.set(config_data.get('inverter_cores', False)); POSICAO_BAG = tuple(config_data.get('posicao_bag', (0,0))); POSICAO_POKEBOLA = tuple(config_data.get('posicao_pokebola', (0,0)))
            self.region_var.set(f"Região: {REGIAO_NOME_POKEMON}"); self.bag_pos_var.set(f"Bag: {POSICAO_BAG}"); self.ball_pos_var.set(f"Bola: {POSICAO_POKEBOLA}")
        except (FileNotFoundError, json.JSONDecodeError): print("Arquivo de config não encontrado.")
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f: json.dump({ 'regiao_ocr': REGIAO_NOME_POKEMON, 'posicao_bag': POSICAO_BAG, 'posicao_pokebola': POSICAO_POKEBOLA, 'inverter_cores': self.invert_colors_var.get() }, f, indent=4)
    def update_status(self, message, color="black"): self.status_label.config(text=message, fg=color)
    def update_capture_count_label(self): self.capture_count_var.set(f"Alvos Capturados: {self.capture_count}")
    def start_ocr_calibration(self): self.update_status("CALIBRAR OCR: Clique no CANTO SUPERIOR ESQUERDO.", "blue"); self.ocr_calibration_step = 1; self.capture_calibration_step = 0; self.listener = mouse.Listener(on_click=self.on_click); self.listener.start()
    def start_capture_calibration(self): self.update_status("CALIBRAR CAPTURA: Clique no botão da BAG.", "blue"); self.capture_calibration_step = 1; self.ocr_calibration_step = 0; self.listener = mouse.Listener(on_click=self.on_click); self.listener.start()
    def on_click(self, x, y, button, pressed):
        if not pressed: return
        if self.ocr_calibration_step > 0:
            if self.ocr_calibration_step == 1: self.first_click = (x, y); self.ocr_calibration_step = 2; self.after(0, self.update_status, "Ótimo! Agora clique no CANTO INFERIOR DIREITO.", "blue")
            elif self.ocr_calibration_step == 2:
                global REGIAO_NOME_POKEMON; REGIAO_NOME_POKEMON = (self.first_click[0], self.first_click[1], x - self.first_click[0], y - self.first_click[1]); self.ocr_calibration_step = 0; self.save_config(); self.after(0, self.update_status, "Calibração OCR concluída!", "green"); self.after(0, self.region_var.set, f"Região: {REGIAO_NOME_POKEMON}"); 
                if self.listener: self.listener.stop()
        elif self.capture_calibration_step > 0:
            if self.capture_calibration_step == 1: global POSICAO_BAG; POSICAO_BAG = (x, y); self.capture_calibration_step = 2; self.after(0, self.update_status, "BAG salva! Agora clique na POKÉBOLA.", "blue"); self.after(0, self.bag_pos_var.set, f"Bag: {POSICAO_BAG}")
            elif self.capture_calibration_step == 2:
                global POSICAO_POKEBOLA; POSICAO_POKEBOLA = (x, y); self.capture_calibration_step = 0; self.save_config(); self.after(0, self.update_status, "Calibração de captura concluída!", "green"); self.after(0, self.ball_pos_var.set, f"Bola: {POSICAO_POKEBOLA}"); 
                if self.listener: self.listener.stop()
    def start_bot(self):
        self.save_config()
        if REGIAO_NOME_POKEMON == (0, 0, 0, 0): self.update_status("ERRO: Vá à aba 'Calibração' e calibre o OCR!", "red"); return
        if self.capture_enabled_var.get() and (POSICAO_BAG == (0,0) or POSICAO_POKEBOLA == (0,0)): self.update_status("ERRO: Vá à aba 'Calibração' e calibre a captura!", "red"); return
        if self.bot_mode_var.get() == 'pesca' and not os.path.exists(IMAGEM_PEIXE): self.update_status(f"ERRO: Imagem '{IMAGEM_PEIXE}' não encontrada!", "red"); return
        if not os.path.exists(IMAGEM_FIM_BATALHA): self.update_status(f"ERRO: Imagem '{IMAGEM_FIM_BATALHA}' não encontrada!", "red"); return
        if not self.bot_is_running:
            if not self.ativar_janela_jogo(): self.update_status(f"Janela '{NOME_JANELA}' não encontrada!", "red"); return
            self.capture_count = 0; self.update_capture_count_label(); self.last_action_time = 0; self.bot_is_running = True
            self.update_status("Bot a iniciar...", "blue"); self.bot_thread = threading.Thread(target=self.run_bot_logic, daemon=True); self.bot_thread.start()
            self.start_button.config(state=tk.DISABLED); self.stop_button.config(state=tk.NORMAL)
            for widget in [self.patrol_radio, self.fish_radio, self.pokemon_entry, self.calibrate_ocr_button, self.test_ocr_button, self.invert_colors_check, self.calibrate_capture_button, self.capture_check] + self.radio_buttons: widget.config(state=tk.DISABLED)
    def stop_bot(self):
        if self.bot_is_running:
            self.bot_is_running = False;
            if self.bot_thread and self.bot_thread.is_alive(): self.bot_thread.join(timeout=0.5)
            self.update_status("Bot parado.", "green"); self.start_button.config(state=tk.NORMAL); self.stop_button.config(state=tk.DISABLED)
            for widget in [self.patrol_radio, self.fish_radio, self.pokemon_entry, self.calibrate_ocr_button, self.test_ocr_button, self.invert_colors_check, self.calibrate_capture_button, self.capture_check] + self.radio_buttons: widget.config(state=tk.NORMAL)
    def on_closing(self): self.save_config(); self.stop_bot(); self.destroy()
    def tentar_capturar(self):
        self.update_status("Tentando capturar!", "purple");
        if not self.ativar_janela_jogo(): self.update_status("Janela do jogo perdida!", "red"); return
        pyautogui.moveTo(POSICAO_BAG, duration=0.2); pyautogui.click(); time.sleep(PAUSA_ENTRE_CLICKS_CAPTURA)
        pyautogui.moveTo(POSICAO_POKEBOLA, duration=0.2); pyautogui.click(); time.sleep(0.2)
        self.update_status("Aguardando resultado...", "cyan"); start_time = time.time()
        while self.bot_is_running:
            try:
                if pyautogui.locateOnScreen(IMAGEM_FIM_BATALHA, confidence=CONFIANCA_FIM_BATALHA): self.capture_count += 1; self.after(0, self.update_capture_count_label); self.update_status(f"Capturado! (Total: {self.capture_count})", "magenta"); time.sleep(1.0); return
            except pyautogui.PyAutoGUIException: pass
            if time.time() - start_time > TIMEOUT_FIM_BATALHA:
                self.update_status("Timeout! Captura falhou.", "orange");
                try:
                    if pyautogui.locateOnScreen(IMAGEM_BATALHA, confidence=CONFIANCA): self.lutar()
                except pyautogui.PyAutoGUIException: pass
                return
            time.sleep(0.05)
    def test_ocr(self):
        if REGIAO_NOME_POKEMON[2] <= 0: self.update_status("ERRO: Região OCR não calibrada!", "red"); return
        try:
            self.ativar_janela_jogo(); time.sleep(0.2)
            screenshot = pyautogui.screenshot(region=REGIAO_NOME_POKEMON); img_cinza = screenshot.convert('L')
            if self.invert_colors_var.get(): img_cinza = ImageOps.invert(img_cinza)
            img_bw = img_cinza.point(lambda x: 0 if x < 128 else 255, '1'); img_bw.save("ocr_test_image.png")
            texto_extraido = pytesseract.image_to_string(img_bw, config='--psm 7').strip().lower()
            if not texto_extraido: self.update_status("OCR não leu nenhum texto.", "orange"); return
            lista_alvos = [nome.strip().lower() for nome in self.pokemon_name_var.get().split(',') if nome.strip()]
            if not lista_alvos: self.update_status(f"OCR Leu: '{texto_extraido}' (Sem alvos)", "blue"); return
            best_match = max(lista_alvos, key=lambda alvo: fuzz.partial_ratio(alvo, texto_extraido))
            best_score = fuzz.partial_ratio(best_match, texto_extraido)
            self.update_status(f"'{texto_extraido}' -> Melhor Match: '{best_match}' ({best_score}%)", "blue")
            print(f"[TESTE OCR] Texto lido: '{texto_extraido}'. Melhor correspondência: '{best_match}' com pontuação de {best_score}%.")
        except Exception as e: self.update_status(f"Erro no teste de OCR: {e}", "red")
    def is_target_pokemon(self):
        nomes_alvo_str = self.pokemon_name_var.get().strip();
        if not nomes_alvo_str or REGIAO_NOME_POKEMON[2] <= 0: return False
        lista_alvos = [nome.strip().lower() for nome in nomes_alvo_str.split(',') if nome.strip()]
        if not lista_alvos: return False
        try:
            screenshot_original = pyautogui.screenshot(region=REGIAO_NOME_POKEMON); screenshot_original.save("battle_ocr_debug.png")
            img_cinza = screenshot_original.convert('L')
            if self.invert_colors_var.get(): img_cinza = ImageOps.invert(img_cinza)
            img_bw = img_cinza.point(lambda x: 0 if x < 128 else 255, '1')
            texto_extraido = pytesseract.image_to_string(img_bw, config='--psm 7').strip().lower()
            if texto_extraido:
                for alvo in lista_alvos:
                    score = fuzz.partial_ratio(alvo, texto_extraido)
                    print(f"[Fuzzy Match] Alvo: '{alvo}' vs OCR: '{texto_extraido}' -> Pontuação: {score}%")
                    if score >= FUZZY_MATCH_THRESHOLD:
                        print(f"ALVO DETECTADO! '{alvo}' é {score}% parecido com '{texto_extraido}'.")
                        self.after(0, self.update_status, f"Alvo '{alvo}' ({score}%) encontrado!", "magenta")
                        return True
            print("--- Fim da Verificação de Nome ---")
        except Exception as e: print(f"[Aviso OCR] Erro: {e}")
        return False
    def lutar(self):
        escolha = self.attack_choice_var.get()
        if escolha == 'run': self.update_status("A tentar fugir...", "cyan"); pyautogui.press('r'); time.sleep(1.0)
        else:
            self.update_status(f"Batalha! Usando ação '{escolha}'", "orange"); time.sleep(PAUSA_INICIO_BATALHA)
            try:
                if pyautogui.locateOnScreen(IMAGEM_BATALHA, confidence=CONFIANCA): pyautogui.press(escolha); time.sleep(PAUSA_ENTRE_ATAQUES)
            except pyautogui.PyAutoGUIException: pass
        time.sleep(PAUSA_FIM_BATALHA)
    def ativar_janela_jogo(self):
        try:
            hwnd = win32gui.FindWindow(None, NOME_JANELA)
            if hwnd == 0: return False
            if win32gui.GetForegroundWindow() != hwnd: shell = win32com.client.Dispatch("WScript.Shell"); shell.SendKeys('%'); win32gui.SetForegroundWindow(hwnd); time.sleep(0.1)
            return True
        except Exception as e: print(f"Erro ao ativar janela: {e}"); return False
    def run_bot_logic(self):
        while self.bot_is_running:
            if not self.ativar_janela_jogo(): self.after(0, self.update_status, f"Janela perdida!", "red"); self.after(0, self.stop_bot); break
            try:
                if pyautogui.locateOnScreen(IMAGEM_BATALHA, confidence=CONFIANCA):
                    self.update_status("Batalha detectada!", "orange"); time.sleep(PAUSA_INICIO_BATALHA)
                    self.indice_movimento_atual = 0 
                    if self.capture_enabled_var.get() and self.is_target_pokemon(): self.tentar_capturar()
                    else: self.lutar()
                    self.last_action_time = 0
                else: 
                    self.update_status("Procurando...", "green")
                    selected_mode = self.bot_mode_var.get()
                    if selected_mode == 'patrulha': self.mover()
                    elif selected_mode == 'pesca': self.pescar()
            except pyautogui.PyAutoGUIException:
                selected_mode = self.bot_mode_var.get()
                if selected_mode == 'patrulha': self.mover()
                elif selected_mode == 'pesca': self.pescar()
            except Exception as e: self.after(0, self.update_status, f"Erro no loop: {e}", "red"); self.after(0, self.stop_bot); break
            time.sleep(0.2) 
    def mover(self):
        if not self.bot_is_running: return
        tecla = SEQUENCIA_MOVIMENTO[self.indice_movimento_atual]; pyautogui.keyDown(tecla); time.sleep(DURACAO_MOVIMENTO); pyautogui.keyUp(tecla)
        self.indice_movimento_atual = (self.indice_movimento_atual + 1) % len(SEQUENCIA_MOVIMENTO)
    def pescar(self):
        if not self.bot_is_running: return
        try:
            pyautogui.locateOnScreen(IMAGEM_PEIXE, confidence=CONFIANCA_PEIXE); self.update_status("Peixe fisgado!", "green"); pyautogui.press(TECLA_PESCA) 
            self.last_action_time = time.time(); time.sleep(2.0); return
        except pyautogui.PyAutoGUIException:
            if time.time() - self.last_action_time > COOLDOWN_RECAST_PESCA: self.update_status("Lançando a vara...", "cyan"); pyautogui.press(TECLA_PESCA); self.last_action_time = time.time()
        except Exception as e: print(f"Erro na pesca: {e}"); self.update_status(f"Erro na pesca: {e}", "red")

if __name__ == "__main__":
    app = BotControllerGUI()
    app.mainloop()