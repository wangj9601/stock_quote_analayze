from setuptools import setup, find_packages

setup(
    name="stock_quote_analyze",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'pandas>=1.5.0',
        'numpy>=1.21.0',
        'tushare>=1.2.0',
        'akshare>=1.8.0',
        'requests>=2.28.0',
        'sqlalchemy>=1.4.0',
    ],
    python_requires='>=3.8',
) 