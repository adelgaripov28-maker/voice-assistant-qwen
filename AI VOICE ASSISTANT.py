#!/usr/bin/env python3
"""
SONAR - Голосовой ассистент на базе Qwen3-VL-4B
Современный интерфейс с анимациями и стильным дизайном
"""

import requests
import json
import sys
import re
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk, font as tkfont
from queue import Queue
import speech_recognition as sr
import os
import pygame
from gtts import gTTS
import tempfile
from datetime import datetime
from PIL import Image, ImageTk  # pip install Pillow
import random

# ==================== КОНФИГУРАЦИЯ ====================
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-vl-4b"

WAKE_WORDS = ["сонар", "sonar"]
SLEEP_WORDS = ["до свидания", "пока"]

# Настройки
MAX_TOKENS = 2000
TEMPERATURE = 0.7
TIMEOUT = 60
SAVE_FOLDER = "созданные_файлы"

# Цветовая схема (Catppuccin Mocha)
COLORS = {
    'bg': '#1e1e2e',
    'bg_dark': '#181825',
    'bg_light': '#313244',
    'text': '#cdd6f4',
    'text_secondary': '#a6adc8',
    'accent': '#89b4fa',
    'accent_hover': '#74a7ea',
    'green': '#a6e3a1',
    'red': '#f38ba8',
    'yellow': '#f9e2af',
    'pink': '#f5c2e7',
    'mauve': '#cba6f7',
    'peach': '#fab387',
    'surface': '#2d2d44',
    'surface_hover': '#3d3d5c'
}

# =====================================================

class ModernButton(tk.Canvas):
    """Современная кнопка с анимацией"""
    def __init__(self, master, text="", icon="", command=None, color=COLORS['accent'], 
                 width=100, height=40, font_size=12):
        super().__init__(master, width=width, height=height, bg=COLORS['bg'], 
                        highlightthickness=0, relief='flat')
        
        self.command = command
        self.color = color
        self.text = text
        self.icon = icon
        self.font_size = font_size
        self.is_hover = False
        self.is_pressed = False
        
        # Создаем фон кнопки
        self.bg_rect = self.create_rectangle(2, 2, width-2, height-2, 
                                            fill=color, outline="", 
                                            cornerradius=10)
        
        # Текст
        self.text_id = self.create_text(width//2, height//2, 
                                       text=f"{icon} {text}" if icon else text,
                                       fill='#1e1e2e', 
                                       font=('Segoe UI', font_size, 'bold'))
        
        # Привязываем события
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_press)
        self.bind('<ButtonRelease-1>', self.on_release)
    
    def on_enter(self, event):
        self.is_hover = True
        self.itemconfig(self.bg_rect, fill=self.darken_color(self.color, 0.8))
        self.config(cursor='hand2')
    
    def on_leave(self, event):
        self.is_hover = False
        self.is_pressed = False
        self.itemconfig(self.bg_rect, fill=self.color)
    
    def on_press(self, event):
        self.is_pressed = True
        self.move(self.bg_rect, 0, 2)
        self.move(self.text_id, 0, 2)
    
    def on_release(self, event):
        self.is_pressed = False
        self.move(self.bg_rect, 0, -2)
        self.move(self.text_id, 0, -2)
        if self.command:
            self.command()
    
    def darken_color(self, color, factor):
        """Затемнение цвета"""
        r, g, b = self.hex_to_rgb(color)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return self.rgb_to_hex(r, g, b)
    
    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(self, r, g, b):
        return f'#{r:02x}{g:02x}{b:02x}'

class VoiceAssistant:
    def __init__(self):
        # Создаем папку для файлов
        if not os.path.exists(SAVE_FOLDER):
            os.makedirs(SAVE_FOLDER)
        
        # Инициализация
        pygame.mixer.init()
        
        # Распознавание
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Настройка микрофона
        print("🔊 Настройка микрофона...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            self.recognizer.energy_threshold = 3000
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 1.5
            self.recognizer.phrase_threshold = 0.3
        print("✅ Микрофон готов")
        
        # Состояния
        self.is_active = True
        self.is_processing = False
        self.is_speaking = False
        self.running = True
        self.conversation_history = []
        self.messages = []
        
        # GUI
        self.root = None
        self.text_area = None
        self.status_label = None
        self.input_entry = None
        self.voice_button = None
        self.status_indicator = None
        self.text_queue = Queue()
        
        # Системный промпт
        self.system_prompt = """Ты - полезный голосовой ассистент Qwen3-VL-4B. 
        Отвечай на вопросы подробно и полностью. 
        Если пользователь просит создать файл с кодом - выдавай ПОЛНЫЙ код.
        Не используй в ответах символы * и #.
        ВАЖНО: Всегда дописывай код до конца!"""
        
        self.create_gui()
    
    def create_gui(self):
        """Создание красивого GUI"""
        self.root = tk.Tk()
        self.root.title("SONAR - Голосовой ассистент")
        self.root.geometry("900x700")
        self.root.configure(bg=COLORS['bg'])
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Центрируем окно
        self.center_window()
        
        # Убираем стандартные границы
        self.root.overrideredirect(False)
        
        # ============ ВЕРХНЯЯ ПАНЕЛЬ ============
        header = tk.Frame(self.root, bg=COLORS['bg_dark'], height=80)
        header.pack(fill='x', pady=(0, 10))
        header.pack_propagate(False)
        
        # Иконка и статус
        status_frame = tk.Frame(header, bg=COLORS['bg_dark'])
        status_frame.pack(pady=10)
        
        # Индикатор статуса (анимированный)
        self.status_indicator = tk.Label(
            status_frame, 
            text="🟢", 
            font=('Segoe UI', 28), 
            bg=COLORS['bg_dark']
        )
        self.status_indicator.pack(side='left', padx=10)
        
        # Название
        title_frame = tk.Frame(status_frame, bg=COLORS['bg_dark'])
        title_frame.pack(side='left')
        
        tk.Label(
            title_frame,
            text="🔊 SONAR",
            font=('Segoe UI', 24, 'bold'),
            bg=COLORS['bg_dark'],
            fg=COLORS['text']
        ).pack(anchor='w')
        
        tk.Label(
            title_frame,
            text=f"Голосовой ассистент • {MODEL_NAME}",
            font=('Segoe UI', 10),
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary']
        ).pack(anchor='w')
        
        # ============ ТЕКСТОВАЯ ОБЛАСТЬ ============
        # Рамка
        text_frame = tk.Frame(self.root, bg=COLORS['bg_light'], padx=2, pady=2)
        text_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
        self.text_area = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 11),
            bg=COLORS['bg'],
            fg=COLORS['text'],
            insertbackground=COLORS['accent'],
            relief=tk.FLAT,
            padx=15,
            pady=15,
            borderwidth=0,
            spacing1=5,
            spacing2=3,
            spacing3=5
        )
        self.text_area.pack(fill='both', expand=True)
        
        # Настройка тегов для разных типов сообщений
        self.text_area.tag_configure('user', foreground=COLORS['accent'], font=('Segoe UI', 11, 'bold'))
        self.text_area.tag_configure('assistant', foreground=COLORS['text'], font=('Segoe UI', 11))
        self.text_area.tag_configure('system', foreground=COLORS['yellow'], font=('Segoe UI', 10, 'italic'))
        self.text_area.tag_configure('file', foreground=COLORS['green'], font=('Segoe UI', 10, 'bold'))
        self.text_area.tag_configure('error', foreground=COLORS['red'], font=('Segoe UI', 10, 'bold'))
        self.text_area.tag_configure('timestamp', foreground=COLORS['text_secondary'], font=('Segoe UI', 9))
        
        # Приветствие
        self.add_formatted_message("🔊 SONAR запущен!\n", 'system')
        self.add_formatted_message("Скажите 'СОНАР' для активации или нажмите 🎤\n", 'system')
        self.add_formatted_message("=" * 50 + "\n\n", 'system')
        self.add_formatted_message("✅ Ассистент активен\n", 'system')
        
        # ============ СТАТУС-БАР ============
        status_bar = tk.Frame(self.root, bg=COLORS['bg_dark'], height=35)
        status_bar.pack(fill='x', pady=(5, 0))
        status_bar.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_bar,
            text="🟢 Активен • Готов к работе",
            font=('Segoe UI', 10),
            bg=COLORS['bg_dark'],
            fg=COLORS['green']
        )
        self.status_label.pack(side='left', padx=15)
        
        # Информация о файлах
        files_count = len([f for f in os.listdir(SAVE_FOLDER) if os.path.isfile(os.path.join(SAVE_FOLDER, f))])
        tk.Label(
            status_bar,
            text=f"📁 Файлов: {files_count}",
            font=('Segoe UI', 10),
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary']
        ).pack(side='right', padx=15)
        
        # ============ НИЖНЯЯ ПАНЕЛЬ ============
        control = tk.Frame(self.root, bg=COLORS['bg'], height=70)
        control.pack(fill='x', padx=15, pady=10)
        control.pack_propagate(False)
        
        # Поле ввода
        input_frame = tk.Frame(control, bg=COLORS['bg_light'], padx=2, pady=2)
        input_frame.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.input_entry = tk.Entry(
            input_frame,
            font=('Segoe UI', 12),
            bg=COLORS['bg'],
            fg=COLORS['text'],
            insertbackground=COLORS['accent'],
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0
        )
        self.input_entry.pack(fill='x', padx=10, pady=5)
        self.input_entry.bind('<Return>', lambda e: self.process_text_input())
        
        # Кнопки
        btn_frame = tk.Frame(control, bg=COLORS['bg'])
        btn_frame.pack(side='right')
        
        # Отправить
        self.create_modern_button(
            btn_frame, "📤", self.process_text_input,
            COLORS['accent'], 50, 40
        ).pack(side='left', padx=3)
        
        # Голос
        self.voice_btn = self.create_modern_button(
            btn_frame, "🎤", self.start_voice_input,
            COLORS['green'], 50, 40
        )
        self.voice_btn.pack(side='left', padx=3)
        
        # Папка
        self.create_modern_button(
            btn_frame, "📁", self.open_files_folder,
            COLORS['mauve'], 50, 40
        ).pack(side='left', padx=3)
        
        # Очистка
        self.create_modern_button(
            btn_frame, "🗑️", self.clear_history,
            COLORS['red'], 50, 40
        ).pack(side='left', padx=3)
        
        # Вкл/Выкл
        self.toggle_btn = self.create_modern_button(
            btn_frame, "⏸️", self.toggle_state,
            COLORS['yellow'], 50, 40
        )
        self.toggle_btn.pack(side='left', padx=3)
        
        # Запускаем фоновые процессы
        self.process_queue()
        self.start_background_listener()
        
        self.root.mainloop()
    
    def create_modern_button(self, parent, text, command, color, width=50, height=40):
        """Создание красивой кнопки"""
        btn = tk.Button(
            parent,
            text=text,
            font=('Segoe UI', 14),
            bg=color,
            fg=COLORS['bg'],
            relief=tk.FLAT,
            cursor='hand2',
            width=width//10,
            height=height//15,
            command=command
        )
        
        # Стиль при наведении
        def on_enter(e):
            btn.config(bg=self.darken_color(color, 0.8))
        def on_leave(e):
            btn.config(bg=color)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    def darken_color(self, color, factor):
        """Затемнение цвета"""
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def center_window(self):
        """Центрирование окна"""
        self.root.update_idletasks()
        width, height = 900, 700
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def add_formatted_message(self, text, tag='system', timestamp=True):
        """Добавление форматированного сообщения"""
        if timestamp:
            time_str = datetime.now().strftime("%H:%M")
            self.text_area.insert(tk.END, f"[{time_str}] ", 'timestamp')
        self.text_area.insert(tk.END, text, tag)
        self.text_area.see(tk.END)
    
    def process_queue(self):
        """Обработка очереди"""
        try:
            while not self.text_queue.empty():
                item = self.text_queue.get_nowait()
                if isinstance(item, dict):
                    self.add_formatted_message(item['text'], item.get('tag', 'system'), item.get('timestamp', True))
                else:
                    self.add_formatted_message(str(item), 'system')
        except:
            pass
        if self.running:
            self.root.after(100, self.process_queue)
    
    def update_status(self, message, color=None):
        """Обновление статуса"""
        if self.status_label:
            self.status_label.config(text=message, fg=color or COLORS['text_secondary'])
    
    def add_to_chat(self, speaker, text, tag='system'):
        """Добавление в чат"""
        self.text_queue.put({
            'text': f"{speaker}: {text}\n",
            'tag': tag,
            'timestamp': True
        })
    
    def update_ui_state(self):
        """Обновление UI состояния"""
        if self.is_active:
            self.status_indicator.config(text="🟢")
            self.update_status("🟢 Активен • Готов к работе", COLORS['green'])
            self.input_entry.config(state='normal')
            self.toggle_btn.config(text="⏸️")
            self.root.title("SONAR - Активен 🟢")
        else:
            self.status_indicator.config(text="🔴")
            self.update_status("🔴 Режим ожидания • Скажите 'СОНАР'", COLORS['red'])
            self.input_entry.config(state='disabled')
            self.toggle_btn.config(text="▶️")
            self.root.title("SONAR - Ожидание 🔴")
    
    def toggle_state(self):
        """Переключение состояния"""
        self.is_active = not self.is_active
        self.update_ui_state()
        if self.is_active:
            self.add_to_chat("🔄", "Активирован ✅", 'system')
            self.speak_text("Активирован")
        else:
            self.add_to_chat("🔄", "Режим ожидания 💤", 'system')
            self.speak_text("До свидания")
    
    def open_files_folder(self):
        """Открытие папки"""
        try:
            if sys.platform == 'win32':
                os.startfile(SAVE_FOLDER)
            elif sys.platform == 'darwin':
                os.system(f'open "{SAVE_FOLDER}"')
            else:
                os.system(f'xdg-open "{SAVE_FOLDER}"')
            self.add_to_chat("📁", f"Открыта папка {SAVE_FOLDER}", 'file')
        except Exception as e:
            self.add_to_chat("❌", f"Ошибка: {e}", 'error')
    
    # [Остальные методы такие же как в предыдущей версии]
    # start_background_listener, start_voice_input, process_text_input,
    # process_question, speak_text, clean_text_for_speech, save_to_file,
    # detect_file_creation_command, clear_history, on_closing
    
    def start_background_listener(self):
        """Фоновое прослушивание"""
        def listen():
            while self.running:
                if self.is_processing or self.is_speaking:
                    time.sleep(0.3)
                    continue
                
                try:
                    with self.microphone as source:
                        audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=8)
                        
                        try:
                            text = self.recognizer.recognize_google(audio, language='ru-RU').lower()
                            print(f"🎤 Распознано: {text}")
                            self.process_voice_command(text)
                        except sr.UnknownValueError:
                            pass
                        except sr.RequestError:
                            pass
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    if "listener" not in str(e).lower():
                        print(f"⚠️ Ошибка: {e}")
                    time.sleep(0.1)
        
        threading.Thread(target=listen, daemon=True).start()
        print("🎤 Фоновое прослушивание запущено")
    
    def detect_file_creation_command(self, text):
        """Определение команды создания файла"""
        keywords = [
            "создай файл", "создай текстовый файл", "создай код",
            "сохрани в файл", "запиши в файл", "сделай файл",
            "сохрани код", "создай скрипт", "сохрани текст"
        ]
        return any(keyword in text for keyword in keywords)
    
    def process_voice_command(self, text):
        """Обработка голосовой команды"""
        if not self.is_active:
            for word in WAKE_WORDS:
                if word in text:
                    self.is_active = True
                    self.root.after(0, self.update_ui_state)
                    self.root.after(0, lambda: self.add_to_chat("🔄", "Активирован ✅", 'system'))
                    self.root.after(0, lambda: self.speak_text("Активирован"))
                    return
        
        if self.is_active:
            for word in SLEEP_WORDS:
                if word in text:
                    self.is_active = False
                    self.root.after(0, self.update_ui_state)
                    self.root.after(0, lambda: self.add_to_chat("🔄", "Режим ожидания 💤", 'system'))
                    self.root.after(0, lambda: self.speak_text("До свидания"))
                    return
        
        if self.is_active and self.detect_file_creation_command(text):
            self.root.after(0, lambda: self.add_to_chat("📁", f"Создаю файл: {text}", 'file'))
            self.root.after(0, lambda: self.process_question(text, create_file=True))
            return
        
        if self.is_active and len(text) > 2:
            is_command = any(word in text for word in WAKE_WORDS + SLEEP_WORDS)
            if not is_command:
                self.root.after(0, lambda: self.add_to_chat("🎤 Вы", f'"{text}"', 'user'))
                self.root.after(0, lambda: self.process_question(text))
    
    def start_voice_input(self):
        """Ручной голосовой ввод"""
        if self.is_processing or not self.is_active:
            return
        
        self.root.after(0, lambda: self.voice_btn.config(bg=COLORS['red'], text="🔴"))
        self.root.after(0, lambda: self.update_status("🎤 Говорите...", COLORS['yellow']))
        
        def recognize():
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
                    text = self.recognizer.recognize_google(audio, language='ru-RU')
                    
                    self.root.after(0, lambda: self.add_to_chat("🎤 Вы", f'"{text}"', 'user'))
                    
                    if self.detect_file_creation_command(text.lower()):
                        self.root.after(0, lambda: self.process_question(text, create_file=True))
                    else:
                        self.root.after(0, lambda: self.process_question(text))
                    
            except sr.UnknownValueError:
                self.root.after(0, lambda: self.update_status("❌ Не распознано", COLORS['red']))
            except sr.WaitTimeoutError:
                self.root.after(0, lambda: self.update_status("⏱️ Время вышло", COLORS['yellow']))
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"❌ {e}", COLORS['red']))
            finally:
                self.root.after(0, lambda: self.voice_btn.config(bg=COLORS['green'], text="🎤"))
                if self.is_active:
                    self.root.after(0, lambda: self.update_status("🟢 Активен", COLORS['green']))
        
        threading.Thread(target=recognize, daemon=True).start()
    
    def process_text_input(self):
        """Текстовый ввод"""
        if self.is_processing or not self.is_active:
            return
        
        text = self.input_entry.get().strip()
        if text:
            self.input_entry.delete(0, tk.END)
            self.add_to_chat("📝 Вы", text, 'user')
            
            if self.detect_file_creation_command(text.lower()):
                self.process_question(text, create_file=True)
            else:
                self.process_question(text)
    
    def save_to_file(self, content, filename=None):
        """Сохранение файла"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if 'def ' in content or 'class ' in content or 'import ' in content:
                ext, name = '.py', f"код_{timestamp}"
            elif '<html' in content:
                ext, name = '.html', f"страница_{timestamp}"
            elif '{' in content and '}' in content:
                ext, name = '.json', f"данные_{timestamp}"
            else:
                ext, name = '.txt', f"текст_{timestamp}"
            filename = f"{name}{ext}"
        
        filepath = os.path.join(SAVE_FOLDER, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    def clean_text_for_speech(self, text):
        """Очистка текста"""
        text = re.sub(r'\*[^*]*\*', '', text)
        text = re.sub(r'#[^#]*#', '', text)
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+', '', text)
        text = re.sub(r'\[[^\]]*\]\([^)]*\)', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def process_question(self, question, create_file=False):
        """Обработка вопроса"""
        if self.is_processing or not self.is_active:
            return
        
        self.is_processing = True
        self.root.after(0, lambda: self.update_status("⏳ Обработка...", COLORS['yellow']))
        
        def process():
            try:
                if create_file:
                    modified_question = f"{question}. Выдай только содержимое файла без пояснений. Код пиши полностью."
                else:
                    modified_question = question
                
                self.conversation_history.append({
                    "role": "user",
                    "content": modified_question
                })
                
                payload = {
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": self.system_prompt}
                    ] + self.conversation_history,
                    "temperature": TEMPERATURE,
                    "max_tokens": MAX_TOKENS,
                    "stream": False
                }
                
                response = requests.post(
                    LM_STUDIO_URL,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content']
                    
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": answer
                    })
                    
                    if create_file:
                        try:
                            filepath = self.save_to_file(answer)
                            filename = os.path.basename(filepath)
                            self.root.after(0, lambda: self.add_to_chat("📁", f"✅ Файл сохранен: {filename}", 'file'))
                            self.root.after(0, lambda: self.add_to_chat("📁", f"Путь: {filepath}", 'file'))
                            self.root.after(0, lambda: self.update_status(f"✅ Файл сохранен: {filename}", COLORS['green']))
                            self.root.after(100, lambda: self.speak_text(f"Файл {filename} сохранен"))
                        except Exception as e:
                            self.root.after(0, lambda: self.add_to_chat("❌", f"Ошибка: {e}", 'error'))
                    else:
                        self.root.after(0, lambda: self.add_to_chat("🤖 Qwen", answer, 'assistant'))
                        clean_answer = self.clean_text_for_speech(answer)
                        if clean_answer and len(clean_answer) > 2:
                            self.root.after(100, lambda: self.speak_text(clean_answer))
                    
                    self.root.after(0, lambda: self.update_status("✅ Готово", COLORS['green']))
                    
                else:
                    self.root.after(0, lambda: self.add_to_chat("❌", f"Ошибка: {response.status_code}", 'error'))
                    
            except Exception as e:
                self.root.after(0, lambda: self.add_to_chat("❌", f"{str(e)[:100]}", 'error'))
            finally:
                self.is_processing = False
                if self.is_active:
                    self.root.after(0, lambda: self.update_status("🟢 Активен", COLORS['green']))
        
        threading.Thread(target=process, daemon=True).start()
    
    def speak_text(self, text):
        """Озвучивание"""
        if self.is_speaking or not text:
            return
        
        def speak():
            self.is_speaking = True
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    temp_file = f.name
                
                tts = gTTS(text=text, lang='ru', slow=False)
                tts.save(temp_file)
                
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                
                pygame.mixer.music.stop()
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
            except Exception as e:
                print(f"⚠️ TTS ошибка: {e}")
            finally:
                self.is_speaking = False
        
        threading.Thread(target=speak, daemon=True).start()
    
    def clear_history(self):
        """Очистка истории"""
        self.conversation_history = []
        self.text_area.delete(1.0, tk.END)
        self.add_formatted_message("🧹 История очищена\n", 'system')
        self.add_formatted_message("=" * 50 + "\n\n", 'system')
        self.add_formatted_message("✅ Ассистент активен\n", 'system')
        self.update_status("🧹 История очищена", COLORS['yellow'])
    
    def on_closing(self):
        """Закрытие"""
        self.running = False
        pygame.mixer.music.stop()
        if self.root:
            self.root.destroy()
        sys.exit(0)

def main():
    print("=" * 60)
    print("🔊 SONAR - Голосовой ассистент")
    print("=" * 60)
    print("✅ Скажите 'СОНАР' для активации")
    print("❌ Скажите 'ДО СВИДАНИЯ' для деактивации")
    print("📁 Скажите 'СОЗДАЙ ФАЙЛ' для сохранения")
    print("=" * 60)
    
    try:
        import requests, speech_recognition, gtts, pygame
    except ImportError as e:
        print(f"❌ Установите: pip install -r requirements.txt")
        sys.exit(1)
    
    assistant = VoiceAssistant()

if __name__ == "__main__":
    main()