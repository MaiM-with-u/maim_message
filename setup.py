from setuptools import setup, find_packages

setup(
    name="maim_message",
    version="0.1.0",
    packages=find_packages(),
    author="tcmofashi",
    author_email="mofashiforzbx@qq.com",
    description="A message handling library for maimcore",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/maim_message",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "pydantic>=1.8.0",
        "aiohttp>=3.8.0",
        "dataclasses>=0.6;python_version<'3.7'",
        "typing-extensions>=4.0.0;python_version<'3.8'",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.15.0",
            "black>=21.0",
            "isort>=5.0",
            "mypy>=0.900",
            "flake8>=3.9",
        ]
    },
    python_requires=">=3.6",
)
