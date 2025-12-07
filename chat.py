import os
import json
import time
import threading
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# 引入 OpenAI 标准库 (国内大模型通用)
from openai import OpenAI, APIError

# ================= 配置与文件路径 =================

CONFIG_FILE = 'config.json'
PROMPT_FILE = 'system_prompt.txt'

# ================= 核心逻辑 =================

def load_file_content(filepath):
    """通用文件读取函数"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ 读取 {filepath} 失败: {e}")
        return None

def load_config():
    """加载配置"""
    content = load_file_content(CONFIG_FILE)
    if content:
        return json.loads(content)
    return {}

# 加载配置
config = load_config()
API_KEY_POOL = config.get('api_key_pool', "sk-jlcjxwykxzufjsbcktazizxsousvpnbcbgctcjgharamoncn" )
# 默认配置 fallback 到 DeepSeek 官方
BASE_URL = config.get('base_url', "https://api.siliconflow.cn/v1") 
MODEL_NAME = config.get('model_name', "Qwen/Qwen2.5-7B-Instruct")

# 全局变量：当前使用的 Key 索引
current_key_index = 0

def get_next_key():
    """轮询获取 API Key"""
    global current_key_index
    if not API_KEY_POOL:
        return None, -1
    key = API_KEY_POOL[current_key_index]
    idx = current_key_index
    current_key_index = (current_key_index + 1) % len(API_KEY_POOL)
    return key, idx

def generate_summary(chat_log_content, log_callback=print):
    """
    调用 OpenAI 兼容接口 (如 DeepSeek/Qwen) 生成总结
    """
    if not API_KEY_POOL:
        log_callback("❌ 错误: config.json 中缺少 api_key_pool！")
        return None

    # 1. 读取提示词模板
    system_prompt_content = load_file_content(PROMPT_FILE)
    if not system_prompt_content:
        log_callback(f"❌ 错误: 找不到提示词文件 {PROMPT_FILE}")
        return None

    # 2. 发起请求
    max_retries = len(API_KEY_POOL) * 2 
    
    log_callback(f"🚀 开始分析，正在调用 {MODEL_NAME} (Key池大小: {len(API_KEY_POOL)})...")
    
    for attempt in range(max_retries):
        api_key, idx = get_next_key()
        
        try:
            # 初始化 OpenAI 客户端 (无代理，直连)
            client = OpenAI(
                api_key=api_key,
                base_url=BASE_URL
            )

            # 发起 Chat 请求
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt_content},
                    {"role": "user", "content": f"以下是需要分析的聊天记录：\n\n{chat_log_content}"}
                ],
                stream=False,
                temperature=0.7 
            )
            
            # 获取结果
            result = response.choices[0].message.content
            return result

        except Exception as e:
            error_str = str(e)
            log_callback(f"⚠️ Key #{idx} 调用失败: {error_str[:100]}...") 
            
            time.sleep(1)
            continue

    log_callback("❌ 所有 API Key 均尝试失败，无法生成总结。请检查 Key 余额或网络连接。")
    return None

# ================= GUI 界面逻辑 =================

class ChatSummaryApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"社群聊天记录分析 - {MODEL_NAME}")
        self.root.geometry("600x550")
        
        # 顶部：文件选择区域
        self.frame_top = tk.Frame(root, padx=10, pady=10)
        self.frame_top.pack(fill=tk.X)
        
        self.lbl_file = tk.Label(self.frame_top, text="请选择聊天记录文件 (.txt):", font=("Arial", 10))
        self.lbl_file.pack(anchor="w")
        
        self.entry_path = tk.Entry(self.frame_top, width=50)
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.btn_select = tk.Button(self.frame_top, text="📂 选择文件", command=self.select_file)
        self.btn_select.pack(side=tk.RIGHT)

        # 中部：模型信息显示
        self.frame_info = tk.Frame(root, padx=10, pady=0)
        self.frame_info.pack(fill=tk.X)
        self.lbl_model = tk.Label(self.frame_info, text=f"当前模型: {MODEL_NAME} | 接口: {BASE_URL}", fg="gray", font=("Arial", 8))
        self.lbl_model.pack(anchor="w")

        # 中部：操作按钮
        self.frame_action = tk.Frame(root, padx=10, pady=10)
        self.frame_action.pack(fill=tk.X)
        
        self.btn_run = tk.Button(self.frame_action, text="🚀 开始生成总结", command=self.start_thread, 
                                 bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_run.pack(fill=tk.X)

        # 底部：日志显示
        self.lbl_log = tk.Label(root, text="运行日志:", padx=10, anchor="w")
        self.lbl_log.pack(fill=tk.X, pady=(5, 0))
        
        self.text_log = scrolledtext.ScrolledText(root, height=15, state='disabled', font=("Consolas", 9))
        self.text_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 初始化检查
        self.log(f"=== 欢迎使用聊天记录分析助手 ===")

        if not API_KEY_POOL:
            self.log("❌ 严重错误: 未检测到 API Key，请检查 config.json")
            self.btn_run.config(state='disabled')

    def log(self, message):
        """向日志框添加信息"""
        self.text_log.config(state='normal')
        self.text_log.insert(tk.END, message + "\n")
        self.text_log.see(tk.END) # 自动滚动到底部
        self.text_log.config(state='disabled')
        self.root.update_idletasks()

    def select_file(self):
        filename = filedialog.askopenfilename(
            title="选择聊天记录文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filename:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, filename)
            self.log(f"📂 已选择文件: {filename}")

    def start_thread(self):
        """开启新线程运行分析"""
        input_file = self.entry_path.get()
        if not input_file or not os.path.exists(input_file):
            messagebox.showwarning("提示", "请先选择有效的聊天记录文件！")
            return
        
        self.btn_run.config(state='disabled', text="⏳ 正在分析中...")
        self.btn_select.config(state='disabled')
        
        thread = threading.Thread(target=self.run_analysis, args=(input_file,))
        thread.daemon = True
        thread.start()

    def run_analysis(self, input_file):
        try:
            # 1. 确定输出文件名
            file_dir = os.path.dirname(input_file)
            file_name = os.path.basename(input_file)
            name_without_ext = os.path.splitext(file_name)[0]
            output_file = os.path.join(file_dir, f"{name_without_ext}_summary.md")

            # 2. 读取内容
            self.log(f"📖 正在读取文件...")
            chat_content = load_file_content(input_file)
            
            if not chat_content:
                self.log("❌ 文件内容为空或读取失败")
                return
            
            # 简单字数检查
            if len(chat_content) < 10:
                self.log("⚠️ 内容太短，无法分析。")
                return

            self.log(f"📊 字数统计: {len(chat_content)} 字")

            # 3. 生成总结
            start_time = time.time()
            summary = generate_summary(chat_content, log_callback=self.log)
            
            if summary:
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    
                    elapsed = time.time() - start_time
                    self.log("-" * 30)
                    self.log(f"✅ 总结生成成功！耗时: {elapsed:.2f}秒")
                    self.log(f"💾 结果已保存至:\n{output_file}")
                    self.log("-" * 30)
                    messagebox.showinfo("成功", f"总结已生成！\n\n保存在: {output_file}")
                except Exception as e:
                    self.log(f"❌ 保存文件失败: {e}")
            else:
                self.log("❌ 生成失败，请检查 config.json。")

        except Exception as e:
            self.log(f"❌ 发生未知错误: {e}")
        
        finally:
            self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        self.btn_run.config(state='normal', text="🚀 开始生成总结")
        self.btn_select.config(state='normal')

def main():
    root = tk.Tk()
    app = ChatSummaryApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()