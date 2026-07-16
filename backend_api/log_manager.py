#!/usr/bin/env python3
"""
一阳穿三线策略日志管理工具
"""

import os
import glob
import shutil
from datetime import datetime, timedelta
import argparse

from backend_core.logging_utils import get_logs_dir

class LogManager:
    """日志管理器（默认扫描项目根 logs/）"""
    
    def __init__(self, log_dir=None):
        self.log_dir = str(log_dir or get_logs_dir())
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def list_logs(self):
        """列出所有日志文件"""
        pattern = os.path.join(self.log_dir, "one_yang_three_lines_*.log")
        logs = glob.glob(pattern)
        logs.sort(key=os.path.getmtime, reverse=True)
        
        if not logs:
            print("📁 没有找到日志文件")
            return []
        
        print(f"📋 找到 {len(logs)} 个日志文件:")
        print("-" * 80)
        
        for i, log_file in enumerate(logs, 1):
            file_size = os.path.getsize(log_file) / 1024 / 1024  # MB
            mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            filename = os.path.basename(log_file)
            
            print(f"{i:2d}. {filename}")
            print(f"     大小: {file_size:.2f} MB")
            print(f"     修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        return logs
    
    def clean_old_logs(self, days=7):
        """清理指定天数前的日志文件"""
        pattern = os.path.join(self.log_dir, "one_yang_three_lines_*.log")
        logs = glob.glob(pattern)
        
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        total_size = 0
        
        print(f"🧹 清理 {days} 天前的日志文件...")
        
        for log_file in logs:
            mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            if mtime < cutoff_time:
                file_size = os.path.getsize(log_file)
                try:
                    os.remove(log_file)
                    deleted_count += 1
                    total_size += file_size
                    print(f"  🗑️ 删除: {os.path.basename(log_file)} ({file_size/1024/1024:.2f} MB)")
                except Exception as e:
                    print(f"  ❌ 删除失败: {os.path.basename(log_file)} - {str(e)}")
        
        if deleted_count == 0:
            print("  ✅ 没有需要清理的日志文件")
        else:
            print(f"  🎉 清理完成: 删除了 {deleted_count} 个文件，释放 {total_size/1024/1024:.2f} MB 空间")
    
    def archive_logs(self, days=30):
        """归档指定天数前的日志文件"""
        pattern = os.path.join(self.log_dir, "one_yang_three_lines_*.log")
        logs = glob.glob(pattern)
        
        cutoff_time = datetime.now() - timedelta(days=days)
        archive_dir = os.path.join(self.log_dir, "archive")
        
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        
        archived_count = 0
        
        print(f"📦 归档 {days} 天前的日志文件到 {archive_dir}...")
        
        for log_file in logs:
            mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            if mtime < cutoff_time:
                filename = os.path.basename(log_file)
                archive_path = os.path.join(archive_dir, filename)
                
                try:
                    shutil.move(log_file, archive_path)
                    archived_count += 1
                    print(f"  📁 归档: {filename}")
                except Exception as e:
                    print(f"  ❌ 归档失败: {filename} - {str(e)}")
        
        if archived_count == 0:
            print("  ✅ 没有需要归档的日志文件")
        else:
            print(f"  🎉 归档完成: 归档了 {archived_count} 个文件")
    
    def show_log_stats(self):
        """显示日志统计信息"""
        pattern = os.path.join(self.log_dir, "one_yang_three_lines_*.log")
        logs = glob.glob(pattern)
        
        if not logs:
            print("📊 没有日志文件")
            return
        
        total_size = sum(os.path.getsize(log) for log in logs)
        total_files = len(logs)
        
        # 最新和最旧的日志
        logs.sort(key=os.path.getmtime)
        oldest = datetime.fromtimestamp(os.path.getmtime(logs[0]))
        newest = datetime.fromtimestamp(os.path.getmtime(logs[-1]))
        
        print("📊 日志统计信息:")
        print("-" * 40)
        print(f"文件总数: {total_files}")
        print(f"总大小: {total_size/1024/1024:.2f} MB")
        print(f"最早日志: {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"最新日志: {newest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"时间跨度: {(newest - oldest).days} 天")
        
        # 按日期统计
        print("\n📅 按日期统计:")
        date_counts = {}
        for log_file in logs:
            mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            date_str = mtime.strftime('%Y-%m-%d')
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
        
        for date_str in sorted(date_counts.keys(), reverse=True)[:7]:
            print(f"  {date_str}: {date_counts[date_str]} 个文件")
    
    def tail_log(self, filename=None, lines=20):
        """查看日志文件的最后几行"""
        if not filename:
            # 获取最新的日志文件
            pattern = os.path.join(self.log_dir, "one_yang_three_lines_*.log")
            logs = glob.glob(pattern)
            if not logs:
                print("📁 没有找到日志文件")
                return
            logs.sort(key=os.path.getmtime, reverse=True)
            filename = logs[0]
        
        if not os.path.exists(filename):
            print(f"❌ 文件不存在: {filename}")
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                print(f"📄 显示文件 {os.path.basename(filename)} 的最后 {len(tail_lines)} 行:")
                print("-" * 80)
                
                for line in tail_lines:
                    print(line.rstrip())
        
        except Exception as e:
            print(f"❌ 读取文件失败: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="一阳穿三线策略日志管理工具")
    parser.add_argument("action", choices=["list", "clean", "archive", "stats", "tail"], 
                       help="操作类型")
    parser.add_argument("--days", type=int, default=7, 
                       help="天数 (用于clean和archive操作)")
    parser.add_argument("--lines", type=int, default=20, 
                       help="行数 (用于tail操作)")
    parser.add_argument("--file", type=str, 
                       help="日志文件名 (用于tail操作)")
    
    args = parser.parse_args()
    
    manager = LogManager()
    
    if args.action == "list":
        manager.list_logs()
    elif args.action == "clean":
        manager.clean_old_logs(args.days)
    elif args.action == "archive":
        manager.archive_logs(args.days)
    elif args.action == "stats":
        manager.show_log_stats()
    elif args.action == "tail":
        manager.tail_log(args.file, args.lines)

if __name__ == "__main__":
    main()
