"""
backend-core包安装配置
"""

from setuptools import setup, find_packages

setup(
    name="backend-core",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "akshare",
        "pandas",
        "numpy",
        "requests",
        "python-dotenv",
        "loguru",
        "apscheduler>=3.10.0",
    ],
    python_requires=">=3.8",
    author="Your Name",
    author_email="your.email@example.com",
    description="股票分析系统核心功能包",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 