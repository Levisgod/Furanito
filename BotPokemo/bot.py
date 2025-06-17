import pyautogui
import time
import sys
import threading
import tkinter as tk
from tkinter import font, ttk
from PIL import Image, ImageOps
import os
import json
import traceback

try:
    import win32gui, win32com.client, psutil, pytesseract, pythoncom, win32api, win32con
    from pynput import mouse
    from thefuzz import fuzz
except ImportError:
    print("ERRO: Bibliotecas em falta. Execute:")
    print("pip install pywin32 psutil pytesseract pillow pynput")
    print("pip install thefuzz python-Levenshtein")
    sys.exit()

# --- CONFIGURAÇÕES GLOBAIS ---
CONFIG_FILE = "config.json"
NOME_JANELA = "Pokemon Blaze Online"
IMAGEM_BATALHA = 'batalha.png'
IMAGEM_HP_INIMIGO = 'fim_batalha.png'
IMAGEM_PEIXE = 'peixe.png'
DEFAULT_POKEMON_PARAR = "ditto, zigzagoon"
IMAGEM_APRENDER_ATAQUE = 'x.png'
POSICAO_RECUSAR_ATAQUE = (0, 0)

def get_tesseract_path():
    if getattr(sys, 'frozen', False): base_path = sys._MEIPASS
    else: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'tesseract', 'tesseract.exe')

try: pytesseract.pytesseract.tesseract_cmd = get_tesseract_path()
except Exception as e: print(f"Aviso: Não foi possível configurar o Tesseract. Erro: {e}")

REGIAO_NOME_POKEMON = (0, 0, 0, 0); POSICAO_BAG = (0, 0); POSICAO_POKEBOLA = (0, 0)

# Constantes de comportamento
SEQUENCIA_MOVIMENTO = ['a', 'd']; TECLA_PESCA = 'f';
CONFIANCA_BATALHA = 0.7; CONFIANCA_HP = 0.8; CONFIANCA_PEIXE = 0.8
FUZZY_MATCH_THRESHOLD = 70
DURACAO_MOVIMENTO = 0.01

# Pausas de batalha
PAUSA_INICIO_BATALHA = 0.1
PAUSA_POS_ACAO = 0.3
PAUSA_FIM_BATALHA = 0.3
PAUSA_POS_FUGA = 0.3

game_hwnd = None
def find_game_window():
    global game_hwnd
    if game_hwnd and win32gui.IsWindow(game_hwnd): return True
    try: game_hwnd = win32gui.FindWindow(None, NOME_JANELA); return game_hwnd is not None
    except Exception: game_hwnd = None; return False

print("Sistema de controlo PRONTO.")

class BotControllerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Controlador do Bot"); self.geometry("380x520"); self.wm_attributes("-topmost", 1)
        self.bot_is_running = False; self.bot_thread = None; self.indice_movimento_atual = 0
        self.listener = None; self.last_action_time = 0; self.capture_count = 0
        self.calibration_mode = None; self.ocr_calibration_step = 0; self.capture_calibration_step = 0; self.first_click = None
        self.default_font = font.Font(family="Helvetica", size=10); self.bold_font = font.Font(family="Helvetica", size=10, weight="bold")
        self.bot_mode_var = tk.StringVar(value="patrulha"); self.pokemon_name_var = tk.StringVar(value=DEFAULT_POKEMON_PARAR)
        self.region_var = tk.StringVar(value=f"Região: {REGIAO_NOME_POKEMON}"); self.attack_choice_var = tk.StringVar(value="3")
        self.capture_enabled_var = tk.BooleanVar(value=True); self.bag_pos_var = tk.StringVar(value=f"Bag: {POSICAO_BAG}")
        self.ball_pos_var = tk.StringVar(value=f"Bola: {POSICAO_POKEBOLA}"); self.capture_count_var = tk.StringVar(value="Alvos Capturados: 0")
        self.invert_colors_var = tk.BooleanVar(value=False)
        self.estado_pesca = "iniciar"
        
        self.recusar_ataque_var = tk.BooleanVar(value=True)
        self.pos_recusar_var = tk.StringVar(value=f"Pos. Recusar: {POSICAO_RECUSAR_ATAQUE}")
        
        self.load_config(); self.create_widgets(); self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        if os.path.exists(CONFIG_FILE) and REGIAO_NOME_POKEMON[2] > 0: status_inicial, status_color = "Bot parado. Configuração carregada.", "green"
        else: status_inicial, status_color = "PRIMEIRA VEZ? Vá à aba de Calibração!", "red"
        self.status_label = tk.Label(self, text=status_inicial, font=self.default_font, fg=status_color); self.status_label.pack(pady=5)
        
        notebook = ttk.Notebook(self); notebook.pack(pady=10, padx=10, fill="both", expand=True)
        tab_control = ttk.Frame(notebook); tab_calibration = ttk.Frame(notebook)
        notebook.add(tab_control, text='Controle Principal'); notebook.add(tab_calibration, text='Calibração')
        
        mode_frame = tk.LabelFrame(tab_control, text="Modo de Operação", font=self.default_font); mode_frame.pack(pady=5, padx=10, fill=tk.X)
        self.patrol_radio = tk.Radiobutton(mode_frame, text="Patrulha (Captura)", variable=self.bot_mode_var, value="patrulha", font=self.default_font); self.patrol_radio.pack(side=tk.LEFT, expand=True)
        self.ev_radio = tk.Radiobutton(mode_frame, text="Treino EV", variable=self.bot_mode_var, value="ev", font=self.default_font); self.ev_radio.pack(side=tk.LEFT, expand=True)
        self.fish_radio = tk.Radiobutton(mode_frame, text="Pesca", variable=self.bot_mode_var, value="pesca", font=self.default_font); self.fish_radio.pack(side=tk.LEFT, expand=True)
        
        target_frame = tk.LabelFrame(tab_control, text="Pokémon Alvo (separar por vírgula)", font=self.default_font); target_frame.pack(pady=5, padx=10, fill=tk.X)
        self.pokemon_entry = tk.Entry(target_frame, textvariable=self.pokemon_name_var, font=self.default_font); self.pokemon_entry.pack(pady=5, padx=5, fill=tk.X)
        
        attack_frame = tk.LabelFrame(tab_control, text="Ação de Batalha Padrão", font=self.default_font); attack_frame.pack(pady=5, padx=10, fill=tk.X)
        self.radio_buttons = []
        for i in range(1, 5): rb = tk.Radiobutton(attack_frame, text=f"{i}", variable=self.attack_choice_var, value=str(i)); rb.pack(side=tk.LEFT, expand=True); self.radio_buttons.append(rb)
        run_rb = tk.Radiobutton(attack_frame, text="Run", variable=self.attack_choice_var, value="run"); run_rb.pack(side=tk.LEFT, expand=True); self.radio_buttons.append(run_rb)
        
        options_frame = tk.LabelFrame(tab_control, text="Opções Adicionais", font=self.default_font); options_frame.pack(pady=5, padx=10, fill=tk.X)
        self.recusar_ataque_check = tk.Checkbutton(options_frame, text="Recusar automaticamente novos ataques", variable=self.recusar_ataque_var, font=self.default_font)
        self.recusar_ataque_check.pack(anchor=tk.W, padx=5)

        stats_frame = tk.LabelFrame(tab_control, text="Estatísticas", font=self.default_font); stats_frame.pack(pady=5, padx=10, fill=tk.X)
        self.capture_count_label = tk.Label(stats_frame, textvariable=self.capture_count_var, font=self.default_font); self.capture_count_label.pack(pady=5, padx=5)

        calibration_frame = tk.LabelFrame(tab_calibration, text="Calibração do OCR", font=self.default_font); calibration_frame.pack(pady=5, padx=10, fill=tk.X)
        ocr_buttons_frame = tk.Frame(calibration_frame); ocr_buttons_frame.pack(fill=tk.X, pady=5)
        self.calibrate_ocr_button = tk.Button(ocr_buttons_frame, text="Calibrar Região OCR", command=self.start_ocr_calibration, font=self.default_font); self.calibrate_ocr_button.pack(side=tk.LEFT, padx=5)
        self.test_ocr_button = tk.Button(ocr_buttons_frame, text="Testar OCR", command=self.test_ocr, font=self.default_font); self.test_ocr_button.pack(side=tk.LEFT, padx=5)
        self.region_label = tk.Label(calibration_frame, textvariable=self.region_var, font=self.default_font); self.region_label.pack(fill=tk.X, padx=5)
        self.invert_colors_check = tk.Checkbutton(calibration_frame, text="Inverter Cores (para texto branco)", variable=self.invert_colors_var, font=self.default_font); self.invert_colors_check.pack(anchor=tk.W, padx=5)
        
        capture_frame = tk.LabelFrame(tab_calibration, text="Captura Automática", font=self.default_font); capture_frame.pack(pady=5, padx=10, fill=tk.X)
        self.capture_check = tk.Checkbutton(capture_frame, text="Tentar Capturar Pokémon Alvo", variable=self.capture_enabled_var, font=self.default_font); self.capture_check.pack(anchor=tk.W, padx=5)
        capture_buttons_frame = tk.Frame(capture_frame); capture_buttons_frame.pack(fill=tk.X, pady=5)
        self.calibrate_capture_button = tk.Button(capture_buttons_frame, text="Calibrar Captura", command=self.start_capture_calibration, font=self.default_font); self.calibrate_capture_button.pack(side=tk.LEFT, padx=5)
        self.bag_pos_label = tk.Label(capture_buttons_frame, textvariable=self.bag_pos_var, font=self.default_font); self.bag_pos_label.pack(side=tk.LEFT, padx=5)
        self.ball_pos_label = tk.Label(capture_buttons_frame, textvariable=self.ball_pos_var, font=self.default_font); self.ball_pos_label.pack(side=tk.LEFT, padx=5)
        
        attack_learn_frame = tk.LabelFrame(tab_calibration, text="Aprendizagem de Ataques", font=self.default_font)
        attack_learn_frame.pack(pady=5, padx=10, fill=tk.X)
        attack_learn_buttons_frame = tk.Frame(attack_learn_frame)
        attack_learn_buttons_frame.pack(fill=tk.X, pady=5)
        self.calibrate_refuse_button = tk.Button(attack_learn_buttons_frame, text="Calibrar Posição 'Não'", command=self.start_refuse_calibration, font=self.default_font)
        self.calibrate_refuse_button.pack(side=tk.LEFT, padx=5)
        self.pos_recusar_label = tk.Label(attack_learn_buttons_frame, textvariable=self.pos_recusar_var, font=self.default_font)
        self.pos_recusar_label.pack(side=tk.LEFT, padx=5)
        
        self.start_button = tk.Button(self, text="Start Bot", command=self.start_bot, font=self.bold_font, bg="#4CAF50", fg="white"); self.start_button.pack(pady=5, fill=tk.X, padx=20)
        self.stop_button = tk.Button(self, text="Stop Bot", command=self.stop_bot, font=self.bold_font, bg="#f44336", fg="white", state=tk.DISABLED); self.stop_button.pack(pady=(0, 5), fill=tk.X, padx=20)

    def load_config(self):
        global REGIAO_NOME_POKEMON, POSICAO_BAG, POSICAO_POKEBOLA, POSICAO_RECUSAR_ATAQUE
        try:
            with open(CONFIG_FILE, 'r') as f: config_data = json.load(f)
            REGIAO_NOME_POKEMON = tuple(config_data.get('regiao_ocr', (0,0,0,0)))
            POSICAO_BAG = tuple(config_data.get('posicao_bag', (0,0)))
            POSICAO_POKEBOLA = tuple(config_data.get('posicao_pokebola', (0,0)))
            POSICAO_RECUSAR_ATAQUE = tuple(config_data.get('posicao_recusar_ataque', (0,0)))
            self.recusar_ataque_var.set(config_data.get('recusar_ataques', True))
            self.invert_colors_var.set(config_data.get('inverter_cores', False))
            self.region_var.set(f"Região: {REGIAO_NOME_POKEMON}")
            self.bag_pos_var.set(f"Bag: {POSICAO_BAG}")
            self.ball_pos_var.set(f"Bola: {POSICAO_POKEBOLA}")
            self.pos_recusar_var.set(f"Pos. Recusar: {POSICAO_RECUSAR_ATAQUE}")
        except (FileNotFoundError, json.JSONDecodeError): print("Arquivo de configuração não encontrado ou inválido. Usando padrões.")
        
    def save_config(self):
        config_data = {
            'regiao_ocr': REGIAO_NOME_POKEMON, 
            'posicao_bag': POSICAO_BAG, 
            'posicao_pokebola': POSICAO_POKEBOLA, 
            'inverter_cores': self.invert_colors_var.get(),
            'posicao_recusar_ataque': POSICAO_RECUSAR_ATAQUE,
            'recusar_ataques': self.recusar_ataque_var.get()
        }
        with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)
        
    def update_status(self, message, color="black"): self.status_label.config(text=message, fg=color)
    def update_capture_count_label(self): self.capture_count_var.set(f"Alvos Capturados: {self.capture_count}")
    
    def start_ocr_calibration(self):
        self.update_status("CALIBRAR OCR: Clique no CANTO SUPERIOR ESQUERDO.", "blue")
        self.calibration_mode = "ocr"; self.ocr_calibration_step = 1
        self.listener = mouse.Listener(on_click=self.on_click); self.listener.start()
        
    def start_capture_calibration(self):
        self.update_status("CALIBRAR CAPTURA: Clique no botão da BAG.", "blue")
        self.calibration_mode = "capture"; self.capture_calibration_step = 1
        self.listener = mouse.Listener(on_click=self.on_click); self.listener.start()

    def start_refuse_calibration(self):
        self.update_status("CALIBRAR RECUSA: Clique no botão 'Não'/'Cancelar'.", "blue")
        self.calibration_mode = "recusar_ataque" 
        self.listener = mouse.Listener(on_click=self.on_click); self.listener.start()
        
    def on_click(self, x, y, button, pressed):
        if not pressed or not self.listener: return

        if self.calibration_mode == "ocr":
            if self.ocr_calibration_step == 1: self.first_click = (x, y); self.ocr_calibration_step = 2; self.after(0, self.update_status, "Ótimo! Agora clique no CANTO INFERIOR DIREITO.", "blue"); return
            elif self.ocr_calibration_step == 2: global REGIAO_NOME_POKEMON; REGIAO_NOME_POKEMON = (self.first_click[0], self.first_click[1], x - self.first_click[0], y - self.first_click[1]); self.after(0, self.update_status, "Calibração OCR concluída!", "green"); self.after(0, self.region_var.set, f"Região: {REGIAO_NOME_POKEMON}")
        
        elif self.calibration_mode == "capture":
            if self.capture_calibration_step == 1: global POSICAO_BAG; POSICAO_BAG = (x, y); self.capture_calibration_step = 2; self.after(0, self.update_status, "BAG salva! Agora clique na POKÉBOLA.", "blue"); self.after(0, self.bag_pos_var.set, f"Bag: {POSICAO_BAG}"); return
            elif self.capture_calibration_step == 2: global POSICAO_POKEBOLA; POSICAO_POKEBOLA = (x, y); self.after(0, self.update_status, "Calibração de captura concluída!", "green"); self.after(0, self.ball_pos_var.set, f"Bola: {POSICAO_POKEBOLA}")

        elif self.calibration_mode == "recusar_ataque":
            global POSICAO_RECUSAR_ATAQUE; POSICAO_RECUSAR_ATAQUE = (x, y)
            self.after(0, self.update_status, "Posição de recusa de ataque salva!", "green"); self.after(0, self.pos_recusar_var.set, f"Pos. Recusar: {POSICAO_RECUSAR_ATAQUE}")

        self.save_config(); self.calibration_mode = None; self.ocr_calibration_step = 0; self.capture_calibration_step = 0; self.listener.stop()

    def start_bot(self):
        self.save_config()
        if not find_game_window(): self.update_status(f"Janela '{NOME_JANELA}' não encontrada!", "red"); return
        if not self.bot_is_running:
            self.capture_count = 0; self.update_capture_count_label()
            self.last_action_time = 0
            self.bot_is_running = True
            self.update_status("Bot a iniciar...", "blue")
            self.bot_thread = threading.Thread(target=self.run_bot_logic, daemon=True); self.bot_thread.start()
            self.toggle_ui_state(tk.DISABLED)
            
    def stop_bot(self):
        if self.bot_is_running: self.bot_is_running = False;
        if self.bot_thread and self.bot_thread.is_alive(): self.bot_thread.join(timeout=1.0)
        self.update_status("Bot parado.", "green"); self.toggle_ui_state(tk.NORMAL)
        
    def toggle_ui_state(self, state):
        is_disabled = state == tk.DISABLED
        self.start_button.config(state=tk.DISABLED if is_disabled else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if is_disabled else tk.DISABLED)
        for widget in [self.patrol_radio, self.ev_radio, self.fish_radio, self.pokemon_entry, self.calibrate_ocr_button, self.test_ocr_button, self.invert_colors_check, self.calibrate_capture_button, self.capture_check, self.recusar_ataque_check, self.calibrate_refuse_button] + self.radio_buttons:
            widget.config(state=state)
        
    def on_closing(self): self.save_config(); self.stop_bot(); self.destroy()

    def executar_com_foco(self, acao, *args, **kwargs):
        if not find_game_window(): self.update_status("Janela do jogo perdida!", "red"); self.after(0, self.stop_bot); return None
        foco_anterior = win32gui.GetForegroundWindow()
        resultado = None
        if game_hwnd != foco_anterior:
            try:
                shell = win32com.client.Dispatch("WScript.Shell"); shell.SendKeys('%')
                win32gui.SetForegroundWindow(game_hwnd); time.sleep(0.05)
            except Exception as e: print(f"Não foi possível focar na janela: {e}"); return None
        
        resultado = acao(*args, **kwargs)
        
        if game_hwnd != foco_anterior and win32gui.IsWindow(foco_anterior):
            try: win32gui.SetForegroundWindow(foco_anterior)
            except Exception: pass
        return resultado

    def mover(self):
        if not self.bot_is_running: return
        tecla = SEQUENCIA_MOVIMENTO[self.indice_movimento_atual]; pyautogui.keyDown(tecla); time.sleep(DURACAO_MOVIMENTO); pyautogui.keyUp(tecla)
        self.indice_movimento_atual = (self.indice_movimento_atual + 1) % len(SEQUENCIA_MOVIMENTO)
    
    def lutar(self):
        escolha = self.attack_choice_var.get()
        self.update_status(f"A atacar com o movimento '{escolha}'...", "red")
        pyautogui.press(escolha)

    def tentar_fugir(self):
        self.update_status("A fugir...", "cyan")
        pyautogui.press('r')

    def tentar_capturar(self):
        self.update_status("A usar Pokébola...", "purple")
        pyautogui.moveTo(POSICAO_BAG, duration=0.1); pyautogui.click()
        time.sleep(0.3)
        pyautogui.moveTo(POSICAO_POKEBOLA, duration=0.1); pyautogui.click()
        
    def pescar(self):
        try:
            if pyautogui.locateOnScreen(IMAGEM_BATALHA, confidence=CONFIANCA_BATALHA):
                self.update_status("Batalha durante a pesca!", "orange")
                self.handle_battle()
                self.last_action_time = 0 
                return
        except pyautogui.PyAutoGUIException:
            pass

        try:
            if pyautogui.locateOnScreen(IMAGEM_PEIXE, confidence=CONFIANCA_PEIXE):
                self.update_status("Peixe fisgado!", "green")
                pyautogui.press(TECLA_PESCA)
                time.sleep(2.5) 
                self.last_action_time = 0
                return
        except pyautogui.PyAutoGUIException:
            pass

        if time.time() - self.last_action_time > 4.0: # Pode usar a constante COOLDOWN_RECAST_PESCA
            self.update_status("A lançar a vara...", "cyan")
            pyautogui.press(TECLA_PESCA)
            self.last_action_time = time.time()
            
    def test_ocr(self): self.executar_com_foco(self._internal_test_ocr)
    def _internal_test_ocr(self):
        if REGIAO_NOME_POKEMON[2] <= 0: self.update_status("ERRO: Região OCR não calibrada!", "red"); return
        try:
            time.sleep(0.2); screenshot = pyautogui.screenshot(region=REGIAO_NOME_POKEMON); img_cinza = screenshot.convert('L')
            if self.invert_colors_var.get(): img_cinza = ImageOps.invert(img_cinza)
            texto_extraido = pytesseract.image_to_string(img_cinza, config='--psm 7').strip().lower()
            if not texto_extraido: self.update_status("OCR não leu nenhum texto.", "orange"); return
            self.update_status(f"OCR Leu: '{texto_extraido}'", "blue")
        except Exception as e: self.update_status(f"Erro no teste de OCR: {e}", "red")

    def is_target_pokemon(self):
        nomes_alvo_str = self.pokemon_name_var.get().strip()
        if not nomes_alvo_str or REGIAO_NOME_POKEMON[2] <= 0: return False, None
        lista_alvos = [nome.strip().lower() for nome in nomes_alvo_str.split(',') if nome.strip()]
        if not lista_alvos: return False, None
        try:
            screenshot = self.executar_com_foco(pyautogui.screenshot, region=REGIAO_NOME_POKEMON)
            if screenshot is None: return False, None
            img_cinza = screenshot.convert('L')
            if self.invert_colors_var.get(): img_cinza = ImageOps.invert(img_cinza)
            texto_extraido = pytesseract.image_to_string(img_cinza, config='--psm 7').strip().lower()
            if texto_extraido:
                for alvo in lista_alvos:
                    if fuzz.partial_ratio(alvo, texto_extraido) >= FUZZY_MATCH_THRESHOLD:
                        self.after(0, self.update_status, f"Alvo '{alvo}' encontrado!", "magenta"); return True, texto_extraido
            return False, texto_extraido
        except Exception as e:
            print(f"[Aviso OCR] Erro ao ler nome: {e}")
            return False, None

    def handle_battle(self):
        time.sleep(PAUSA_INICIO_BATALHA + 0.3)
        self.update_status("Batalha detectada!", "orange")

        if self.attack_choice_var.get() == 'run':
            self.executar_com_foco(self.tentar_fugir)
            time.sleep(PAUSA_POS_FUGA)
            return
            
        e_um_alvo, nome_ocr = self.is_target_pokemon()

        modo_atual = self.bot_mode_var.get()
        if modo_atual == 'ev' and not e_um_alvo:
            self.executar_com_foco(self.tentar_fugir)
            time.sleep(PAUSA_POS_FUGA)
            return

        acao_a_executar = self.lutar
        if modo_atual != 'ev' and self.capture_enabled_var.get() and e_um_alvo:
            acao_a_executar = self.tentar_capturar
        
        self.executar_com_foco(acao_a_executar)
        time.sleep(PAUSA_POS_ACAO)
        
        try:
            self.executar_com_foco(pyautogui.locateOnScreen, IMAGEM_HP_INIMIGO, confidence=CONFIANCA_HP)
            self.update_status("Inimigo sobreviveu. A aguardar próximo turno...", "red")
        except pyautogui.PyAutoGUIException:
            self.update_status("Inimigo derrotado/capturado!", "green")
            if e_um_alvo:
                self.capture_count += 1
                self.after(0, self.update_capture_count_label)
            time.sleep(PAUSA_FIM_BATALHA)

    def run_bot_logic(self):
        pythoncom.CoInitialize()

        def _internal_logic():
            try:
                if self.recusar_ataque_var.get():
                    try:
                        if pyautogui.locateOnScreen(IMAGEM_APRENDER_ATAQUE, confidence=0.8):
                            self.update_status("Recusando novo ataque...", "purple")
                            pyautogui.moveTo(POSICAO_RECUSAR_ATAQUE, duration=0.2)
                            pyautogui.click()
                            time.sleep(0.8)
                            return
                    except pyautogui.ImageNotFoundException:
                        pass
                
                if pyautogui.locateOnScreen(IMAGEM_BATALHA, confidence=CONFIANCA_BATALHA):
                    self.handle_battle()
                    self.last_action_time = 0 # Reinicia a pesca após a batalha
                    return 

                current_mode = self.bot_mode_var.get()
                if current_mode == 'pesca':
                    self.pescar()
                else:
                    self.update_status("A patrulhar...", "green")
                    self.mover()

            except pyautogui.ImageNotFoundException:
                current_mode = self.bot_mode_var.get()
                if current_mode == 'pesca':
                    self.pescar()
                else:
                    self.update_status("A patrulhar...", "green")
                    self.mover()
            except Exception as e:
                print("\n--- ERRO CRÍTICO INESPERADO ---"); traceback.print_exc()
                self.after(0, self.update_status, f"ERRO: {type(e).__name__}", "red")
                self.after(0, self.stop_bot)
                self.bot_is_running = False 

        while self.bot_is_running:
            self.executar_com_foco(_internal_logic)
            time.sleep(0.2)
            
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    app = BotControllerGUI()
    app.mainloop()