#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统 - 交互式审查脚本
用于在 AI 完成主要任务后，允许用户进行交互式审查和提供子提示。
"""

import sys
import os

if __name__ == "__main__":
    # 尝试使 stdout 无缓冲，以获得更响应的交互。
    # 这可能在某些平台或非 TTY 环境下不起作用，
    # 但这是此类交互式脚本的良好实践。
    try:
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
    except Exception:
        pass # 忽略如果无缓冲失败，例如在某些环境中

    try:
        sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)
    except Exception:
        pass # 忽略

    print("--- FINAL REVIEW GATE ACTIVE ---", flush=True)
    print("AI 已完成其主要操作。等待您的审查或进一步的子提示。", flush=True)
    print("输入您的子提示，或输入以下之一以表示完成：'TASK_COMPLETE'、'Done'、'Quit'、'q'", flush=True)
    
    active_session = True
    while active_session:
        try:
            # 发出脚本已准备好接收输入的信号。
            # AI 不需要解析此内容，但它对用户可见性有好处。
            print("REVIEW_GATE_AWAITING_INPUT:", end="", flush=True) 
            
            line = sys.stdin.readline()
            
            if not line:  # EOF
                print("--- REVIEW GATE: STDIN CLOSED (EOF), EXITING SCRIPT ---", flush=True)
                active_session = False
                break
            
            user_input = line.strip()

            # 检查退出条件
            if user_input.upper() in ['TASK_COMPLETE', 'DONE', 'QUIT', 'Q']:
                print(f"--- REVIEW GATE: USER SIGNALED COMPLETION WITH '{user_input.upper()}' ---", flush=True)
                active_session = False
                break
            elif user_input: # 如果有任何其他非空输入（且不是完成命令）
                # 这是 AI 将"监听"的关键行。
                print(f"USER_REVIEW_SUB_PROMPT: {user_input}", flush=True)
            # 如果 user_input 为空（且不是完成命令），
            # 循环仅继续，并且将再次打印 "REVIEW_GATE_AWAITING_INPUT:"。
            
        except KeyboardInterrupt:
            print("--- REVIEW GATE: SESSION INTERRUPTED BY USER (KeyboardInterrupt) ---", flush=True)
            active_session = False
            break
        except Exception as e:
            print(f"--- REVIEW GATE SCRIPT ERROR: {e} ---", flush=True)
            active_session = False
            break
            
    print("--- FINAL REVIEW GATE SCRIPT EXITED ---", flush=True) 